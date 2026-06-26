from collections import OrderedDict

import numpy as np

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
        # Relevance cutoff. A job is kept only if its similarity is at least
        # max(rel_ratio * top, abs_floor), where `top` is the best score among
        # the allowed jobs. rel_ratio drops roles far weaker than the candidate's
        # strongest match (the core "don't show unrelated teams" behavior);
        # abs_floor guards the degenerate case where even the top match is weak.
        # Both default to 0.0 (no filtering) so the ranker's ordering/pagination
        # semantics are unchanged unless a caller opts in (see app/state.py).
        self._rel_ratio = rel_ratio
        self._abs_floor = abs_floor
        # Per-candidate cache of the filter-independent similarity search, so
        # paging and re-filtering for the same candidate reuse a single
        # index.search (the expensive step). In-process is fine single-instance;
        # the multi-instance version is a shared store (e.g. Redis) keyed the same
        # way. Jobs are static per boot, so only a re-upload (invalidate) stales
        # an entry.
        self._cache: OrderedDict[str, list[tuple[str, float]]] = OrderedDict()

    def rank_ids(
        self,
        query: np.ndarray,
        allowed_ids: set[str],
        limit: int,
        offset: int,
        cache_key: str | None = None,
    ) -> tuple[list[str], int]:
        ranked = self._search(query, cache_key)
        # Keep scores so we can apply the relevance cutoff. `ranked` is sorted by
        # descending score, so the first surviving entry is the allowed maximum.
        allowed = [(job_id, score) for job_id, score in ranked if job_id in allowed_ids]
        kept = self._above_threshold(allowed)
        total = len(kept)
        return kept[offset : offset + limit], total

    def _above_threshold(self, allowed: list[tuple[str, float]]) -> list[str]:
        if not allowed:
            return []
        top = allowed[0][1]
        threshold = max(self._rel_ratio * top, self._abs_floor)
        return [job_id for job_id, score in allowed if score >= threshold]

    def _search(
        self, query: np.ndarray, cache_key: str | None
    ) -> list[tuple[str, float]]:
        if cache_key is not None and cache_key in self._cache:
            self._cache.move_to_end(cache_key)  # LRU touch
            return self._cache[cache_key]
        ranked = self._index.search(query, self._search_k)
        if cache_key is not None:
            self._cache[cache_key] = ranked
            self._cache.move_to_end(cache_key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)  # evict least-recently-used
        return ranked

    def invalidate(self, cache_key: str) -> None:
        self._cache.pop(cache_key, None)
