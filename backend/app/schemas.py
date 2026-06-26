from pydantic import BaseModel


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


class ApplyRequest(BaseModel):
    candidate_id: str
    job_id: str
