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


def test_encode_shape_and_normalized():
    emb = Embedder()
    vecs = emb.encode(["python backend engineer", "marketing seo specialist"])
    assert vecs.shape == (2, 384)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_related_text_scores_higher_than_unrelated():
    emb = Embedder()
    resume = emb.encode(
        ["experienced python backend engineer, postgres, kubernetes"]
    )[0]
    backend = emb.encode(
        ["backend software engineer using python and postgres"]
    )[0]
    marketing = emb.encode(["seo content marketing manager, email campaigns"])[0]
    assert float(resume @ backend) > float(resume @ marketing)
