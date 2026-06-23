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
    min_years_exp: int
    city: str
    state_region: str
    country: str
    work_mode: WorkMode
    skills: list[str]
    description: str


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
