import numpy as np
from sentence_transformers import SentenceTransformer

from app.storage.models import Job


def job_to_text(job: Job) -> str:
    # Embed only the role signal — title + skills + the short summary. The other
    # display fields (about_role, responsibilities, required/preferred_quals,
    # benefits, company_about) are prose for the page and would dilute the vector
    # across jobs, so they are deliberately excluded (§3B / §13).
    return f"{job.title}. Skills: {', '.join(job.skills)}. {job.summary}"


class Embedder:
    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> None:
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return vecs.astype(np.float32)
