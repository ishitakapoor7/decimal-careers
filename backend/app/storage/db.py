import json
import sqlite3
import threading
from dataclasses import dataclass

from app.storage.models import (
    Application,
    Candidate,
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


@dataclass
class JobFilters:
    teams: list[Team] | None = None
    seniority_levels: list[SeniorityLevel] | None = None
    employment_types: list[EmploymentType] | None = None
    work_modes: list[WorkMode] | None = None
    city: str | None = None
    state_region: str | None = None
    country: str | None = None


class Database:
    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False lets the threadpool workers share one
        # connection; self._lock serializes access so only one thread is ever
        # inside the connection at a time (SQLite is a single-writer store).
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, title TEXT, team TEXT, employment_type TEXT,
                    seniority_level TEXT, min_years_exp INTEGER, city TEXT,
                    state_region TEXT, country TEXT, work_mode TEXT,
                    skills TEXT, description TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_team ON jobs(team);
                CREATE INDEX IF NOT EXISTS idx_jobs_level ON jobs(seniority_level);
                CREATE INDEX IF NOT EXISTS idx_jobs_mode ON jobs(work_mode);
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, resume_text TEXT, created_at TEXT
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY, candidate_id TEXT, job_id TEXT,
                    status TEXT, created_at TEXT
                );
                """
            )
            self._conn.commit()

    def insert_jobs(self, jobs: list[Job]) -> None:
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        j.id,
                        j.title,
                        j.team.value,
                        j.employment_type.value,
                        j.seniority_level.value,
                        j.min_years_exp,
                        j.city,
                        j.state_region,
                        j.country,
                        j.work_mode.value,
                        json.dumps(j.skills),
                        j.description,
                    )
                    for j in jobs
                ],
            )
            self._conn.commit()

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            title=row["title"],
            team=Team(row["team"]),
            employment_type=EmploymentType(row["employment_type"]),
            seniority_level=SeniorityLevel(row["seniority_level"]),
            min_years_exp=row["min_years_exp"],
            city=row["city"],
            state_region=row["state_region"],
            country=row["country"],
            work_mode=WorkMode(row["work_mode"]),
            skills=json.loads(row["skills"]),
            description=row["description"],
        )

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        return self._row_to_job(row) if row else None

    def _where(self, f: JobFilters) -> tuple[str, list]:
        clauses: list[str] = []
        params: list = []

        def in_clause(col: str, values: list) -> None:
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{col} IN ({placeholders})")
            params.extend(v.value for v in values)

        if f.teams:
            in_clause("team", f.teams)
        if f.seniority_levels:
            in_clause("seniority_level", f.seniority_levels)
        if f.employment_types:
            in_clause("employment_type", f.employment_types)
        if f.work_modes:
            in_clause("work_mode", f.work_modes)
        for col, val in (
            ("city", f.city),
            ("state_region", f.state_region),
            ("country", f.country),
        ):
            if val:
                clauses.append(f"{col} = ?")
                params.append(val)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return where, params

    def query_jobs(
        self, filters: JobFilters, limit: int, offset: int
    ) -> tuple[list[Job], int]:
        where, params = self._where(filters)
        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) AS n FROM jobs{where}", params
            ).fetchone()["n"]
            rows = self._conn.execute(
                f"SELECT * FROM jobs{where} ORDER BY id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [self._row_to_job(r) for r in rows], total

    def job_ids_matching(self, filters: JobFilters) -> set[str]:
        where, params = self._where(filters)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id FROM jobs{where}", params
            ).fetchall()
        return {r["id"] for r in rows}

    def insert_candidate(self, c: Candidate) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO candidates VALUES (?,?,?)",
                (c.id, c.resume_text, c.created_at),
            )
            self._conn.commit()

    def get_candidate(self, cid: str) -> Candidate | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (cid,)
            ).fetchone()
        return (
            Candidate(
                id=row["id"],
                resume_text=row["resume_text"],
                created_at=row["created_at"],
            )
            if row
            else None
        )

    def insert_application(self, a: Application) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO applications VALUES (?,?,?,?,?)",
                (a.id, a.candidate_id, a.job_id, a.status, a.created_at),
            )
            self._conn.commit()

    def list_applications(self, candidate_id: str) -> list[Application]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM applications WHERE candidate_id = ? "
                "ORDER BY created_at",
                (candidate_id,),
            ).fetchall()
        return [
            Application(
                id=r["id"],
                candidate_id=r["candidate_id"],
                job_id=r["job_id"],
                status=r["status"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
