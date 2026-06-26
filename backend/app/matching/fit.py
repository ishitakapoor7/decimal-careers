"""Calibrated hybrid fit: turn raw cosine similarity into a fit score + a tier +
human-readable reasons, using the structured résumé profile.

    calibrated = cosine * seniority_factor * education_factor * skill_factor

The factors are the *structured* signals the embedding can't express on its own.
`skill_factor` is the subtle one: the embedding already rewards skill overlap, but it
sees a FLAT skill list — it can't tell a must-have from a nice-to-have. So skill_factor
carries only that missing distinction: required coverage dominates, preferred
contributes lightly, in a deliberately gentle band (≥ _SKILL_FLOOR). It adds the
must-have/nice-to-have *weighting*, rather than re-scoring overlap from scratch (which
would double-count cosine's undifferentiated skill signal). Making the two layers fully
orthogonal — drop skills from the embedding so the vector owns semantic fit and the
structured layer owns exact-skill fit — is the Phase-2 decouple.

Everything is fail-open: a None/"unknown" profile field (or a job with no required
skills listed) yields factor 1.0, so an unconfident extraction degrades to today's
pure-similarity behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.generator import INTERN_OPEN_TO_GRADS
from app.resume.profile import JOB_RANK, ResumeProfile, SeniorityRank
from app.storage.models import Job, SeniorityLevel

Tier = Literal["strong", "good", "possible"]
_TIER_ORDER: dict[Tier, int] = {"possible": 0, "good": 1, "strong": 2}

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
class SkillOverlap:
    # Résumé↔job skill matches, split by the job's must-have vs nice-to-have lists so
    # the explanation can weight required hits — a candidate matching only nice-to-haves
    # must not read the same as one matching the must-haves.
    required: list[str]
    preferred: list[str]


@dataclass(frozen=True)
class JobFitPartial:
    # Pre-finalization: the score is known but the tier isn't (it depends on the
    # candidate's top score across the result set, which the ranker computes).
    calibrated: float
    reasons: list[str]
    matched_required: list[str]
    matched_preferred: list[str]
    tier_cap: Tier | None  # hard ceiling imposed by a penalty (e.g. "possible")


@dataclass(frozen=True)
class JobFit:
    tier: Tier
    reasons: list[str]
    matched_required: list[str]
    matched_preferred: list[str]


def job_seniority_rank(job: Job) -> SeniorityRank:
    return JOB_RANK[job.seniority_level]


def job_requires_enrollment(job: Job) -> bool:
    # Intern level ⇒ enrollment required, EXCEPT the minority of internships the
    # generator marks open to recent grads (INTERN_OPEN_TO_GRADS in the quals) — so a
    # graduated candidate is only penalized on roles that truly need a degree in
    # progress. Derived from the JD text (single source of truth), no schema field.
    if job.seniority_level != SeniorityLevel.INTERN:
        return False
    return not any(INTERN_OPEN_TO_GRADS in q.lower() for q in job.required_quals)


def seniority_factor(
    cand: SeniorityRank | None, job_rank: SeniorityRank
) -> tuple[float, str | None, Tier | None]:
    """Asymmetric, distance-based multiplier. Unknown candidate → 1.0 (fail-open).
    Large over-qualification (a VP applying to an intern role) is penalized hardest
    so it sinks below the relevance threshold."""
    if cand is None:
        return 1.0, None, None
    d = int(cand) - int(job_rank)
    factor = _DISTANCE_FACTOR.get(abs(d), 0.25)
    if d >= 3:
        factor *= 0.6  # extra hit for being far over-qualified
    if abs(d) < 2:
        return factor, None, None  # adjacent levels: mild, no reason/cap
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
    cap: Tier = "possible" if abs(d) >= 3 else "good"
    return factor, reason, cap


def education_factor(
    profile: ResumeProfile, job: Job
) -> tuple[float, str | None, Tier | None]:
    # Graduated → an internship that requires current enrollment.
    if job_requires_enrollment(job) and profile.education_status == "graduated":
        return (
            0.10,
            "This internship requires current enrollment; your résumé reads as "
            "already graduated.",
            "possible",
        )
    # The inverse mismatch: a still-enrolled student against a role that demands real
    # professional experience (senior+). Fire ONLY when nothing in the résumé
    # contradicts the early-career-student read — a working professional pursuing a
    # part-time degree carries a senior title or stated tenure, and seniority_factor
    # already handles them, so penalizing here would be a false positive (fail-open).
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
            "possible",
        )
    return 1.0, None, None


def skill_overlap(profile_skills: list[str], job: Job) -> SkillOverlap:
    # Explanation-only: which of the job's listed skills literally appear in the
    # résumé, split into must-have vs nice-to-have. Order follows the job's lists for
    # stable display. A job predating the required/preferred split (empty
    # required_skills) yields all matches as preferred — we never over-claim a
    # "required" hit we can't substantiate.
    have = {s.lower() for s in profile_skills}
    required = {s.lower() for s in job.required_skills}
    req: list[str] = []
    pref: list[str] = []
    for s in job.skills:
        if s.lower() not in have:
            continue
        (req if s.lower() in required else pref).append(s)
    return SkillOverlap(required=req, preferred=pref)


# Skill-coverage band: required coverage dominates, preferred contributes lightly, and
# the floor keeps the whole factor in [_SKILL_FLOOR, 1.0] — a gentle nudge that ranks
# "matches the must-haves" above "matches only the nice-to-haves" without letting skill
# overlap (already in cosine) dominate the score. Coverage is normalized so matching
# everything the job lists scores 1.0 even when the job has no preferred skills.
_SKILL_FLOOR = 0.85
_REQ_WEIGHT = 0.8
_PREF_WEIGHT = 0.2


def skill_factor(overlap: SkillOverlap, job: Job) -> float:
    n_req = len(job.required_skills)
    if n_req == 0:
        return 1.0  # fail-open: no required/preferred split to assess (e.g. old job)
    n_pref = len(job.skills) - n_req
    has_pref = n_pref > 0
    req_cov = len(overlap.required) / n_req
    pref_cov = (len(overlap.preferred) / n_pref) if has_pref else 0.0
    denom = _REQ_WEIGHT + (_PREF_WEIGHT if has_pref else 0.0)
    coverage = (_REQ_WEIGHT * req_cov + _PREF_WEIGHT * pref_cov) / denom
    return _SKILL_FLOOR + (1.0 - _SKILL_FLOOR) * coverage


def _min_cap(a: Tier | None, b: Tier | None) -> Tier | None:
    caps = [c for c in (a, b) if c is not None]
    return min(caps, key=lambda c: _TIER_ORDER[c]) if caps else None


def make_rescorer(
    profile: ResumeProfile, job_lookup: Callable[[str], Job | None]
) -> Callable[[str, float], JobFitPartial]:
    """Build the per-job rescorer the ranker applies after the cached cosine search.
    Cheap arithmetic per allowed job; the expensive search stays cached."""

    def rescore(job_id: str, cosine: float) -> JobFitPartial:
        job = job_lookup(job_id)
        if job is None:  # defensive: rank a vanished job at raw similarity
            return JobFitPartial(cosine, [], [], [], None)
        sf, s_reason, s_cap = seniority_factor(profile.seniority, job_seniority_rank(job))
        ef, e_reason, e_cap = education_factor(profile, job)
        overlap = skill_overlap(profile.skills, job)
        skf = skill_factor(overlap, job)  # must-have coverage weighted above nice-to-have
        # Only the hard/negative penalty reasons travel as text; the positive skill
        # match is carried structurally (required vs. preferred) and rendered as
        # labeled chips, so a plain "Matches N skills" line would both duplicate it
        # and blur the must-have/nice-to-have distinction this fix exists to make.
        reasons = [r for r in (e_reason, s_reason) if r]
        return JobFitPartial(
            calibrated=cosine * sf * ef * skf,
            reasons=reasons,
            matched_required=overlap.required,
            matched_preferred=overlap.preferred,
            tier_cap=_min_cap(s_cap, e_cap),
        )

    return rescore


# Absolute calibrated-score bands for tiering. Relative tiering alone (score vs. the
# candidate's BEST) over-labels when that best is itself weak: every near-top role
# becomes "strong" by ratio even at a mediocre absolute score. The final tier takes
# the MORE CONSERVATIVE of the relative and absolute tiers, so a weak absolute fit
# can't be "strong" no matter how it compares to the rest of the page. Grounded in
# the seeded catalog's cosine distribution (in-domain roles ≳0.55, adjacent ≳0.45;
# see app/state.py) and tunable — calibrated == cosine for an unpenalized candidate.
_ABS_STRONG = 0.55
_ABS_GOOD = 0.45


def relative_tier(ratio: float) -> Tier:
    if ratio >= 0.85:
        return "strong"
    if ratio >= 0.65:
        return "good"
    return "possible"


def absolute_tier(calibrated: float) -> Tier:
    if calibrated >= _ABS_STRONG:
        return "strong"
    if calibrated >= _ABS_GOOD:
        return "good"
    return "possible"


def _lower(a: Tier, b: Tier) -> Tier:
    return a if _TIER_ORDER[a] <= _TIER_ORDER[b] else b


def finalize_fit(partial: JobFitPartial, ratio: float) -> JobFit:
    """Tier = the most conservative of: the relative tier (score vs. the candidate's
    best), the absolute tier (raw calibrated strength), and any hard penalty cap. The
    absolute band stops a mediocre top score from making everything 'strong'; the cap
    stops an over-qualified / ineligible role from topping the page."""
    tier = _lower(relative_tier(ratio), absolute_tier(partial.calibrated))
    if partial.tier_cap is not None:
        tier = _lower(tier, partial.tier_cap)
    return JobFit(
        tier=tier,
        reasons=partial.reasons,
        matched_required=partial.matched_required,
        matched_preferred=partial.matched_preferred,
    )
