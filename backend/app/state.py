from pathlib import Path

import numpy as np

from app.generator import generate
from app.matching.embedder import Embedder, job_to_text
from app.matching.index import FaissIndex, JobIndex, NumpyIndex
from app.matching.ranker import Ranker
from app.resume.profile import select_extractor
from app.storage.db import Database
from app.storage.models import Job

FAISS_THRESHOLD = 20_000

# Job embeddings baked at image-build time so boot skips embedding the whole catalog
# on CPU (which would blow past the deploy healthcheck). Absent in dev/tests.
_PRECOMPUTED_VECTORS = Path(__file__).resolve().parent / "precomputed_vectors.npz"


def _load_precomputed_vectors(jobs: list[Job], embedder: Embedder) -> np.ndarray | None:
    if not _PRECOMPUTED_VECTORS.exists():
        return None
    data = np.load(_PRECOMPUTED_VECTORS)
    # Trust the bake only if the same model produced it AND it covers exactly this
    # catalog — a model/catalog mismatch means the vectors live in another space (or
    # don't line up), so fall back to live encoding rather than serve noise.
    if "model" not in data or str(data["model"]) != embedder.model_name:
        return None
    by_id = {str(i): v for i, v in zip(data["ids"], data["vectors"])}
    if {j.id for j in jobs} != set(by_id):
        return None
    return np.stack([by_id[j.id] for j in jobs]).astype(np.float32)


def build_index(jobs: list[Job], embedder: Embedder) -> JobIndex:
    index: JobIndex = FaissIndex() if len(jobs) >= FAISS_THRESHOLD else NumpyIndex()
    vectors = _load_precomputed_vectors(jobs, embedder)
    if vectors is None:
        vectors = embedder.encode_documents([job_to_text(j) for j in jobs])
    index.add([j.id for j in jobs], vectors)
    return index


class AppState:
    def __init__(self, db: Database, embedder: Embedder) -> None:
        self.db = db
        self.embedder = embedder
        # DB is the single source of truth, so the index always mirrors persisted jobs.
        jobs = db.all_jobs()
        # In-memory job map: the rescorer needs each job's fields for every allowed job
        # on every request, so serve it from RAM (jobs are static per boot).
        self.jobs_by_id = {j.id: j for j in jobs}
        self.index = build_index(jobs, embedder)
        # Cutoffs for the PLAIN cosine fallback only (rank_ids). The calibrated-fit path
        # ignores these and drops on the absolute 0–5 floor in fit.py. Tunable.
        self.ranker = Ranker(self.index, rel_ratio=0.65, abs_floor=0.30)
        # HeuristicExtractor unless ANTHROPIC_API_KEY is set (LlmExtractor is a dormant swap).
        self.extractor = select_extractor()

    @classmethod
    def seeded(
        cls, n: int = 500, seed: int = 0, db_path: str = ":memory:"
    ) -> "AppState":
        db = Database(db_path)
        db.init_schema()
        # Seed only an empty catalog; a DB pre-seeded by scripts/seed.py is used as-is.
        if db.count_jobs() == 0:
            db.insert_jobs(generate(n, seed=seed))
        return cls(db, Embedder())
