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
