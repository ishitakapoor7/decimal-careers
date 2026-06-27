import os

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.storage.models import Job

_QUERY_PREFIX = "query: "
_PASSAGE_PREFIX = "passage: "
_CHUNK_WORDS = 60


def job_to_text(job: Job) -> str:
    # only role signal is embedded: title + skills + short summary
    return f"{job.title}. Skills: {', '.join(job.skills)}. {job.summary}"


class Embedder:
    def __init__(self, model_name: str = "intfloat/e5-small-v2") -> None:
        # Capped intra-op threads
        torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "2")))
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def _encode(self, texts: list[str]) -> np.ndarray:
        vecs = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return vecs.astype(np.float32)

    def encode_documents(self, texts: list[str]) -> np.ndarray:
        """Embed the job catalog. Returns one unit-norm vector per text."""
        return self._encode([_PASSAGE_PREFIX + t for t in texts])

    def encode_query(self, text: str) -> np.ndarray:
        """Embed a resume as 1 unit vector. The résumé is split into word chunks, each chunk 
        gets the e5 `query:` prefix, and  chunk vectors are mean-pooled and re-normalized."""
        words = text.split()
        chunks = [
            " ".join(words[i : i + _CHUNK_WORDS])
            for i in range(0, max(len(words), 1), _CHUNK_WORDS)
        ]
        vecs = self._encode([_QUERY_PREFIX + c for c in chunks])
        pooled = vecs.mean(axis=0)
        norm = np.linalg.norm(pooled)
        if norm > 0:
            pooled = pooled / norm
        return pooled.astype(np.float32)
