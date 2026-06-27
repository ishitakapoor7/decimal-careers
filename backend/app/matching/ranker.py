import threading
from collections import OrderedDict
from collections.abc import Callable

import numpy as np

from app.matching.fit import JobFit, JobFitPartial, finalize_fit
from app.matching.index import JobIndex


class Ranker:
    def __init__(
        self,
        index: JobIndex,
        search_k: int = 1000,
        cache_size: int = 128,
        rel_ratio: float = 0.0,
        abs_floor: float = 0.0,
    ) -> None:
        self._index = index
        self._search_k = search_k
        self._cache_size = cache_size 
        self._rel_ratio = rel_ratio # relevance cutoff
        self._abs_floor = abs_floor
        # Per candidate cache of the filter-independent similarity search, so
        # paging and refiltering for the same candidate reuses a single
        # index.search (the expensive step)
        self._cache: OrderedDict[str, list[tuple[str, float]]] = OrderedDict()
        # lock to make cache reads/writes atomic
        self._cache_lock = threading.Lock()

    def rank_ids(
        self,
        query: np.ndarray,
        allowed_ids: set[str],
        limit: int,
        offset: int,
        cache_key: str | None = None,
    ) -> tuple[list[str], int]:
        ranked = self._search(query, cache_key)
        allowed = [(job_id, score) for job_id, score in ranked if job_id in allowed_ids]
        kept = self._above_threshold(allowed)
        total = len(kept)
        return kept[offset : offset + limit], total

    def rank_with_fit(
        self,
        query: np.ndarray,
        allowed_ids: set[str],
        limit: int,
        offset: int,
        rescore: Callable[[str, float], JobFitPartial],
        cache_key: str | None = None,
    ) -> tuple[list[str], dict[str, JobFit], int]:
        """personalized ranking with the calibrated fit layer. rescore turns each
        (job_id, cosine) into a JobFitPartial carrying the weighted base."""
        ranked = self._search(query, cache_key)
        scored = [
            (job_id, rescore(job_id, score))
            for job_id, score in ranked
            if job_id in allowed_ids
        ]
        scored.sort(key=lambda t: t[1].base, reverse=True)
        kept: list[tuple[str, JobFit]] = []
        for job_id, partial in scored:
            fit = finalize_fit(partial)
            if fit is not None:
                kept.append((job_id, fit))
        total = len(kept)
        page = kept[offset : offset + limit]
        return [jid for jid, _ in page], {jid: fit for jid, fit in page}, total

    def _above_threshold(self, allowed: list[tuple[str, float]]) -> list[str]:
        if not allowed:
            return []
        top = allowed[0][1]
        threshold = max(self._rel_ratio * top, self._abs_floor)
        return [job_id for job_id, score in allowed if score >= threshold]

    def _search(
        self, query: np.ndarray, cache_key: str | None
    ) -> list[tuple[str, float]]:
        if cache_key is not None:
            with self._cache_lock:
                if cache_key in self._cache:
                    self._cache.move_to_end(cache_key)  # LRU 
                    return self._cache[cache_key]
        ranked = self._index.search(query, self._search_k)
        if cache_key is not None:
            with self._cache_lock:
                self._cache[cache_key] = ranked
                self._cache.move_to_end(cache_key)
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)  # evict 
        return ranked

    def invalidate(self, cache_key: str) -> None:
        with self._cache_lock:
            self._cache.pop(cache_key, None)
