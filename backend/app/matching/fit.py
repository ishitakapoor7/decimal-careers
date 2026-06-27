"""Calibrated hybrid fit: turn raw cosine similarity into a single 0-5 fit SCORE,
then a tier, using the structured résumé profile.

The weights, the 0-5 anchors, and the tier cutoffs are all calibrated from the
seeded catalog's measured score distributions and documented as tunable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.generator import INTERN_OPEN_TO_GRADS
from app.resume.profile import JOB_RANK, ResumeProfile, SeniorityRank
from app.storage.models import Job, SeniorityLevel, Team

Tier = Literal["strong", "good", "possible"]

# Weights chosen for each factor's exponent in the weighted base. Tuned through multiple runs. 
W_SENIORITY = 0.7
W_EDUCATION = 0.3
W_SKILL = 0.5
W_DOMAIN = 0.7

# Absolute base for 0–5 anchors, read off the measured distributions: a genuine top
# match lands near BASE_MAX, while an unrelated / off-domain résumé's best match
# tops out near BASE_MIN 
BASE_MIN = 0.64
BASE_MAX = 0.865

# Tier cutoffs on the 0–5 score. 
T_STRONG = 3.5
T_GOOD = 2.5
T_POSSIBLE = 1.2

_LEVEL_LABEL: dict[SeniorityRank, str] = {
    SeniorityRank.INTERN: "intern",
    SeniorityRank.ENTRY: "entry",
    SeniorityRank.MID: "mid",
    SeniorityRank.SENIOR: "senior",
    SeniorityRank.STAFF: "staff",
    SeniorityRank.EXECUTIVE: "VP/executive",
}

# |distance| → multiplier. >=4 falls through to 0.25.
_DISTANCE_FACTOR: dict[int, float] = {0: 1.0, 1: 0.92, 2: 0.75, 3: 0.5}


@dataclass(frozen=True)
class JobFitPartial:
    base: float
    reasons: list[str]
    matched_skills: list[str]


@dataclass(frozen=True)
class JobFit:
    tier: Tier
    score: float  
    reasons: list[str]
    matched_skills: list[str]


def job_seniority_rank(job: Job) -> SeniorityRank:
    return JOB_RANK[job.seniority_level]


def job_requires_enrollment(job: Job) -> bool:
    """True if the role is an internship that explicitly requires current enrollment"""
    if job.seniority_level != SeniorityLevel.INTERN:
        return False
    return not any(INTERN_OPEN_TO_GRADS in q.lower() for q in job.required_quals)


def seniority_factor(
    cand: SeniorityRank | None, job_rank: SeniorityRank
) -> tuple[float, str | None]:
    """Asymmetric, distance-based multiplier. Unknown candidate maps to 1 (fail-open)."""
    if cand is None:
        return 1.0, None
    d = int(cand) - int(job_rank)
    factor = _DISTANCE_FACTOR.get(abs(d), 0.25)
    if d >= 3:
        factor *= 0.6  # extra hit for being far over-qualified
    if abs(d) < 2:
        return factor, None  # adjacent levels: mild, no reason
    job_label, cand_label = _LEVEL_LABEL[job_rank], _LEVEL_LABEL[cand]
    if d > 0:
        reason = (
            f"This role is pitched at {job_label} level; your background reads as "
            f"{cand_label}-level."
        )
    else:
        reason = (
            f"This role is pitched at {job_label} level — a step up from your "
            f"{cand_label}-level background."
        )
    return factor, reason


def education_factor(profile: ResumeProfile, job: Job) -> tuple[float, str | None]:
    if job_requires_enrollment(job) and profile.education_status == "graduated":
        return (
            0.10,
            "This internship requires current enrollment; your résumé reads as "
            "already graduated.",
        )
    if (
        profile.education_status == "in_progress"
        and job_seniority_rank(job) >= SeniorityRank.SENIOR
        and (profile.seniority is None or profile.seniority <= SeniorityRank.ENTRY)
        and (profile.total_years is None or profile.total_years < 3)
    ):
        return (
            0.35,
            "Your résumé reads as a current student, but this role expects several "
            "years of professional experience.",
        )
    return 1.0, None


# Clusters: a product/tech/creative side and a go-to-market/business side, with product bridging them.
_TEAM_ADJACENCY: dict[Team, frozenset[Team]] = {
    Team.ENGINEERING: frozenset({Team.PRODUCT, Team.DESIGN}),
    Team.PRODUCT: frozenset({Team.ENGINEERING, Team.DESIGN, Team.MARKETING}),
    Team.DESIGN: frozenset({Team.ENGINEERING, Team.PRODUCT, Team.MARKETING}),
    Team.MARKETING: frozenset({Team.PRODUCT, Team.DESIGN, Team.SALES}),
    Team.SALES: frozenset({Team.MARKETING, Team.OPERATIONS}),
    Team.OPERATIONS: frozenset({Team.FINANCE, Team.SALES}),
    Team.FINANCE: frozenset({Team.OPERATIONS}),
}

# Same domain - full; adjacent discipline - mild downgrade (still reachable as
# good/possible); unrelated - hard downgrade (drops below the floor).
_DOMAIN_ADJACENT = 0.9
_DOMAIN_UNRELATED = 0.5


def team_affinity_factor(
    domain: Team | None, job_team: Team
) -> tuple[float, str | None]:
    if domain is None or job_team == domain:
        return 1.0, None
    if job_team in _TEAM_ADJACENCY.get(domain, frozenset()):
        return _DOMAIN_ADJACENT, None
    return (
        _DOMAIN_UNRELATED,
        f"This role is on the {job_team.value} team, which is outside your "
        f"{domain.value} background.",
    )


def skill_overlap(profile_skills: list[str], job: Job) -> list[str]:
    have = {s.lower() for s in profile_skills}
    return [s for s in job.skills if s.lower() in have]


def skill_factor(n_matched: int) -> float:
    """Downgrade-only skill-evidence multiplier. Concrete overlap (≥2) is neutral;
    thin (1) or absent (0) overlap pulls the score down. """
    if n_matched >= 2:
        return 1.0
    if n_matched == 1:
        return 0.9
    return 0.6


def to_score(base: float) -> float:
    raw = (base - BASE_MIN) / (BASE_MAX - BASE_MIN)
    return 5.0 * min(max(raw, 0.0), 1.0)


def tier_for(score: float) -> Tier | None:
    """Tier from absolute thresholds on the 0-5 score. """
    if score >= T_STRONG:
        return "strong"
    if score >= T_GOOD:
        return "good"
    if score >= T_POSSIBLE:
        return "possible"
    return None


def make_rescorer(
    profile: ResumeProfile, job_lookup: Callable[[str], Job | None]
) -> Callable[[str, float], JobFitPartial]:
    """Build the per-job rescorer the ranker applies after the cached cosine search.
    Cheap arithmetic per allowed job; the expensive search stays cached."""

    def rescore(job_id: str, cosine: float) -> JobFitPartial:
        job = job_lookup(job_id)
        if job is None:  # defensive: rank a vanished job at raw similarity
            return JobFitPartial(cosine, [], [])
        sf, s_reason = seniority_factor(profile.seniority, job_seniority_rank(job))
        ef, e_reason = education_factor(profile, job)
        df, d_reason = team_affinity_factor(profile.domain, job.team)
        matched = skill_overlap(profile.skills, job)
        base = (
            cosine
            * (sf**W_SENIORITY)
            * (ef**W_EDUCATION)
            * (df**W_DOMAIN)
            * (skill_factor(len(matched)) ** W_SKILL)
        )
        reasons = [r for r in (e_reason, s_reason, d_reason) if r]
        return JobFitPartial(base=base, reasons=reasons, matched_skills=matched)

    return rescore


def finalize_fit(partial: JobFitPartial) -> JobFit | None:
    """Turn a partial into a final fit: score from base, tier from score. Returns
    None when the score is below the possible floor"""
    score = to_score(partial.base)
    tier = tier_for(score)
    if tier is None:
        return None
    return JobFit(
        tier=tier,
        score=score,
        reasons=partial.reasons,
        matched_skills=partial.matched_skills,
    )
