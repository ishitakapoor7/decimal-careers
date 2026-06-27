"""Precompute the seeded catalog's job embeddings at image-build time.

Boot otherwise embeds all 500 jobs on CPU before uvicorn serves a single request —
the lifespan builds the index synchronously — which on a CPU-limited container blows
past the deploy healthcheck window. Generating the vectors once during `docker build`
and baking the result lets startup load them instead of recomputing, dropping cold
start from minutes to seconds. The bake is stamped with the embedding model name so a
model swap forces a rebuild instead of silently serving mismatched vectors.

Deterministic: generate(n, seed) is reproducible, so the baked ids line up with
the catalog the app seeds on first boot (same n/seed). state.build_index still
matches by id before trusting the file, so any drift falls back to live encoding.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.generator import generate
from app.matching.embedder import Embedder, job_to_text

OUT = Path(__file__).resolve().parents[1] / "app" / "precomputed_vectors.npz"


def main(n: int = 500, seed: int = 0) -> None:
    jobs = generate(n, seed=seed)
    embedder = Embedder()
    vectors = embedder.encode_documents([job_to_text(j) for j in jobs])
    ids = np.array([j.id for j in jobs])
    # Stamp the model so state._load_precomputed_vectors rejects a bake from a
    # different embedding model (job vectors and query vectors must share a space).
    np.savez(OUT, ids=ids, vectors=vectors, model=embedder.model_name)
    print(f"wrote {len(ids)} job vectors ({embedder.model_name}) to {OUT}")


if __name__ == "__main__":
    main()
