from concurrent.futures import ThreadPoolExecutor

from app.storage.db import Database, JobFilters
from app.storage.models import (
    Application,
    Candidate,
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


def make_job(jid: str, team: Team, level: SeniorityLevel, mode: WorkMode) -> Job:
    return Job(
        id=jid,
        title=f"{team.value} role",
        team=team,
        employment_type=EmploymentType.FULL_TIME,
        seniority_level=level,
        city="New York",
        state_region="NY",
        country="USA",
        work_mode=mode,
        skills=["Python"],
        company="Acme",
        company_about="Acme builds things.",
        summary="role summary",
        about_role="role summary. You'll do great work.",
        responsibilities=["Build things.", "Ship things."],
        required_quals=["You have 3+ years of experience.", "You know Python."],
        preferred_quals=["Bonus points if you've worked with SQL."],
        benefits=["Competitive salary.", "Good health insurance."],
        salary_min=100_000,
        salary_max=130_000,
        posted_date="2026-06-01",
    )


def test_insert_and_get_job_roundtrips():
    db = Database()
    db.init_schema()
    job = make_job("j1", Team.ENGINEERING, SeniorityLevel.MID, WorkMode.REMOTE)
    db.insert_jobs([job])
    fetched = db.get_job("j1")
    assert fetched == job
    assert db.get_job("missing") is None


def test_query_jobs_filters_and_paginates():
    db = Database()
    db.init_schema()
    db.insert_jobs(
        [
            make_job("j1", Team.ENGINEERING, SeniorityLevel.MID, WorkMode.REMOTE),
            make_job("j2", Team.MARKETING, SeniorityLevel.MID, WorkMode.REMOTE),
            make_job("j3", Team.ENGINEERING, SeniorityLevel.SENIOR, WorkMode.ONSITE),
        ]
    )
    page, total = db.query_jobs(
        JobFilters(teams=[Team.ENGINEERING]), limit=1, offset=0
    )
    assert total == 2
    assert len(page) == 1 and page[0].team == Team.ENGINEERING


def test_job_ids_matching_returns_set():
    db = Database()
    db.init_schema()
    db.insert_jobs(
        [
            make_job("j1", Team.ENGINEERING, SeniorityLevel.MID, WorkMode.REMOTE),
            make_job("j2", Team.MARKETING, SeniorityLevel.MID, WorkMode.REMOTE),
        ]
    )
    ids = db.job_ids_matching(JobFilters(work_modes=[WorkMode.REMOTE]))
    assert ids == {"j1", "j2"}


def test_all_jobs_returns_every_inserted_job():
    db = Database()
    db.init_schema()
    db.insert_jobs(
        [
            make_job("j2", Team.MARKETING, SeniorityLevel.SENIOR, WorkMode.ONSITE),
            make_job("j1", Team.ENGINEERING, SeniorityLevel.MID, WorkMode.REMOTE),
        ]
    )
    got = db.all_jobs()
    assert {j.id for j in got} == {"j1", "j2"}
    # full Job objects round-trip, not just ids
    assert db.get_job("j1") in got and db.get_job("j2") in got


def test_count_jobs_reflects_inserts():
    db = Database()
    db.init_schema()
    assert db.count_jobs() == 0
    db.insert_jobs(
        [make_job("j1", Team.ENGINEERING, SeniorityLevel.MID, WorkMode.REMOTE)]
    )
    assert db.count_jobs() == 1


def test_application_roundtrip():
    db = Database()
    db.init_schema()
    db.insert_candidate(Candidate(id="c1", resume_text="resume", created_at="t"))
    db.insert_application(
        Application(
            id="a1", candidate_id="c1", job_id="j1", status="applied", created_at="t"
        )
    )
    apps = db.list_applications("c1")
    assert len(apps) == 1 and apps[0].job_id == "j1"


def test_concurrent_writes_are_serialized():
    # The threadpool mirrors how FastAPI runs sync endpoints: many threads
    # share one connection. The lock must keep every write intact.
    db = Database()
    db.init_schema()
    db.insert_candidate(Candidate(id="c1", resume_text="r", created_at="t"))
    workers, per_worker = 8, 50

    def write(worker: int) -> None:
        for i in range(per_worker):
            db.insert_application(
                Application(
                    id=f"a-{worker}-{i}",
                    candidate_id="c1",
                    job_id="j1",
                    status="applied",
                    created_at="t",
                )
            )
            db.list_applications("c1")  # concurrent reads alongside writes

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(write, range(workers)))

    assert len(db.list_applications("c1")) == workers * per_worker
