from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


def test_job_constructs_with_enum_values():
    job = Job(
        id="j1",
        title="Backend Engineer",
        team=Team.ENGINEERING,
        employment_type=EmploymentType.FULL_TIME,
        seniority_level=SeniorityLevel.MID,
        city="New York",
        state_region="NY",
        country="USA",
        work_mode=WorkMode.HYBRID,
        skills=["Python", "Postgres"],
        description="Build APIs.",
        company="Acme",
        summary="Build APIs as a backend engineer.",
        salary_min=120_000,
        salary_max=160_000,
        posted_date="2026-06-01",
    )
    assert job.team.value == "engineering"
    assert job.work_mode.value == "hybrid"
    assert job.skills == ["Python", "Postgres"]
