from typing import Protocol

import faiss
import numpy as np


class JobIndex(Protocol):
    def add(self, job_ids: list[str], vectors: np.ndarray) -> None: ...
    def search(self, query: np.ndarray, k: int) -> list[tuple[str, float]]: ...


class NumpyIndex:
    def __init__(self) -> None:
        self._ids: list[str] = []
        self._matrix: np.ndarray | None = None

    def add(self, job_ids: list[str], vectors: np.ndarray) -> None:
        vecs = vectors.astype(np.float32)
        if self._matrix is None:
            self._matrix = vecs
        else:
            self._matrix = np.vstack([self._matrix, vecs])
        self._ids.extend(job_ids)

    def search(self, query: np.ndarray, k: int) -> list[tuple[str, float]]:
        if self._matrix is None:
            return []
        scores = self._matrix @ query.astype(np.float32)
        k = min(k, len(self._ids))
        top = np.argsort(-scores)[:k]
        return [(self._ids[i], float(scores[i])) for i in top]


class FaissIndex:
    def __init__(self, dim: int = 384) -> None:
        self._index = faiss.IndexFlatIP(dim)
        self._ids: list[str] = []

    def add(self, job_ids: list[str], vectors: np.ndarray) -> None:
        self._index.add(vectors.astype(np.float32))
        self._ids.extend(job_ids)

    def search(self, query: np.ndarray, k: int) -> list[tuple[str, float]]:
        if not self._ids:
            return []
        k = min(k, len(self._ids))
        scores, idxs = self._index.search(
            query.astype(np.float32).reshape(1, -1), k
        )
        return [
            (self._ids[i], float(s))
            for s, i in zip(scores[0], idxs[0])
            if i != -1
        ]
