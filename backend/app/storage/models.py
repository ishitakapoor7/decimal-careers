from dataclasses import dataclass, field
from enum import Enum


class Team(str, Enum):
    ENGINEERING = "engineering"
    SALES = "sales"
    PRODUCT = "product"
    MARKETING = "marketing"
    DESIGN = "design"
    FINANCE = "finance"
    OPERATIONS = "operations"


class EmploymentType(str, Enum):
    FULL_TIME = "full_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"


class WorkMode(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    team: Team
    employment_type: EmploymentType
    seniority_level: SeniorityLevel
    city: str
    state_region: str
    country: str
    work_mode: WorkMode
    skills: list[str]
    # Display + signal fields. `summary` is the ONLY generated text that is
    # embedded (via job_to_text); `skills` also feeds the vector. Everything else
    # here is display-only prose the frontend styles section-by-section — see the
    # prose-qualifications design note. Qualifications are full sentences, not
    # bare skill words, so the JD reads like a real posting.
    company: str
    company_about: str
    summary: str
    about_role: str
    responsibilities: list[str]
    required_quals: list[str]
    preferred_quals: list[str]
    benefits: list[str]
    salary_min: int
    salary_max: int
    posted_date: str
    # Subset of `skills` that are must-haves (the remainder are nice-to-haves). Lets
    # the fit layer report required-skill matches distinctly from preferred ones, so a
    # candidate hitting only nice-to-haves isn't shown the same overlap as one hitting
    # the must-haves. Defaults empty for rows/tests predating the column.
    required_skills: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    id: str
    resume_text: str
    created_at: str
    # Resume embedding, persisted as raw float32 bytes so pagination/re-rank
    # reuses it instead of re-running the model on every request. Optional:
    # candidates predating this column (or with no extractable text) have None.
    resume_vector: bytes | None = None
    # Structured signal extracted from the résumé (seniority/education/skills),
    # serialized as JSON. Extracted once at upload and reused on every /jobs call
    # to drive the calibrated fit score. None for candidates predating the column.
    profile: str | None = None


@dataclass(frozen=True)
class Application:
    id: str
    candidate_id: str
    job_id: str
    status: str
    created_at: str
    # Apply-form inputs (the Ashby-style drawer). Optional with defaults so older
    # rows and tests that omit them still construct. The résumé itself is NOT
    # duplicated here — it lives on the candidate, linked via candidate_id.
    name: str = ""
    email: str = ""
    earliest_start: str = ""  # e.g. "2026-08"
    linkedin: str = ""
    github: str = ""
    other_links: list[str] = field(default_factory=list)
    requires_visa: bool = False
    why_company: str = ""
    # Filename of the résumé this application was submitted with. A record only
    # (what they applied with) — the file is not parsed or embedded here, and an
    # application-specific résumé never alters the candidate's ranking résumé.
    resume_name: str = ""


@dataclass(frozen=True)
class SavedJob:
    # A bookmark: a candidate's saved job. Tiny store — no body, just the link
    # and when it was saved. PK is (candidate_id, job_id) so saving is idempotent.
    candidate_id: str
    job_id: str
    created_at: str
