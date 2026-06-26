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


def _are_sentences(items: list[str]) -> bool:
    return all(s.endswith(".") and " " in s.strip() for s in items)


def test_qualifications_are_prose_sentences_not_bare_skills():
    # Required/preferred qualifications must read as full sentences (Reducto-style),
    # not bare skill words — the frontend shows prose, not skill pills.
    j = generate(5, seed=6)[0]
    assert len(j.required_quals) >= 2 and _are_sentences(j.required_quals)
    assert len(j.preferred_quals) >= 1 and _are_sentences(j.preferred_quals)


def test_qualification_sentences_mention_the_skills():
    # Skill names still appear verbatim inside the prose, so the JD stays concrete
    # and scannable even without pills.
    j = generate(20, seed=6)[3]
    req_text = " ".join(j.required_quals)
    pref_text = " ".join(j.preferred_quals)
    assert any(skill in req_text for skill in j.skills)
    assert any(skill in pref_text for skill in j.skills)


def test_about_role_is_a_paragraph():
    j = generate(5, seed=6)[0]
    assert j.about_role.count(".") >= 2  # more than one sentence
    assert len(j.about_role) > len(j.summary)


def test_structured_jd_sections_are_populated():
    j = generate(5, seed=6)[0]
    assert j.responsibilities and _are_sentences(j.responsibilities)
    assert j.benefits and _are_sentences(j.benefits)
    assert j.company_about and isinstance(j.company_about, str)


def test_job_no_longer_carries_description_blob():
    # The single description string is replaced by structured fields the frontend
    # styles section-by-section.
    j = generate(5, seed=6)[0]
    assert not hasattr(j, "description")
