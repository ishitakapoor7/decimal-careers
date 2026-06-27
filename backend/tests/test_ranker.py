import numpy as np

from app.matching.fit import BASE_MAX, BASE_MIN, JobFitPartial
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


def test_relevance_threshold_drops_weak_matches():
    # With a relevance cutoff, a job far weaker than the candidate's strongest
    # match is removed entirely — not merely ranked lower. Query [1,0]: "a"=1.0,
    # "c"=0.707, "b"=0.0. threshold = max(0.65*1.0, 0.30) = 0.65, so the
    # orthogonal "b" is dropped and total reflects only the kept jobs.
    ranker = Ranker(_index(), rel_ratio=0.65, abs_floor=0.30)
    ids, total = ranker.rank_ids(
        _unit([1, 0]), allowed_ids={"a", "b", "c"}, limit=10, offset=0
    )
    assert ids == ["a", "c"]
    assert total == 2


def test_threshold_is_relative_to_the_best_allowed_match():
    # The cutoff is relative to the top score *among allowed* jobs, so a hard
    # filter that excludes the strongest matches still returns its own best.
    # Allowed {b, c} with query [1,0]: c=0.707 is the allowed top, threshold =
    # max(0.65*0.707, 0.30) = 0.46, so b (0.0) drops but c stays.
    ranker = Ranker(_index(), rel_ratio=0.65, abs_floor=0.30)
    ids, total = ranker.rank_ids(
        _unit([1, 0]), allowed_ids={"b", "c"}, limit=10, offset=0
    )
    assert ids == ["c"]
    assert total == 1


def test_rank_with_fit_sorts_by_base_thresholds_and_tiers():
    # ONE score drives order and tier. rescore hands back a fixed weighted `base`
    # per job; rank_with_fit sorts by it, maps to 0–5, tiers by absolute cutoffs,
    # and drops anything below the "possible" floor. Bases are expressed against the
    # anchors so the test survives a retune: BASE_MAX → 5.0 (strong), mid-band →
    # ~3.0 (good), below BASE_MIN → dropped.
    ranker = Ranker(_index())
    span = BASE_MAX - BASE_MIN
    bases = {"a": BASE_MAX, "b": BASE_MIN + 0.6 * span, "c": BASE_MIN - 0.05}

    def rescore(jid: str, cos: float) -> JobFitPartial:
        return JobFitPartial(bases[jid], [], ["Python", "Go"])

    ids, fits, total = ranker.rank_with_fit(
        _unit([1, 0]), {"a", "b", "c"}, limit=10, offset=0, rescore=rescore
    )
    assert ids == ["a", "b"]  # sorted by base; "c" dropped below the floor
    assert total == 2
    assert "c" not in fits
    assert fits["a"].tier == "strong" and fits["a"].score == 5.0
    assert fits["b"].tier == "good"


def test_rank_with_fit_empty_when_nothing_allowed():
    ranker = Ranker(_index())
    ids, fits, total = ranker.rank_with_fit(
        _unit([1, 0]), set(), 10, 0, lambda j, c: JobFitPartial(c, [], [])
    )
    assert ids == [] and fits == {} and total == 0


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
