from datetime import date

from app.resume.profile import HeuristicExtractor, ResumeProfile, SeniorityRank

# Pin "today" so education status (expected vs. past graduation) is deterministic.
_EX = HeuristicExtractor(today=date(2026, 6, 26))


def test_seniority_from_executive_title():
    p = _EX.extract("VP of Engineering at Acme. Led a 40-person org.")
    assert p.seniority == SeniorityRank.EXECUTIVE


def test_seniority_takes_the_highest_title_in_history():
    # A VP whose history also lists Senior Engineer reads as EXECUTIVE (max), not
    # senior — seniority is the person's peak/most-recent level.
    text = "Senior Software Engineer 2015-2019. Director of Platform 2019-2024."
    assert _EX.extract(text).seniority == SeniorityRank.EXECUTIVE


def test_intern_title_reads_as_intern():
    assert _EX.extract("Software Engineering Intern, summer 2025.").seniority == (
        SeniorityRank.INTERN
    )


def test_bare_manager_titles_are_not_promoted():
    # Product/Program/Account Manager are IC-ish titles — must NOT read as exec.
    p = _EX.extract("Product Manager at Acme. Shipped the billing platform.")
    assert p.seniority != SeniorityRank.EXECUTIVE


def test_years_extracted_from_explicit_phrase():
    assert _EX.extract("8+ years of experience building backends.").total_years == 8.0


def test_seniority_falls_back_to_years_when_no_title_keyword():
    # No title keyword, but tenure is stated → conservative rank from years.
    assert _EX.extract("6 years of experience in data.").seniority == (
        SeniorityRank.SENIOR
    )
    assert _EX.extract("1 year of experience.").seniority == SeniorityRank.ENTRY


def test_education_in_progress_from_expected_future_year():
    p = _EX.extract("B.S. in Computer Science, expected May 2027.")
    assert p.education_status == "in_progress"
    assert p.grad_year == 2027


def test_education_graduated_from_past_degree_year():
    p = _EX.extract("B.S. in Computer Science, Stanford, 2019.")
    assert p.education_status == "graduated"
    assert p.grad_year == 2019


def test_education_unknown_when_no_signal():
    assert _EX.extract("Backend engineer who likes Go.").education_status == "unknown"


def test_skills_matched_from_shared_lexicon():
    skills = _EX.extract("Strong with Python, Postgres, and React.").skills
    assert {"Python", "Postgres", "React"} <= set(skills)
    # Word-boundary: "Go" must not be matched inside "Google".
    assert "Go" not in _EX.extract("Worked at Google on search.").skills


def test_fail_open_on_garbage():
    p = _EX.extract("asdf qwer zxcv")
    assert p == ResumeProfile()  # all-default: no seniority, unknown edu, no skills
