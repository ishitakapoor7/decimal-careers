from dataclasses import dataclass
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


@dataclass(frozen=True)
class Candidate:
    id: str
    resume_text: str
    created_at: str
    # Resume embedding, persisted as raw float32 bytes so pagination/re-rank
    # reuses it instead of re-running the model on every request. Optional:
    # candidates predating this column (or with no extractable text) have None.
    resume_vector: bytes | None = None


@dataclass(frozen=True)
class Application:
    id: str
    candidate_id: str
    job_id: str
    status: str
    created_at: str
