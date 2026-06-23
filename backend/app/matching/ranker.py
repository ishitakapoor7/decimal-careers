import numpy as np

from app.matching.index import JobIndex


class Ranker:
    def __init__(self, index: JobIndex, search_k: int = 1000) -> None:
        self._index = index
        self._search_k = search_k

    def rank_ids(
        self,
        query: np.ndarray,
        allowed_ids: set[str],
        limit: int,
        offset: int,
    ) -> tuple[list[str], int]:
        ranked = self._index.search(query, self._search_k)
        allowed = [job_id for job_id, _ in ranked if job_id in allowed_ids]
        total = len(allowed)
        return allowed[offset : offset + limit], total
