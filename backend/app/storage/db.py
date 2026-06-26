import json
import sqlite3
import threading
from dataclasses import dataclass

from app.storage.models import (
    Application,
    Candidate,
    EmploymentType,
    Job,
    SavedJob,
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
        # WAL lets readers proceed without blocking on a writer (and vice versa),
        # both across threads in this process and across separate OS processes if
        # the app is ever run with multiple worker processes against the same
        # file. Without it, SQLite's default rollback-journal mode takes a
        # whole-file lock for writes, which can surface as "database is locked"
        # under concurrent traffic. No-op for ":memory:" (no separate file to
        # apply WAL to), harmless to set unconditionally.
        self._conn.execute("PRAGMA journal_mode=WAL")

    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, title TEXT, team TEXT, employment_type TEXT,
                    seniority_level TEXT, city TEXT,
                    state_region TEXT, country TEXT, work_mode TEXT,
                    skills TEXT, company TEXT, company_about TEXT,
                    summary TEXT, about_role TEXT, responsibilities TEXT,
                    required_quals TEXT, preferred_quals TEXT, benefits TEXT,
                    salary_min INTEGER, salary_max INTEGER, posted_date TEXT,
                    required_skills TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_team ON jobs(team);
                CREATE INDEX IF NOT EXISTS idx_jobs_level ON jobs(seniority_level);
                CREATE INDEX IF NOT EXISTS idx_jobs_mode ON jobs(work_mode);
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, resume_text TEXT, created_at TEXT,
                    resume_vector BLOB, profile TEXT
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY, candidate_id TEXT, job_id TEXT,
                    status TEXT, created_at TEXT,
                    name TEXT, email TEXT, earliest_start TEXT,
                    linkedin TEXT, github TEXT, other_links TEXT,
                    requires_visa INTEGER, why_company TEXT, resume_name TEXT
                );
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    candidate_id TEXT, job_id TEXT, created_at TEXT,
                    PRIMARY KEY (candidate_id, job_id)
                );
                """
            )
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        # CREATE TABLE IF NOT EXISTS never alters an existing table, so columns
        # added after a DB file was first created must be backfilled here.
        # Each entry is idempotent: add the column only when it's absent.
        additions = {
            "applications": [("resume_name", "TEXT")],
            "candidates": [("resume_vector", "BLOB"), ("profile", "TEXT")],
            "jobs": [("required_skills", "TEXT")],
        }
        for table, columns in additions.items():
            existing = {
                row["name"]
                for row in self._conn.execute(f"PRAGMA table_info({table})")
            }
            for name, decl in columns:
                if name not in existing:
                    self._conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {decl}"
                    )

    def insert_jobs(self, jobs: list[Job]) -> None:
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO jobs VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        j.id,
                        j.title,
                        j.team.value,
                        j.employment_type.value,
                        j.seniority_level.value,
                        j.city,
                        j.state_region,
                        j.country,
                        j.work_mode.value,
                        json.dumps(j.skills),
                        j.company,
                        j.company_about,
                        j.summary,
                        j.about_role,
                        json.dumps(j.responsibilities),
                        json.dumps(j.required_quals),
                        json.dumps(j.preferred_quals),
                        json.dumps(j.benefits),
                        j.salary_min,
                        j.salary_max,
                        j.posted_date,
                        json.dumps(j.required_skills),
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
            city=row["city"],
            state_region=row["state_region"],
            country=row["country"],
            work_mode=WorkMode(row["work_mode"]),
            skills=json.loads(row["skills"]),
            company=row["company"],
            company_about=row["company_about"],
            summary=row["summary"],
            about_role=row["about_role"],
            responsibilities=json.loads(row["responsibilities"]),
            required_quals=json.loads(row["required_quals"]),
            preferred_quals=json.loads(row["preferred_quals"]),
            benefits=json.loads(row["benefits"]),
            salary_min=row["salary_min"],
            salary_max=row["salary_max"],
            posted_date=row["posted_date"],
            # NULL for rows written before the column existed → no required/preferred
            # split (skill_overlap then treats all matches as preferred).
            required_skills=(
                json.loads(row["required_skills"]) if row["required_skills"] else []
            ),
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

    def all_jobs(self) -> list[Job]:
        # Whole catalog, id-ordered for determinism. Feeds the boot-time index
        # build so the index always mirrors the persisted DB (caveat §0).
        with self._lock:
            rows = self._conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        return [self._row_to_job(r) for r in rows]

    def count_jobs(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) AS n FROM jobs"
            ).fetchone()["n"]

    def insert_candidate(self, c: Candidate) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO candidates "
                "(id, resume_text, created_at, resume_vector, profile) "
                "VALUES (?,?,?,?,?)",
                (c.id, c.resume_text, c.created_at, c.resume_vector, c.profile),
            )
            self._conn.commit()

    def get_candidate(self, cid: str) -> Candidate | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM candidates WHERE id = ?", (cid,)
            ).fetchone()
        if row is None:
            return None
        keys = row.keys()
        return Candidate(
            id=row["id"],
            resume_text=row["resume_text"],
            created_at=row["created_at"],
            resume_vector=row["resume_vector"],
            profile=row["profile"] if "profile" in keys else None,
        )

    def insert_application(self, a: Application) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO applications (id, candidate_id, job_id, "
                "status, created_at, name, email, earliest_start, linkedin, "
                "github, other_links, requires_visa, why_company, resume_name) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    a.id,
                    a.candidate_id,
                    a.job_id,
                    a.status,
                    a.created_at,
                    a.name,
                    a.email,
                    a.earliest_start,
                    a.linkedin,
                    a.github,
                    json.dumps(a.other_links),
                    int(a.requires_visa),
                    a.why_company,
                    a.resume_name,
                ),
            )
            self._conn.commit()

    def list_applications(self, candidate_id: str) -> list[Application]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM applications WHERE candidate_id = ? "
                "ORDER BY created_at",
                (candidate_id,),
            ).fetchall()
        return [self._row_to_application(r) for r in rows]

    def _row_to_application(self, r: sqlite3.Row) -> Application:
        return Application(
            id=r["id"],
            candidate_id=r["candidate_id"],
            job_id=r["job_id"],
            status=r["status"],
            created_at=r["created_at"],
            name=r["name"] or "",
            email=r["email"] or "",
            earliest_start=r["earliest_start"] or "",
            linkedin=r["linkedin"] or "",
            github=r["github"] or "",
            other_links=json.loads(r["other_links"]) if r["other_links"] else [],
            requires_visa=bool(r["requires_visa"]),
            why_company=r["why_company"] or "",
            resume_name=r["resume_name"] or "",
        )

    # --- Saved jobs (bookmarks) ---------------------------------------------

    def save_job(self, candidate_id: str, job_id: str, created_at: str) -> None:
        # Idempotent: saving an already-saved job is a no-op (PK conflict ignored).
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO saved_jobs (candidate_id, job_id, "
                "created_at) VALUES (?,?,?)",
                (candidate_id, job_id, created_at),
            )
            self._conn.commit()

    def unsave_job(self, candidate_id: str, job_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM saved_jobs WHERE candidate_id = ? AND job_id = ?",
                (candidate_id, job_id),
            )
            self._conn.commit()

    def list_saved(self, candidate_id: str) -> list[SavedJob]:
        # Newest first, mirroring how the Saved tab reads.
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM saved_jobs WHERE candidate_id = ? "
                "ORDER BY created_at DESC",
                (candidate_id,),
            ).fetchall()
        return [
            SavedJob(
                candidate_id=r["candidate_id"],
                job_id=r["job_id"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
