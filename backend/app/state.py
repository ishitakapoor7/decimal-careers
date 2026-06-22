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
    def __init__(self, db: Database, embedder: Embedder, jobs: list[Job]) -> None:
        self.db = db
        self.embedder = embedder
        self.index = build_index(jobs, embedder)
        self.ranker = Ranker(self.index)

    @classmethod
    def seeded(cls, n: int = 500, seed: int = 0) -> "AppState":
        db = Database()
        db.init_schema()
        jobs = generate(n, seed=seed)
        db.insert_jobs(jobs)
        return cls(db, Embedder(), jobs)
