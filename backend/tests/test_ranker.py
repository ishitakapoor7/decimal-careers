import numpy as np

from app.matching.fit import JobFitPartial
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


def test_rank_with_fit_thresholds_on_calibrated_and_caps_tier():
    # Query [1,1]: cosines a=c=0.707-ish... actually a=b=0.707, c=1.0. Penalties:
    # "c" crushed below threshold; "b" survives but is hard-capped to "possible"
    # despite a high score ratio; "a" is a clean strong match with skills.
    ranker = Ranker(_index(), rel_ratio=0.6, abs_floor=0.0)

    def rescore(jid: str, cos: float) -> JobFitPartial:
        if jid == "c":
            return JobFitPartial(cos * 0.05, ["over-qualified"], [], "possible")
        if jid == "b":
            return JobFitPartial(cos * 0.95, ["capped"], [], "possible")
        # ≥2 matched skills so the skill-overlap gate allows the top tier.
        return JobFitPartial(cos, [], ["Python", "Go"], None)

    ids, fits, total = ranker.rank_with_fit(
        _unit([1, 1]), {"a", "b", "c"}, limit=10, offset=0, rescore=rescore
    )
    assert "c" not in ids  # calibrated score fell below the relevance threshold
    assert total == 2
    assert fits["a"].tier == "strong"  # rank 0 of the relevant set
    assert fits["b"].tier == "possible"  # held down by the penalty cap
    assert "Python" in fits["a"].matched_skills


def test_rank_with_fit_empty_when_nothing_allowed():
    ranker = Ranker(_index())
    ids, fits, total = ranker.rank_with_fit(
        _unit([1, 0]), set(), 10, 0, lambda j, c: JobFitPartial(c, [], [], None)
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
