from app.generator import generate
from app.matching.embedder import Embedder, job_to_text
from app.matching.index import FaissIndex, JobIndex, NumpyIndex
from app.matching.ranker import Ranker
from app.storage.db import Database
from app.storage.models import Job

FAISS_THRESHOLD = 20_000


def build_index(jobs: list[Job], embedder: Embedder) -> JobIndex:
    index: JobIndex = FaissIndex() if len(jobs) >= FAISS_THRESHOLD else NumpyIndex()
    vectors = embedder.encode([job_to_text(j) for j in jobs])
    index.add([j.id for j in jobs], vectors)
    return index


class AppState:
    def __init__(self, db: Database, embedder: Embedder) -> None:
        self.db = db
        self.embedder = embedder
        # The DB is the single source of truth: build the index from whatever
        # catalog is persisted, never from a separately-generated list that could
        # diverge from the DB (caveat §0 — old code regenerated at boot and left
        # orphan rows that browse could see but personalization could not rank).
        self.index = build_index(db.all_jobs(), embedder)
        self.ranker = Ranker(self.index)

    @classmethod
    def seeded(
        cls, n: int = 500, seed: int = 0, db_path: str = ":memory:"
    ) -> "AppState":
        # db_path=":memory:" for tests; deployment passes a file path so
        # uploaded resumes/applications survive a server restart.
        db = Database(db_path)
        db.init_schema()
        # Seed synthetic jobs ONLY when the catalog is empty. A persistent DB
        # pre-seeded by scripts/seed.py is used as-is, never partially rebuilt.
        if db.count_jobs() == 0:
            db.insert_jobs(generate(n, seed=seed))
        return cls(db, Embedder())
