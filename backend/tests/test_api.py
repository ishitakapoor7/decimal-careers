import io

from docx import Document
from fastapi.testclient import TestClient

from app.main import app, get_state
from app.state import AppState

_DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _docx(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# Small deterministic state for fast tests.
_TEST_STATE = AppState.seeded(n=60, seed=7)
app.dependency_overrides[get_state] = lambda: _TEST_STATE
client = TestClient(app)


def test_jobs_paginated_and_filtered():
    r = client.get("/jobs", params={"team": "engineering", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] == 5 and len(body["items"]) <= 5
    assert all(j["team"] == "engineering" for j in body["items"])


def test_job_detail_and_404():
    listing = client.get("/jobs", params={"limit": 1}).json()["items"][0]
    assert client.get(f"/jobs/{listing['id']}").status_code == 200
    assert client.get("/jobs/does-not-exist").status_code == 404


def test_limit_capped_at_100():
    r = client.get("/jobs", params={"limit": 1000})
    assert r.status_code == 422


def test_upload_resume_then_apply_and_list():
    up = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("python backend engineer postgres"), _DOCX_MIME)},
    )
    assert up.status_code == 200
    cid = up.json()["candidate_id"]  # server-minted
    assert cid
    job_id = client.get("/jobs", params={"limit": 1}).json()["items"][0]["id"]
    ap = client.post(
        "/apply",
        json={
            "candidate_id": cid,
            "job_id": job_id,
            "name": "Ada Lovelace",
            "email": "ada@example.com",
        },
    )
    assert ap.status_code == 200 and ap.json()["job_id"] == job_id
    apps = client.get("/applications", params={"candidate_id": cid}).json()
    assert any(a["job_id"] == job_id for a in apps["items"])


def test_apply_requires_name_and_email():
    # The apply form's required fields are enforced server-side, not just in the UI.
    cid = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("python backend"), _DOCX_MIME)},
    ).json()["candidate_id"]
    job_id = client.get("/jobs", params={"limit": 1}).json()["items"][0]["id"]
    r = client.post("/apply", json={"candidate_id": cid, "job_id": job_id})
    assert r.status_code == 422


def test_apply_stores_form_inputs():
    # The whole point of the form: the inputs come back on the applications page.
    cid = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("python backend"), _DOCX_MIME)},
    ).json()["candidate_id"]
    job_id = client.get("/jobs", params={"limit": 1}).json()["items"][0]["id"]
    payload = {
        "candidate_id": cid,
        "job_id": job_id,
        "name": "Grace Hopper",
        "email": "grace@example.com",
        "earliest_start": "2026-08",
        "linkedin": "https://linkedin.com/in/grace",
        "github": "https://github.com/grace",
        "other_links": ["https://grace.dev"],
        "requires_visa": True,
        "why_company": "I love the matching problem.",
        "resume_name": "grace_tailored.pdf",
    }
    assert client.post("/apply", json=payload).status_code == 200
    app = client.get("/applications", params={"candidate_id": cid}).json()["items"][0]
    assert app["name"] == "Grace Hopper"
    assert app["earliest_start"] == "2026-08"
    assert app["other_links"] == ["https://grace.dev"]
    assert app["requires_visa"] is True
    assert app["why_company"] == "I love the matching problem."
    assert app["resume_name"] == "grace_tailored.pdf"


def test_save_unsave_and_list():
    cid = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("python backend"), _DOCX_MIME)},
    ).json()["candidate_id"]
    job_id = client.get("/jobs", params={"limit": 1}).json()["items"][0]["id"]
    # Save, then it shows up as a full job on the saved list.
    assert client.post("/saved", json={"candidate_id": cid, "job_id": job_id}).json() == {"saved": True}
    saved = client.get("/saved", params={"candidate_id": cid}).json()["items"]
    assert any(j["id"] == job_id for j in saved)
    # Saving again is idempotent (no duplicate).
    client.post("/saved", json={"candidate_id": cid, "job_id": job_id})
    assert len(client.get("/saved", params={"candidate_id": cid}).json()["items"]) == 1
    # Unsave removes it.
    client.delete("/saved", params={"candidate_id": cid, "job_id": job_id})
    assert client.get("/saved", params={"candidate_id": cid}).json()["items"] == []


def test_save_unknown_job_404():
    r = client.post("/saved", json={"candidate_id": "c1", "job_id": "nope"})
    assert r.status_code == 404


def test_upload_mints_unique_ids():
    f = {"file": ("r.docx", _docx("data scientist python"), _DOCX_MIME)}
    a = client.post("/upload-resume", files=f).json()["candidate_id"]
    b = client.post("/upload-resume", files=f).json()["candidate_id"]
    assert a and b and a != b


def test_upload_reuses_supplied_id():
    f = {"file": ("r.docx", _docx("designer figma"), _DOCX_MIME)}
    first = client.post(
        "/upload-resume", data={"candidate_id": "keep-me"}, files=f
    )
    assert first.json()["candidate_id"] == "keep-me"
    # Re-upload with the same id replaces that candidate's resume, same id back.
    again = client.post(
        "/upload-resume",
        data={"candidate_id": "keep-me"},
        files={"file": ("r.docx", _docx("designer sketch"), _DOCX_MIME)},
    )
    assert again.json()["candidate_id"] == "keep-me"


def test_personalized_ranking_failure_degrades_to_plain_browse():
    # Personalization is an enhancement, not a hard dependency: if the ranking
    # layer throws (index / embedder / a future remote vector store), the request
    # must still serve the catalog (200), not 500.
    cid = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("python backend engineer"), _DOCX_MIME)},
    ).json()["candidate_id"]

    def boom(*args, **kwargs):
        raise RuntimeError("vector store unavailable")

    original = _TEST_STATE.ranker.rank_ids
    _TEST_STATE.ranker.rank_ids = boom  # type: ignore[method-assign]
    try:
        r = client.get("/jobs", params={"candidate_id": cid, "limit": 5})
    finally:
        _TEST_STATE.ranker.rank_ids = original  # type: ignore[method-assign]
    assert r.status_code == 200
    assert len(r.json()["items"]) > 0


def test_job_response_includes_new_display_fields():
    item = client.get("/jobs", params={"limit": 1}).json()["items"][0]
    for key in (
        "company", "company_about", "summary", "about_role", "responsibilities",
        "required_quals", "preferred_quals", "benefits", "salary_min",
        "salary_max", "posted_date",
    ):
        assert key in item, f"missing {key}"
    # Qualifications arrive as prose sentences, not bare skill words.
    assert all(q.endswith(".") and " " in q for q in item["required_quals"])
    assert "description" not in item  # the single blob was replaced by sections


def test_job_response_omits_min_years_exp():
    # min_years_exp was dropped (§2) until the Phase-2 seniority penalty needs it;
    # it must not appear on the wire.
    item = client.get("/jobs", params={"limit": 1}).json()["items"][0]
    assert "min_years_exp" not in item


def test_upload_empty_resume_returns_400():
    # A valid file we can't extract any text from (e.g. a scanned/image PDF, here
    # an empty docx) must signal failure, not silently fall back to plain browse.
    r = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx(""), _DOCX_MIME)},
    )
    assert r.status_code == 400


def test_upload_malformed_file_returns_400_not_500():
    # Corrupt bytes behind a supported extension is user error → clean 400.
    r = client.post(
        "/upload-resume",
        files={"file": ("r.pdf", b"not a real pdf", "application/pdf")},
    )
    assert r.status_code == 400


def test_personalized_ranking_changes_order():
    up = client.post(
        "/upload-resume",
        files={"file": ("r.docx", _docx("seo content marketing email campaigns"), _DOCX_MIME)},
    )
    cid = up.json()["candidate_id"]
    ranked = client.get(
        "/jobs", params={"candidate_id": cid, "limit": 5}
    ).json()["items"]
    # Top result for a marketing resume should not be an engineering role.
    assert ranked[0]["team"] != "engineering"
