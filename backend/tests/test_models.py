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
        min_years_exp=3,
        city="New York",
        state_region="NY",
        country="USA",
        work_mode=WorkMode.HYBRID,
        skills=["Python", "Postgres"],
        description="Build APIs.",
    )
    assert job.team.value == "engineering"
    assert job.work_mode.value == "hybrid"
    assert job.skills == ["Python", "Postgres"]
