import dataclasses

import numpy as np

from app.matching.embedder import Embedder, job_to_text
from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


def _job(title: str, skills: list[str], summary: str) -> Job:
    return Job(
        id="j",
        title=title,
        team=Team.ENGINEERING,
        employment_type=EmploymentType.FULL_TIME,
        seniority_level=SeniorityLevel.MID,
        city="NYC",
        state_region="NY",
        country="USA",
        work_mode=WorkMode.REMOTE,
        skills=skills,
        company="Acme",
        company_about="Acme builds things.",
        summary=summary,
        about_role=f"{summary} You'll do great work.",
        responsibilities=["Build and ship services."],
        required_quals=["You have 3+ years of experience.", "You know the stack."],
        preferred_quals=["Bonus points if you've shipped at scale."],
        benefits=["Competitive salary."],
        salary_min=120_000,
        salary_max=160_000,
        posted_date="2026-06-01",
    )


def test_job_to_text_includes_title_and_skills():
    text = job_to_text(_job("Backend Engineer", ["Python", "AWS"], "Build APIs"))
    assert "Backend Engineer" in text and "Python" in text and "Build APIs" in text


def test_job_to_text_embeds_summary_not_prose_qualifications():
    # The display prose (responsibilities, required/preferred quals, benefits) must
    # NOT enter the vector; only the role-specific summary does (§3B / §13). This is
    # what lets the JD read like a real posting without diluting matching.
    job = dataclasses.replace(
        _job("Engineer", ["Python"], "distinctive role summary phrase"),
        required_quals=["You have eight billion years of niche experience."],
        preferred_quals=["Bonus points for unlimited pto enjoyment."],
        benefits=["Equal opportunity employer with free kombucha."],
    )
    text = job_to_text(job)
    assert "distinctive role summary phrase" in text
    assert "eight billion years" not in text
    assert "equal opportunity" not in text


def test_encode_documents_shape_and_normalized():
    emb = Embedder()
    vecs = emb.encode_documents(["python backend engineer", "marketing seo specialist"])
    assert vecs.shape == (2, 384)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_encode_query_returns_single_unit_vector():
    emb = Embedder()
    vec = emb.encode_query("experienced python backend engineer, postgres, kubernetes")
    assert vec.shape == (384,)
    assert vec.dtype == np.float32
    assert np.allclose(np.linalg.norm(vec), 1.0, atol=1e-3)


def test_encode_query_reads_whole_resume_not_just_first_chunk():
    # A long résumé is chunked + mean-pooled, so content past the first chunk still
    # shapes the vector — the fix for the model truncating a 1500-token résumé at its
    # token cap. Distinct tail content must move the pooled vector.
    emb = Embedder()
    head = " ".join(["administrative office coordinator scheduling"] * 80)  # many chunks
    tail = "distributed systems kubernetes rust compiler engineer"
    whole = emb.encode_query(head + " " + tail)
    head_only = emb.encode_query(head)
    assert float(whole @ head_only) < 0.999


def test_related_text_scores_higher_than_unrelated():
    # Asymmetric: résumé via encode_query (query: prefix), jobs via encode_documents
    # (passage: prefix) — the way the live matching path embeds each side.
    emb = Embedder()
    resume = emb.encode_query("experienced python backend engineer, postgres, kubernetes")
    backend = emb.encode_documents(
        ["backend software engineer using python and postgres"]
    )[0]
    marketing = emb.encode_documents(["seo content marketing manager, email campaigns"])[0]
    assert float(resume @ backend) > float(resume @ marketing)
