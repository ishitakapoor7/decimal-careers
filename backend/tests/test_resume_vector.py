import io

import numpy as np
from docx import Document
from fastapi.testclient import TestClient

from app.main import app, get_state
from app.state import AppState
from app.storage.db import Database
from app.storage.models import Candidate

_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_candidate_resume_vector_roundtrips_through_db():
    db = Database()
    db.init_schema()
    blob = np.array([0.1, 0.2, 0.3], dtype=np.float32).tobytes()
    db.insert_candidate(
        Candidate(id="c1", resume_text="r", created_at="t", resume_vector=blob)
    )
    got = db.get_candidate("c1")
    assert got is not None
    assert got.resume_vector == blob


def test_candidate_without_vector_still_roundtrips():
    db = Database()
    db.init_schema()
    db.insert_candidate(Candidate(id="c2", resume_text="r", created_at="t"))
    got = db.get_candidate("c2")
    assert got is not None and got.resume_vector is None


def test_upload_stores_vector_and_rank_does_not_reembed():
    state = AppState.seeded(n=40, seed=11)
    calls = {"n": 0}
    real_encode = state.embedder.encode

    def counting_encode(texts):
        calls["n"] += 1
        return real_encode(texts)

    state.embedder.encode = counting_encode  # type: ignore[method-assign]

    previous = app.dependency_overrides.get(get_state)
    app.dependency_overrides[get_state] = lambda: state
    try:
        client = TestClient(app)
        up = client.post(
            "/upload-resume",
            files={
                "file": ("r.docx", _docx("python backend engineer postgres"), _DOCX_MIME)
            },
        )
        assert up.status_code == 200
        cid = up.json()["candidate_id"]

        # The vector is persisted on the candidate at upload time.
        stored = state.db.get_candidate(cid)
        assert stored is not None and stored.resume_vector is not None
        assert calls["n"] == 1  # embedded exactly once, at upload

        # Paging the personalized list reuses the stored vector — no re-embed.
        client.get("/jobs", params={"candidate_id": cid, "limit": 5, "offset": 0})
        client.get("/jobs", params={"candidate_id": cid, "limit": 5, "offset": 5})
        assert calls["n"] == 1
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_state, None)
        else:
            app.dependency_overrides[get_state] = previous
