import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile

from app.resume.parser import parse_resume
from app.schemas import ApplicationOut, ApplyRequest, JobOut, JobsPage
from app.state import AppState
from app.storage.db import JobFilters
from app.storage.models import (
    Application,
    Candidate,
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)

_state: AppState | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the singleton app state once, before the server accepts traffic.

    Startup runs single-threaded, so there is no initialization race: by the
    time any threadpool worker handles a request, _state is fully built.

    CAREER_DB_PATH points at a file so uploaded resumes and applications
    survive a restart; it defaults to ":memory:" for ephemeral local runs.
    """
    global _state
    _state = AppState.seeded(db_path=os.environ.get("CAREER_DB_PATH", ":memory:"))
    yield


app = FastAPI(title="Personalized Career Site API", lifespan=lifespan)


def get_state() -> AppState:
    if _state is None:
        raise RuntimeError("app state not initialized; lifespan did not run")
    return _state


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        team=job.team.value,
        employment_type=job.employment_type.value,
        seniority_level=job.seniority_level.value,
        min_years_exp=job.min_years_exp,
        city=job.city,
        state_region=job.state_region,
        country=job.country,
        work_mode=job.work_mode.value,
        skills=job.skills,
        description=job.description,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/jobs", response_model=JobsPage)
def list_jobs(
    state: AppState = Depends(get_state),
    team: list[Team] | None = Query(default=None),
    seniority_level: list[SeniorityLevel] | None = Query(default=None),
    employment_type: list[EmploymentType] | None = Query(default=None),
    work_mode: list[WorkMode] | None = Query(default=None),
    city: str | None = None,
    state_region: str | None = None,
    country: str | None = None,
    candidate_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> JobsPage:
    filters = JobFilters(
        teams=team,
        seniority_levels=seniority_level,
        employment_types=employment_type,
        work_modes=work_mode,
        city=city,
        state_region=state_region,
        country=country,
    )
    candidate = state.db.get_candidate(candidate_id) if candidate_id else None
    if candidate and candidate.resume_text:
        allowed = state.db.job_ids_matching(filters)
        query = state.embedder.encode([candidate.resume_text])[0]
        ids, total = state.ranker.rank_ids(query, allowed, limit, offset)
        items = [_to_out(job) for i in ids if (job := state.db.get_job(i))]
        return JobsPage(items=items, total=total, limit=limit, offset=offset)
    jobs, total = state.db.query_jobs(filters, limit, offset)
    return JobsPage(
        items=[_to_out(j) for j in jobs], total=total, limit=limit, offset=offset
    )


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, state: AppState = Depends(get_state)) -> JobOut:
    job = state.db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_out(job)


@app.post("/upload-resume")
def upload_resume(
    file: UploadFile = File(...),
    candidate_id: str | None = Form(default=None),
    state: AppState = Depends(get_state),
) -> dict[str, object]:
    data = file.file.read()
    try:
        text = parse_resume(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    # Mint an opaque ID on first upload; reuse the client's stored one when a
    # returning candidate replaces their resume. Pseudonymous, not authenticated.
    cid = candidate_id or str(uuid.uuid4())
    state.db.insert_candidate(
        Candidate(id=cid, resume_text=text, created_at=_now())
    )
    return {"candidate_id": cid, "char_count": len(text)}


@app.post("/apply", response_model=ApplicationOut)
def apply(req: ApplyRequest, state: AppState = Depends(get_state)) -> ApplicationOut:
    if state.db.get_job(req.job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    application = Application(
        id=str(uuid.uuid4()),
        candidate_id=req.candidate_id,
        job_id=req.job_id,
        status="applied",
        created_at=_now(),
    )
    state.db.insert_application(application)
    return ApplicationOut(**application.__dict__)


@app.get("/applications")
def list_applications(
    candidate_id: str, state: AppState = Depends(get_state)
) -> dict[str, list]:
    apps = state.db.list_applications(candidate_id)
    return {"items": [ApplicationOut(**a.__dict__).model_dump() for a in apps]}
