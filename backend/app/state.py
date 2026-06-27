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

# Job embeddings precomputed at image-build time (scripts/precompute_embeddings.py)
# and baked next to this module. Loading them lets boot skip embedding the whole
# catalog with MiniLM on CPU — that synchronous startup step otherwise blows past
# the deploy healthcheck on a CPU-limited container. Absent in dev/tests, where
# the catalog is small and encoding at boot is cheap, so we fall back to encoding.
_PRECOMPUTED_VECTORS = Path(__file__).resolve().parent / "precomputed_vectors.npz"


def _load_precomputed_vectors(jobs: list[Job]) -> np.ndarray | None:
    if not _PRECOMPUTED_VECTORS.exists():
        return None
    data = np.load(_PRECOMPUTED_VECTORS)
    by_id = {str(i): v for i, v in zip(data["ids"], data["vectors"])}
    # Only trust the file if it covers exactly this catalog (same generate(n, seed)).
    # Any drift — a regenerated or hand-edited DB — falls back to live encoding.
    if {j.id for j in jobs} != set(by_id):
        return None
    return np.stack([by_id[j.id] for j in jobs]).astype(np.float32)


def build_index(jobs: list[Job], embedder: Embedder) -> JobIndex:
    index: JobIndex = FaissIndex() if len(jobs) >= FAISS_THRESHOLD else NumpyIndex()
    vectors = _load_precomputed_vectors(jobs)
    if vectors is None:
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
        jobs = db.all_jobs()
        # In-memory job map, built once from the same boot-time catalog as the
        # index. The fit rescorer needs each job's seniority/skills for EVERY
        # allowed job on EVERY personalized request; serving that from RAM keeps it
        # O(1) instead of a DB read per job (jobs are static per boot, like the index).
        self.jobs_by_id = {j.id: j for j in jobs}
        self.index = build_index(jobs, embedder)
        # Relevance cutoff for personalized ranking: drop roles scoring below
        # 65% of the candidate's strongest match (with a 0.30 absolute floor).
        # Calibrated from the seeded catalog's score distributions — for a SWE
        # résumé every engineering role scores ≥0.56 while the best unrelated
        # role is ~0.48, so this removes clearly-unrelated teams while keeping
        # genuinely adjacent ones (e.g. product for a marketing résumé). Tunable.
        self.ranker = Ranker(self.index, rel_ratio=0.65, abs_floor=0.30)
        # Résumé → structured profile (seniority/education/skills). HeuristicExtractor
        # unless ANTHROPIC_API_KEY is set; the LLM path is a dormant swap (see
        # select_extractor). Built once and reused for every upload.
        self.extractor = select_extractor()

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
