"""Calibrated hybrid fit: turn raw cosine similarity into a fit score + a tier +
human-readable reasons, using the structured résumé profile.

    calibrated = cosine * seniority_factor * education_factor

The factors are the *structured* signals the embedding can't express on its own.
Skill-overlap is computed too, but **for explanation only** — it never enters
`calibrated`, because `job_to_text` and the résumé embedding both already include
the skills section, so scoring lexical overlap on top would double-count and bias
toward keyword-stuffed résumés. It owns the *why*, not the *rank*.

Everything is fail-open: a None/"unknown" profile field yields factor 1.0, so an
unconfident extraction degrades to today's pure-similarity behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

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
class JobFitPartial:
    # Pre-finalization: the score is known but the tier isn't (it depends on the
    # candidate's top score across the result set, which the ranker computes).
    calibrated: float
    reasons: list[str]
    matched_skills: list[str]
    tier_cap: Tier | None  # hard ceiling imposed by a penalty (e.g. "possible")


@dataclass(frozen=True)
class JobFit:
    tier: Tier
    reasons: list[str]
    matched_skills: list[str]


def job_seniority_rank(job: Job) -> SeniorityRank:
    return JOB_RANK[job.seniority_level]


def job_requires_enrollment(job: Job) -> bool:
    # The generator ties intern ↔ internship ↔ "pursuing a degree", so the intern
    # level IS the enrollment requirement. Derived (no schema field) on purpose.
    return job.seniority_level == SeniorityLevel.INTERN


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
    if job_requires_enrollment(job) and profile.education_status == "graduated":
        return (
            0.10,
            "This internship requires current enrollment; your résumé reads as "
            "already graduated.",
            "possible",
        )
    return 1.0, None, None


def skill_overlap(profile_skills: list[str], job: Job) -> list[str]:
    # Explanation-only: which of the job's listed skills literally appear in the
    # résumé. Order follows the job's list for stable display.
    have = {s.lower() for s in profile_skills}
    return [s for s in job.skills if s.lower() in have]


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
            return JobFitPartial(cosine, [], [], None)
        sf, s_reason, s_cap = seniority_factor(profile.seniority, job_seniority_rank(job))
        ef, e_reason, e_cap = education_factor(profile, job)
        matched = skill_overlap(profile.skills, job)
        # Hard/negative reasons first, then the positive skill match.
        reasons = [r for r in (e_reason, s_reason) if r]
        if matched:
            shown = ", ".join(matched[:5]) + ("…" if len(matched) > 5 else "")
            reasons.append(
                f"Matches {len(matched)} of {len(job.skills)} listed skills: {shown}"
            )
        return JobFitPartial(
            calibrated=cosine * sf * ef,
            reasons=reasons,
            matched_skills=matched,
            tier_cap=_min_cap(s_cap, e_cap),
        )

    return rescore


def relative_tier(ratio: float) -> Tier:
    if ratio >= 0.85:
        return "strong"
    if ratio >= 0.65:
        return "good"
    return "possible"


def finalize_fit(partial: JobFitPartial, ratio: float) -> JobFit:
    """Combine the relative tier (score vs. the candidate's best) with any hard cap
    from a penalty, so an over-qualified / ineligible role can't be 'strong' even
    when it tops the filtered list."""
    tier = relative_tier(ratio)
    if partial.tier_cap is not None and _TIER_ORDER[partial.tier_cap] < _TIER_ORDER[tier]:
        tier = partial.tier_cap
    return JobFit(tier=tier, reasons=partial.reasons, matched_skills=partial.matched_skills)
