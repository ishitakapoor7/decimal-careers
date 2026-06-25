from app.generator import generate
from app.storage.models import EmploymentType, SeniorityLevel, Team


def test_generate_count_and_determinism():
    a = generate(50, seed=1)
    b = generate(50, seed=1)
    assert len(a) == 50
    assert [j.id for j in a] == [j.id for j in b]  # deterministic
    assert len({j.id for j in a}) == 50  # unique ids


def test_intern_level_implies_internship():
    jobs = generate(200, seed=2)
    for j in jobs:
        if j.seniority_level == SeniorityLevel.INTERN:
            assert j.employment_type == EmploymentType.INTERNSHIP


def test_skills_match_team_cluster():
    jobs = generate(200, seed=3)
    eng_skills = {"Python", "Go", "Postgres", "Kubernetes", "React", "AWS"}
    eng_jobs = [j for j in jobs if j.team == Team.ENGINEERING]
    assert eng_jobs, "expected some engineering jobs"
    for j in eng_jobs:
        assert set(j.skills) & eng_skills  # at least one engineering skill
