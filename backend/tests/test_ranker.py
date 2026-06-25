import numpy as np

from app.matching.index import NumpyIndex
from app.matching.ranker import Ranker


def _unit(vals: list[float]) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


def _index() -> NumpyIndex:
    idx = NumpyIndex()
    idx.add(
        ["a", "b", "c"],
        np.stack([_unit([1, 0]), _unit([0, 1]), _unit([1, 1])]),
    )
    return idx


def test_rank_orders_by_similarity_within_allowed():
    ranker = Ranker(_index())
    ids, total = ranker.rank_ids(
        _unit([1, 0]), allowed_ids={"a", "b", "c"}, limit=10, offset=0
    )
    assert ids == ["a", "c", "b"]
    assert total == 3


def test_rank_excludes_filtered_out_ids():
    ranker = Ranker(_index())
    ids, total = ranker.rank_ids(
        _unit([1, 0]), allowed_ids={"b", "c"}, limit=10, offset=0
    )
    assert ids == ["c", "b"]
    assert total == 2


def test_rank_paginates():
    ranker = Ranker(_index())
    ids, total = ranker.rank_ids(
        _unit([1, 0]), allowed_ids={"a", "b", "c"}, limit=1, offset=1
    )
    assert ids == ["c"]
    assert total == 3


def test_search_is_cached_per_key_across_pages():
    idx = _index()
    calls = {"n": 0}
    real = idx.search

    def counting(query, k):
        calls["n"] += 1
        return real(query, k)

    idx.search = counting  # type: ignore[method-assign]
    ranker = Ranker(idx)
    q = _unit([1, 0])

    # Two pages for the same candidate reuse a single index.search.
    ranker.rank_ids(q, {"a", "b", "c"}, limit=1, offset=0, cache_key="cand")
    ranker.rank_ids(q, {"a", "b", "c"}, limit=1, offset=1, cache_key="cand")
    assert calls["n"] == 1

    # Invalidation (e.g. on re-upload) forces a recompute.
    ranker.invalidate("cand")
    ranker.rank_ids(q, {"a", "b", "c"}, limit=1, offset=0, cache_key="cand")
    assert calls["n"] == 2
