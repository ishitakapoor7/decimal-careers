import numpy as np
from sentence_transformers import SentenceTransformer

from app.storage.models import Job


def job_to_text(job: Job) -> str:
    return f"{job.title}. Skills: {', '.join(job.skills)}. {job.description}"


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
