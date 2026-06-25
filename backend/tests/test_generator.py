from app.generator import generate
from app.storage.models import EmploymentType, SeniorityLevel


def test_generate_count_and_determinism():
    a = generate(50, seed=1)
    b = generate(50, seed=1)
    assert len(a) == 50
    assert [j.id for j in a] == [j.id for j in b]  # deterministic
    assert len({j.id for j in a}) == 50  # unique ids


def test_generator_populates_new_display_fields():
    j = generate(5, seed=4)[0]
    assert j.company and isinstance(j.company, str)
    assert j.summary and isinstance(j.summary, str)
    assert j.salary_min < j.salary_max
    assert j.posted_date  # non-empty date string


def test_intern_level_implies_internship():
    jobs = generate(200, seed=2)
    for j in jobs:
        if j.seniority_level == SeniorityLevel.INTERN:
            assert j.employment_type == EmploymentType.INTERNSHIP


def test_skills_come_from_team_variant_pool():
    # Each job's skills are sampled from ONE role variant's pool, so they're a
    # subset of the team's combined variant skills — coherent sub-clusters.
    from app.generator import _ROLE_VARIANTS

    for j in generate(200, seed=3):
        team_skills = {s for _, pool in _ROLE_VARIANTS[j.team] for s in pool}
        assert set(j.skills) <= team_skills


def test_companies_vary_across_catalog():
    assert len({j.company for j in generate(60, seed=5)}) > 1


def test_posted_dates_vary_across_catalog():
    assert len({j.posted_date for j in generate(60, seed=5)}) > 1


def test_summary_articles_are_grammatical():
    # Vowel-initial titles must take "an" (e.g. "an Account Executive").
    for j in generate(120, seed=8):
        assert " a Account" not in j.summary
        assert " a Operations" not in j.summary


def test_description_is_multi_section():
    j = generate(5, seed=6)[0]
    assert j.description.count("\n") >= 3  # multiple sections / bullets
    assert len(j.description) > len(j.summary) * 3  # full JD >> embedded summary
