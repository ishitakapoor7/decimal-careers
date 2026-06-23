import numpy as np
import pytest

from app.matching.index import FaissIndex, NumpyIndex


def _unit(vals: list[float]) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


@pytest.fixture(params=[NumpyIndex, FaissIndex])
def index(request):
    if request.param is FaissIndex:
        return FaissIndex(dim=2)
    return NumpyIndex()


def test_index_returns_best_first(index):
    index.add(
        ["a", "b", "c"],
        np.stack([_unit([1, 0]), _unit([0, 1]), _unit([1, 1])]),
    )
    results = index.search(_unit([1, 0]), k=2)
    assert [r[0] for r in results] == ["a", "c"]
    assert results[0][1] > results[1][1]


def test_index_k_caps_results(index):
    index.add(["a", "b"], np.stack([_unit([1, 0]), _unit([0, 1])]))
    assert len(index.search(_unit([1, 0]), k=5)) == 2
