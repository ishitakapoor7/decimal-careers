from pydantic import BaseModel


class FitOut(BaseModel):
    # Calibrated fit, present only on the personalized /jobs path. The raw score is
    # deliberately NOT exposed (avoids false precision); the frontend renders the
    # tier + reasons. matched_skills powers the positive "matches these skills" chip
    # (explanation-only — skill overlap is not part of the score).
    tier: str
    reasons: list[str] = []
    matched_skills: list[str] = []


class JobOut(BaseModel):
    id: str
    title: str
    team: str
    employment_type: str
    seniority_level: str
    city: str
    state_region: str
    country: str
    work_mode: str
    skills: list[str]
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
    # Populated only on the personalized path (a candidate with a parsed résumé).
    fit: FitOut | None = None


class JobsPage(BaseModel):
    items: list[JobOut]
    total: int
    limit: int
    offset: int


class ApplicationOut(BaseModel):
    id: str
    candidate_id: str
    job_id: str
    status: str
    created_at: str
    name: str = ""
    email: str = ""
    earliest_start: str = ""
    linkedin: str = ""
    github: str = ""
    other_links: list[str] = []
    requires_visa: bool = False
    why_company: str = ""
    resume_name: str = ""


class ApplyRequest(BaseModel):
    candidate_id: str
    job_id: str
    # Apply-form inputs. name + email are required (a real application needs a
    # person to reach); the rest are optional.
    name: str
    email: str
    earliest_start: str = ""
    linkedin: str = ""
    github: str = ""
    other_links: list[str] = []
    requires_visa: bool = False
    why_company: str = ""
    # Filename of the résumé submitted with this application (record only).
    resume_name: str = ""


class SaveRequest(BaseModel):
    candidate_id: str
    job_id: str
