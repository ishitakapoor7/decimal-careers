from app.matching.fit import (
    education_factor,
    finalize_fit,
    make_rescorer,
    seniority_factor,
    skill_overlap,
)
from app.resume.profile import ResumeProfile, SeniorityRank
from app.storage.models import (
    EmploymentType,
    Job,
    SeniorityLevel,
    Team,
    WorkMode,
)


def _job(level: SeniorityLevel, skills: list[str] | None = None) -> Job:
    return Job(
        id="j1",
        title="Some Role",
        team=Team.ENGINEERING,
        employment_type=(
            EmploymentType.INTERNSHIP
            if level == SeniorityLevel.INTERN
            else EmploymentType.FULL_TIME
        ),
        seniority_level=level,
        city="SF",
        state_region="CA",
        country="USA",
        work_mode=WorkMode.REMOTE,
        skills=skills or ["Python", "Go", "Postgres"],
        company="Acme",
        company_about="",
        summary="",
        about_role="",
        responsibilities=[],
        required_quals=[],
        preferred_quals=[],
        benefits=[],
        salary_min=0,
        salary_max=0,
        posted_date="2026-06-01",
    )


def test_seniority_factor_exact_is_full():
    f, reason, cap = seniority_factor(SeniorityRank.SENIOR, SeniorityRank.SENIOR)
    assert f == 1.0 and reason is None and cap is None


def test_seniority_factor_vp_to_intern_is_crushed_and_capped():
    f, reason, cap = seniority_factor(SeniorityRank.EXECUTIVE, SeniorityRank.INTERN)
    assert f == 0.25 * 0.6  # |d|>=4 → 0.25, over-qualified ≥3 → ×0.6
    assert cap == "possible"
    assert reason and "intern" in reason


def test_seniority_factor_unknown_candidate_is_fail_open():
    assert seniority_factor(None, SeniorityRank.INTERN) == (1.0, None, None)


def test_education_factor_graduated_into_internship_is_hard_capped():
    f, reason, cap = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.INTERN)
    )
    assert f == 0.10 and cap == "possible" and "enroll" in reason.lower()


def test_education_factor_in_progress_is_fine():
    f, _, cap = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.INTERN)
    )
    assert f == 1.0 and cap is None


def test_education_factor_only_applies_to_internships():
    f, _, _ = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 1.0


def test_skill_overlap_is_explanation_only_and_ordered():
    job = _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    assert skill_overlap(["go", "python"], job) == ["Python", "Go"]


def test_overqualified_graduated_cannot_be_strong_even_as_top_result():
    profile = ResumeProfile(seniority=SeniorityRank.EXECUTIVE, education_status="graduated")
    rescore = make_rescorer(profile, lambda _id: _job(SeniorityLevel.INTERN))
    partial = rescore("j1", 0.9)
    assert partial.calibrated < 0.2  # seniority + enrollment penalties stack
    assert partial.tier_cap == "possible"
    fit = finalize_fit(partial, ratio=1.0)  # even as the candidate's #1
    assert fit.tier == "possible"
    assert any("enroll" in r.lower() for r in fit.reasons)


def test_exact_fit_keeps_score_and_can_be_strong():
    profile = ResumeProfile(
        seniority=SeniorityRank.SENIOR, education_status="unknown", skills=["Python", "Go"]
    )
    rescore = make_rescorer(
        profile, lambda _id: _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    )
    partial = rescore("j1", 0.8)
    assert partial.calibrated == 0.8  # factor 1.0 × 1.0
    assert partial.matched_skills == ["Python", "Go"]
    assert partial.tier_cap is None
    assert finalize_fit(partial, ratio=1.0).tier == "strong"
