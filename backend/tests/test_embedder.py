import numpy as np

from app.matching.embedder import Embedder, job_to_text
from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


def _job(title: str, skills: list[str], desc: str) -> Job:
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
        description=desc,
    )


def test_job_to_text_includes_title_and_skills():
    text = job_to_text(_job("Backend Engineer", ["Python", "AWS"], "Build APIs"))
    assert "Backend Engineer" in text and "Python" in text and "Build APIs" in text


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
