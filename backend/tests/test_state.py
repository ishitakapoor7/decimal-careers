import os
import tempfile

from app.generator import generate
from app.state import AppState
from app.storage.db import Database


def test_app_state_indexes_existing_catalog_not_default_n():
    # Reproduces caveat §0: a persistent DB seeded with MORE jobs than the
    # seeded() default must NOT be partially re-generated. The DB is the single
    # source of truth — the index covers the WHOLE catalog, leaving no orphans
    # (DB rows that can never be ranked because they have no vector).
    path = tempfile.mktemp(suffix=".db")
    try:
        db = Database(path)
        db.init_schema()
        db.insert_jobs(generate(120, seed=0))  # seed.py-style pre-seed
        state = AppState.seeded(db_path=path, n=10)  # small default-style n
        # Index built FROM the DB (was 10 under the old regenerate-at-boot bug).
        assert len(state.index._ids) == 120
        assert state.db.count_jobs() == 120  # no extra inserts, no orphans
    finally:
        os.remove(path)


def test_app_state_seeds_an_empty_db():
    # Preserved behavior: an empty DB is still seeded with n synthetic jobs and
    # the index matches.
    state = AppState.seeded(n=15, seed=1)  # :memory:, empty
    assert state.db.count_jobs() == 15
    assert len(state.index._ids) == 15
