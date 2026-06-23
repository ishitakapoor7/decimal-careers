"""Offline scalability benchmark: query latency vs catalog size, numpy vs FAISS."""
import time

import numpy as np

from app.generator import generate
from app.matching.embedder import Embedder, job_to_text
from app.matching.index import FaissIndex, NumpyIndex

TIERS = [5, 500, 50_000, 500_000]


def _time_search(index, query: np.ndarray, runs: int = 20) -> float:
    start = time.perf_counter()
    for _ in range(runs):
        index.search(query, k=100)
    return (time.perf_counter() - start) / runs * 1000  # ms/query


def main() -> None:
    embedder = Embedder()
    query = embedder.encode(["python backend engineer"])[0]
    print(f"{'jobs':>8} {'numpy ms':>10} {'faiss ms':>10}")
    for n in TIERS:
        jobs = generate(n, seed=0)
        vectors = embedder.encode([job_to_text(j) for j in jobs])
        ids = [j.id for j in jobs]
        npx = NumpyIndex()
        npx.add(ids, vectors)
        fx = FaissIndex()
        fx.add(ids, vectors)
        print(
            f"{n:>8} {_time_search(npx, query):>10.2f} "
            f"{_time_search(fx, query):>10.2f}"
        )


if __name__ == "__main__":
    main()
