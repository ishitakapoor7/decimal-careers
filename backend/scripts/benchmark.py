"""Offline scalability benchmark: query latency vs catalog size, numpy vs FAISS.

Default mode embeds a generated catalog at each tier (realistic end-to-end, but
embedding 500k job texts on CPU takes minutes). `--random` skips embedding and
measures search latency on random unit vectors of the same shape: both backends
are EXACT (numpy matmul; FAISS IndexFlatIP brute force), so search latency
depends only on catalog size and dimension — not vector contents — and random
vectors give representative numbers in seconds.
"""
import argparse
import gc
import time

import numpy as np

from app.matching.index import FaissIndex, NumpyIndex

# NB: the embedder (torch) and the generator are imported lazily inside main(),
# only on the embedding path. Importing torch alongside FAISS in one process
# segfaults on macOS (duplicate libomp), so --random must never pull torch in.

TIERS = [5, 500, 50_000, 500_000]
_DIM = 384


def _time_search(index, query: np.ndarray, runs: int = 20) -> float:
    start = time.perf_counter()
    for _ in range(runs):
        index.search(query, k=100)
    return (time.perf_counter() - start) / runs * 1000  # ms/query


def _unit_vectors(n: int, rng: np.random.Generator, d: int = _DIM) -> np.ndarray:
    v = rng.standard_normal((n, d)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v


def main(random_vectors: bool) -> None:
    rng = np.random.default_rng(0)
    if random_vectors:
        query = _unit_vectors(1, rng)[0]
    else:
        from app.matching.embedder import Embedder, job_to_text

        embedder = Embedder()
        query = embedder.encode_query("python backend engineer")

    print(f"{'jobs':>8} {'numpy ms':>10} {'faiss ms':>10}")
    for n in TIERS:
        if random_vectors:
            vectors = _unit_vectors(n, rng)
            ids = [str(i) for i in range(n)]
        else:
            from app.generator import generate

            jobs = generate(n, seed=0)
            vectors = embedder.encode_documents([job_to_text(j) for j in jobs])
            ids = [j.id for j in jobs]
        npx = NumpyIndex()
        npx.add(ids, vectors)
        fx = FaissIndex()
        fx.add(ids, vectors)
        print(
            f"{n:>8} {_time_search(npx, query):>10.3f} "
            f"{_time_search(fx, query):>10.3f}"
        )
        # Free each tier before building the next (500k vectors are ~0.75GB each).
        del vectors, ids, npx, fx
        gc.collect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--random",
        action="store_true",
        help="measure search latency on random unit vectors (skips embedding)",
    )
    main(parser.parse_args().random)
