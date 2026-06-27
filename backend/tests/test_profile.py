from datetime import date

from app.resume.profile import (
    HeuristicExtractor,
    ResumeProfile,
    SeniorityRank,
    profile_from_json,
    profile_to_json,
)
from app.storage.models import Team

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


def test_generic_words_are_not_credited_as_skills():
    # Generic business words appear in any résumé's prose and false-match across
    # domains (a backend résumé "positioning our platform" should NOT read as having
    # the marketing skill "Positioning"); they're excluded so the skill penalty can
    # still demote off-domain roles. Real, specific skills are still credited.
    p = _EX.extract(
        "Led cross-functional research on positioning our AI platform integrations, "
        "built with Python and PyTorch."
    )
    assert {"Python", "PyTorch"} <= set(p.skills)
    assert not (
        {"Cross-functional", "Research", "Positioning", "Platform", "Integrations"}
        & set(p.skills)
    )


def test_seniority_keyword_in_prose_is_not_a_title():
    # "staff"/"senior" appear constantly in ordinary résumé prose and must NOT inflate
    # seniority unless they head an actual title (followed by a role noun).
    p = _EX.extract(
        "Supported faculty and staff with outreach. Completed a Senior Capstone "
        "Project. Collaborated with senior leadership on logistics."
    )
    assert p.seniority is None  # no "<level> <role-noun>" title anywhere


def test_seniority_title_with_role_noun_is_credited():
    assert _EX.extract("Staff Software Engineer at Acme.").seniority == (
        SeniorityRank.STAFF
    )
    assert _EX.extract("Senior Data Scientist, 2020-2024.").seniority == (
        SeniorityRank.SENIOR
    )


def test_internship_seeker_is_capped_to_entry():
    # Even with a stray "senior engineers" prose mention, an explicit internship
    # seeker is early-career — capped to ENTRY, never read as senior.
    p = _EX.extract(
        "Incoming M.S. Mechanical Engineering Student. Seeking summer internship. "
        "Collaborated with senior engineers on a design project."
    )
    assert p.seniority == SeniorityRank.ENTRY


def test_domain_inferred_from_specific_skills():
    # PyTorch/Kubernetes/Spark are engineering-only skills → confident ENGINEERING.
    p = _EX.extract("Built models with Python, PyTorch, Spark, and Kubernetes.")
    assert p.domain == Team.ENGINEERING


def test_domain_is_none_when_skills_are_thin_or_cross_domain():
    # SQL (4 teams) + Excel (finance/ops) carry no distinctive domain signal → None
    # (fail-open: no domain penalty rather than a confident wrong guess).
    p = _EX.extract("Comfortable with SQL and Excel for reporting.")
    assert p.domain is None


def test_profile_json_roundtrip_includes_domain():
    # The stored-then-ranked path (main.upload → main.list_jobs) persists the profile
    # as JSON; domain must survive the round-trip or the team-affinity factor goes dead.
    p = ResumeProfile(
        seniority=SeniorityRank.SENIOR, total_years=6.0, education_status="graduated",
        grad_year=2019, skills=["Python", "PyTorch"], domain=Team.ENGINEERING,
    )
    assert profile_from_json(profile_to_json(p)) == p


def test_profile_json_tolerates_missing_domain():
    # A profile stored before the domain field existed deserializes with domain=None.
    legacy = '{"seniority": 3, "education_status": "graduated", "skills": ["Python"]}'
    assert profile_from_json(legacy).domain is None


def test_fail_open_on_garbage():
    p = _EX.extract("asdf qwer zxcv")
    assert p == ResumeProfile()  # all-default: no seniority, unknown edu, no skills
