"""Structured signal extraction from resume text"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from enum import IntEnum
from typing import Any, Literal, Protocol

from app.generator import skill_vocabulary, skills_by_team
from app.storage.models import SeniorityLevel, Team


class SeniorityRank(IntEnum):
    INTERN = 0
    ENTRY = 1
    MID = 2
    SENIOR = 3
    STAFF = 4
    EXECUTIVE = 5


# Job seniority enum maps rank. Used by the fit layer to measure candidate-job distance.
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
    # Inferred domain (which team the resume's skills belong to), or None when the
    # skill signal is too thin/ambiguous to be confident. 
    domain: Team | None = None


class Extractor(Protocol):
    def extract(self, text: str) -> ResumeProfile: ...


# Title keywords maps to rank. Take MAX matching rank across the whole resume (a
# person's experience level is their highest / most-recent title)
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
    (SeniorityRank.MID, ("junior", "jr.", "mid-level", "mid level")),
    (SeniorityRank.ENTRY, (
        "associate", "new grad", "entry-level", "apprentice",
    )),
    (SeniorityRank.INTERN, ("intern", "internship", "trainee", "co-op")),
]

# Bare promoting words that also appear in ordinary prose and falsely inflate seniority. They only count
# when they sit in a TITLE: immediately followed (within ~2 words) by a role noun
_TITLE_CONTEXT_TERMS = frozenset({"senior", "sr.", "staff", "principal", "distinguished"})
_ROLE_NOUNS = (
    "engineer", "engineers", "developer", "scientist", "manager", "analyst",
    "designer", "architect", "consultant", "specialist", "researcher", "lead",
    "director", "accountant", "marketer", "strategist", "administrator",
    "programmer", "technician", "associate", "executive", "officer",
)
_ROLE_NOUN_RE = "|".join(_ROLE_NOUNS)

# Strong early-career markers a working professional would never write.
_EARLY_CAREER = re.compile(
    r"seeking\s+(?:a\s+|an\s+|summer\s+|fall\s+|spring\s+|"
    r"full[-\s]?time\s+|part[-\s]?time\s+)*(?:internship|intern|co-?op)"
    r"|incoming\s+(?:[a-z.&]+\s+){0,4}student"
    r"|rising\s+(?:freshman|sophomore|junior|senior)",
    re.IGNORECASE,
)

# Vocabulary skills that are also common English / generic business words. 
_GENERIC_SKILL_TERMS = frozenset({
    "Activation", "Analytics", "Compliance", "Cross-functional", "Dashboards", "Discovery",
    "Editorial", "Email", "Integrations", "Layout", "Modeling", "Motion",
    "Onboarding", "Planning", "Platform", "Positioning", "Prioritization",
    "Reporting", "Research", "Retention", "Specs", "Storytelling", "Synthesis",
})

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
    # Word-boundary, case-insensitive containment 
    pattern = (
        r"(?<![A-Za-z0-9])" + re.escape(term).replace(" ", r"\s+") + r"(?![A-Za-z0-9])"
    )
    return re.search(pattern, text, re.IGNORECASE) is not None


def _title_context(text: str, term: str) -> bool:
    pattern = (
        r"(?<![A-Za-z0-9])" + re.escape(term).replace(" ", r"\s+")
        + r"(?:\s+[A-Za-z.&/-]+){0,2}\s+(?:" + _ROLE_NOUN_RE + r")(?![A-Za-z])"
    )
    return re.search(pattern, text, re.IGNORECASE) is not None


# skill (lowercased) mapped to teams that list it, built once from the catalog lexicon.
_SKILLS_BY_TEAM: dict[str, set[Team]] = {
    s.lower(): teams for s, teams in skills_by_team().items()
}


class HeuristicExtractor:
    """Deterministic, dependency-free extractor (the shipped/test path)."""

    def __init__(self, today: date | None = None) -> None:
        self._today = today or date.today()
        # Drop generic cross-domain words so a resume is credited only with domain-specific skills
        self._skills = skill_vocabulary() - _GENERIC_SKILL_TERMS

    def extract(self, text: str) -> ResumeProfile:
        seniority = self._seniority(text)
        years = self._years(text)
        if seniority is None and years is not None:
            seniority = (
                SeniorityRank.ENTRY
                if years < 2
                else SeniorityRank.MID
                if years < 5
                else SeniorityRank.SENIOR
            )
        status, grad_year = self._education(text)
        skills = sorted(s for s in self._skills if _matches(text, s))
        return ResumeProfile(
            seniority=seniority,
            total_years=years,
            education_status=status,
            grad_year=grad_year,
            skills=skills,
            domain=self._domain(skills),
        )

    def _seniority(self, text: str) -> SeniorityRank | None:
        best: SeniorityRank | None = None
        for rank, terms in _SENIORITY_KEYWORDS:
            hit = any(
                (_title_context(text, t) if t in _TITLE_CONTEXT_TERMS else _matches(text, t))
                for t in terms
            )
            if hit and (best is None or rank > best):
                best = rank
        if _EARLY_CAREER.search(text):
            if best is None:
                return SeniorityRank.ENTRY
            return min(best, SeniorityRank.ENTRY)
        return best

    def _domain(self, skills: list[str]) -> Team | None:
        # Tally a domain score per team from the resume's skills, weighting each skill
        # by SPECIFICITY (1 / number of teams that list it): PyTorch (engineering-only)
        # counts full, SQL (4 teams) barely counts. Assign a domain only when one team
        # clearly dominates; a thin/ambiguous signal stays None so no penalty (fail-open).
        scores: dict[Team, float] = {}
        for s in skills:
            teams = _SKILLS_BY_TEAM.get(s.lower())
            if not teams:
                continue
            w = 1.0 / len(teams)
            for t in teams:
                scores[t] = scores.get(t, 0.0) + w
        if not scores:
            return None
        ranked = sorted(scores.values(), reverse=True)
        top_team = max(scores, key=scores.__getitem__)
        top = ranked[0]
        runner = ranked[1] if len(ranked) > 1 else 0.0
        # Need real, distinctive evidence (≥2.0 specificity-weighted) and a clear lead
        # over the next team (≥1.5×), else the domain is too uncertain to act on.
        if top >= 2.0 and top >= 1.5 * runner:
            return top_team
        return None

    def _years(self, text: str) -> float | None:
        nums = [int(m.group(1)) for m in _YEARS_OF_EXP.finditer(text)]
        plausible = [n for n in nums if 0 < n <= 50]
        return float(max(plausible)) if plausible else None

    def _education(self, text: str) -> tuple[EducationStatus, int | None]:
        has_degree = any(_matches(text, d) for d in _DEGREE_TERMS)
        m = _EXPECTED_YEAR.search(text)
        expected = int(m.group(1)) if m else None
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


# String mapped to rank, for parsing an LLM's structured output back into the scale.
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
    path for messy real résumés."""

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

    def _default_client(self) -> Any:  
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
            "domain": p.domain.value if p.domain is not None else None,
        }
    )


def profile_from_json(raw: str | None) -> ResumeProfile | None:
    if not raw:
        return None
    d = json.loads(raw)
    s = d.get("seniority")
    dom = d.get("domain")
    return ResumeProfile(
        seniority=SeniorityRank(s) if s is not None else None,
        total_years=d.get("total_years"),
        education_status=d.get("education_status") or "unknown",
        grad_year=d.get("grad_year"),
        skills=d.get("skills") or [],
        # Tolerate profiles stored before this field existed (→ None, fail-open).
        domain=Team(dom) if dom is not None else None,
    )


def select_extractor(today: date | None = None) -> Extractor:
    """The deployed/test path is HeuristicExtractor; LlmExtractor is used only when
    an API key is present """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return LlmExtractor(today=today)
    return HeuristicExtractor(today=today)
