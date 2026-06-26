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
        company="Acme",
        company_about="Acme builds developer tools.",
        summary="Build APIs as a backend engineer.",
        about_role="Build APIs as a backend engineer. You'll own services end-to-end.",
        responsibilities=["Design and build services.", "Review pull requests."],
        required_quals=["You have 3+ years of experience.", "You're proficient in Python and Postgres."],
        preferred_quals=["Bonus points if you've worked with Kubernetes."],
        benefits=["Competitive salary and equity.", "Comprehensive health coverage."],
        salary_min=120_000,
        salary_max=160_000,
        posted_date="2026-06-01",
    )
    assert job.team.value == "engineering"
    assert job.work_mode.value == "hybrid"
    assert job.skills == ["Python", "Postgres"]
