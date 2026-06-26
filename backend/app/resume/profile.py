"""Structured signal extraction from résumé text.

The matcher's job vectors capture *semantic* fit; this module adds the *structured*
signals an embedding can't express on its own — seniority, tenure, and education
status — so the fit layer (app/matching/fit.py) can penalize a VP→intern or a
graduated→enrollment-required mismatch and explain why.

Design rule: **fail-open**. Every field defaults to None/"unknown"; the heuristic
only reports a signal it can see explicitly. Anything uncertain stays blank and the
fit layer applies no penalty — so an arbitrary uploaded résumé never gets worse
results than it would under pure similarity. The deterministic HeuristicExtractor
is the shipped/test path; LlmExtractor (same Protocol) is the documented swap.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Any, Literal, Protocol

from app.generator import skill_vocabulary
from app.storage.models import SeniorityLevel


class SeniorityRank(IntEnum):
    # Candidate-side scale. Jobs only reach STAFF; EXECUTIVE exists so an
    # over-qualified résumé (VP / Director) sits a measurable distance ABOVE the
    # most senior posting — distance the fit penalty turns into a low score.
    INTERN = 0
    ENTRY = 1
    MID = 2
    SENIOR = 3
    STAFF = 4
    EXECUTIVE = 5


# Job seniority enum → rank. Used by the fit layer to measure candidate↔job distance.
JOB_RANK: dict[SeniorityLevel, SeniorityRank] = {
    SeniorityLevel.INTERN: SeniorityRank.INTERN,
    SeniorityLevel.ENTRY: SeniorityRank.ENTRY,
    SeniorityLevel.MID: SeniorityRank.MID,
    SeniorityLevel.SENIOR: SeniorityRank.SENIOR,
    SeniorityLevel.STAFF: SeniorityRank.STAFF,
}

EducationStatus = Literal["graduated", "in_progress", "unknown"]


@dataclass(frozen=True)
class ResumeProfile:
    seniority: SeniorityRank | None = None
    total_years: float | None = None
    education_status: EducationStatus = "unknown"
    grad_year: int | None = None
    skills: list[str] = field(default_factory=list)


class Extractor(Protocol):
    def extract(self, text: str) -> ResumeProfile: ...


# Title keywords → rank. We take the MAX matching rank across the whole résumé (a
# person's seniority is their highest / most-recent title), so a VP whose history
# also lists "Senior Engineer" reads as EXECUTIVE. Lists are deliberately
# conservative — bare "Manager" is excluded (Product/Program/Account Manager are IC
# titles) so we don't falsely promote. No match → None (fail-open).
_SENIORITY_KEYWORDS: list[tuple[SeniorityRank, tuple[str, ...]]] = [
    (SeniorityRank.EXECUTIVE, (
        "chief", "cto", "ceo", "cfo", "coo", "cmo", "cpo",
        "vp", "vice president", "svp", "evp", "head of", "director",
    )),
    (SeniorityRank.STAFF, (
        "staff", "principal", "distinguished", "tech lead", "team lead",
        "lead engineer", "engineering manager", "senior manager",
    )),
    (SeniorityRank.SENIOR, ("senior", "sr.")),
    # "Junior" reads as MID, not entry: a résumé that states a "Junior X" title means
    # the person climbed the ladder into that role. Entry-level candidates typically
    # list the bare title (no prefix), so entry signals are explicit ("entry-level",
    # "new grad", "associate", "apprentice").
    (SeniorityRank.MID, ("junior", "jr.", "mid-level", "mid level")),
    (SeniorityRank.ENTRY, (
        "associate", "new grad", "entry-level", "apprentice",
    )),
    (SeniorityRank.INTERN, ("intern", "internship", "trainee", "co-op")),
]

_EDU_IN_PROGRESS = (
    "pursuing", "in progress", "current student", "candidate for",
    "expected to graduate", "expected graduation",
)
_DEGREE_TERMS = (
    "b.s.", "b.a.", "b.sc", "m.s.", "m.a.", "m.sc", "mba", "ph.d", "phd",
    "bachelor", "master", "doctorate", "undergraduate",
)

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_YEARS_OF_EXP = re.compile(
    r"(\d{1,2})\s*\+?\s*years?(?:\s+of)?\s+(?:experience|exp\b|industry)",
    re.IGNORECASE,
)
_EXPECTED_YEAR = re.compile(
    r"(?:expected|anticipated)(?:\s+graduation)?[^0-9]{0,20}((?:19|20)\d{2})",
    re.IGNORECASE,
)


def _matches(text: str, term: str) -> bool:
    # Word-boundary, case-insensitive containment that won't fire "Go" inside
    # "Google" or "senior" inside "Seniority". Multi-word terms tolerate runs of
    # whitespace; punctuated skills ("CI/CD", "A/B Testing") are matched literally.
    pattern = (
        r"(?<![A-Za-z0-9])" + re.escape(term).replace(" ", r"\s+") + r"(?![A-Za-z0-9])"
    )
    return re.search(pattern, text, re.IGNORECASE) is not None


class HeuristicExtractor:
    """Deterministic, dependency-free extractor (the shipped/test path). `today`
    is injectable so education status (expected vs. past graduation) is testable."""

    def __init__(self, today: date | None = None) -> None:
        self._today = today or date.today()
        self._skills = skill_vocabulary()

    def extract(self, text: str) -> ResumeProfile:
        seniority = self._seniority(text)
        years = self._years(text)
        if seniority is None and years is not None:
            # No title keyword, but tenure is stated → conservative rank from
            # years, capped at SENIOR (never infer STAFF/EXEC from years alone).
            seniority = (
                SeniorityRank.ENTRY
                if years < 2
                else SeniorityRank.MID
                if years < 5
                else SeniorityRank.SENIOR
            )
        status, grad_year = self._education(text)
        return ResumeProfile(
            seniority=seniority,
            total_years=years,
            education_status=status,
            grad_year=grad_year,
            skills=sorted(s for s in self._skills if _matches(text, s)),
        )

    def _seniority(self, text: str) -> SeniorityRank | None:
        best: SeniorityRank | None = None
        for rank, terms in _SENIORITY_KEYWORDS:
            if any(_matches(text, t) for t in terms) and (best is None or rank > best):
                best = rank
        return best

    def _years(self, text: str) -> float | None:
        nums = [int(m.group(1)) for m in _YEARS_OF_EXP.finditer(text)]
        plausible = [n for n in nums if 0 < n <= 50]
        return float(max(plausible)) if plausible else None

    def _education(self, text: str) -> tuple[EducationStatus, int | None]:
        has_degree = any(_matches(text, d) for d in _DEGREE_TERMS)
        m = _EXPECTED_YEAR.search(text)
        expected = int(m.group(1)) if m else None
        # An "expected" year at/after the current year clearly means not-yet-done.
        if expected is not None and expected >= self._today.year:
            return "in_progress", expected
        if any(_matches(text, k) for k in _EDU_IN_PROGRESS) and (
            has_degree or expected is not None
        ):
            return "in_progress", expected
        if has_degree:
            years = [int(y.group(0)) for y in _YEAR.finditer(text)]
            past = [y for y in years if 1980 <= y <= self._today.year]
            if past:
                return "graduated", max(past)
        return "unknown", None


# String → rank, for parsing an LLM's structured output back into the scale.
_RANK_BY_NAME: dict[str, SeniorityRank] = {r.name.lower(): r for r in SeniorityRank}

_LLM_PROMPT = (
    "Extract structured fields from the résumé text. Return ONLY a JSON object with "
    "keys: seniority (one of intern|entry|mid|senior|staff|executive, by the "
    "person's highest/most-recent role, or null), total_years (number or null), "
    "education_status (graduated|in_progress|unknown — in_progress if a degree is "
    "expected/ongoing relative to the current year {year}), grad_year (int or null), "
    "skills (array of skill strings). No prose, no code fences."
)


class LlmExtractor:
    """Claude-backed extractor behind the same Protocol — the robust production
    path for messy real résumés. It is selected only when ANTHROPIC_API_KEY is set
    (see select_extractor); otherwise the deterministic heuristic runs. The real
    Anthropic client is imported lazily so neither tests nor a keyless deploy need
    the SDK. Parsing is fail-open: any malformed response yields an empty profile.
    """

    def __init__(
        self,
        client: Any = None,
        model: str = "claude-haiku-4-5-20251001",
        today: date | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._today = today or date.today()

    def extract(self, text: str) -> ResumeProfile:
        client = self._client or self._default_client()
        resp = client.messages.create(
            model=self._model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": f"{_LLM_PROMPT.format(year=self._today.year)}\n\n{text}",
                }
            ],
        )
        return self._to_profile(resp.content[0].text)

    def _default_client(self) -> Any:  # pragma: no cover - needs the SDK + a key
        import anthropic

        return anthropic.Anthropic()

    def _to_profile(self, raw: str) -> ResumeProfile:
        try:
            data = json.loads(raw)
            status = data.get("education_status")
            years = data.get("total_years")
            return ResumeProfile(
                seniority=_RANK_BY_NAME.get(str(data.get("seniority")).lower()),
                total_years=float(years) if years is not None else None,
                education_status=(
                    status if status in ("graduated", "in_progress") else "unknown"
                ),
                grad_year=data.get("grad_year"),
                skills=[str(s) for s in data.get("skills") or []],
            )
        except (ValueError, TypeError, AttributeError):
            return ResumeProfile()  # fail-open on any malformed output


def profile_to_json(p: ResumeProfile) -> str:
    return json.dumps(
        {
            "seniority": int(p.seniority) if p.seniority is not None else None,
            "total_years": p.total_years,
            "education_status": p.education_status,
            "grad_year": p.grad_year,
            "skills": p.skills,
        }
    )


def profile_from_json(raw: str | None) -> ResumeProfile | None:
    if not raw:
        return None
    d = json.loads(raw)
    s = d.get("seniority")
    return ResumeProfile(
        seniority=SeniorityRank(s) if s is not None else None,
        total_years=d.get("total_years"),
        education_status=d.get("education_status") or "unknown",
        grad_year=d.get("grad_year"),
        skills=d.get("skills") or [],
    )


def select_extractor(today: date | None = None) -> Extractor:
    """The deployed/test path is HeuristicExtractor; LlmExtractor is used only when
    an API key is present (the user does not set one, so it stays dormant). Mirrors
    the JobIndex / Embedder swap-seams: same Protocol, swapped implementation."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LlmExtractor(today=today)
    return HeuristicExtractor(today=today)
