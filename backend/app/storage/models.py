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
    # Only `summary` (+ `skills`) is embedded via job_to_text; the rest is display-only
    # prose the frontend styles section-by-section.
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


@dataclass(frozen=True)
class Candidate:
    id: str
    resume_text: str
    created_at: str
    # Resume embedding as raw float32 bytes, reused across pagination/re-rank. None for
    # candidates predating the column or with no extractable text.
    resume_vector: bytes | None = None
    # Structured profile (seniority/education/skills/domain) as JSON, driving the fit
    # score. None for candidates predating the column.
    profile: str | None = None


@dataclass(frozen=True)
class Application:
    id: str
    candidate_id: str
    job_id: str
    status: str
    created_at: str
    # Apply-form inputs. Optional with defaults so older rows and tests still construct.
    name: str = ""
    email: str = ""
    earliest_start: str = ""  # e.g. "2026-08"
    linkedin: str = ""
    github: str = ""
    other_links: list[str] = field(default_factory=list)
    requires_visa: bool = False
    why_company: str = ""
    resume_name: str = ""  # what they applied with; not parsed or embedded


@dataclass(frozen=True)
class SavedJob:
    # A bookmark. PK is (candidate_id, job_id) so saving is idempotent.
    candidate_id: str
    job_id: str
    created_at: str
