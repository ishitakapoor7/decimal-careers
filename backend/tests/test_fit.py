from app.matching.fit import (
    JobFitPartial,
    education_factor,
    finalize_fit,
    make_rescorer,
    seniority_factor,
    skill_factor,
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


def _job(
    level: SeniorityLevel,
    skills: list[str] | None = None,
    required_skills: list[str] | None = None,
) -> Job:
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
        required_skills=required_skills or [],
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


def test_skill_overlap_splits_required_and_preferred():
    job = _job(
        SeniorityLevel.SENIOR,
        skills=["Python", "Go", "Postgres"],
        required_skills=["Python", "Postgres"],
    )
    ov = skill_overlap(["go", "python"], job)
    assert ov.required == ["Python"]  # matched must-have
    assert ov.preferred == ["Go"]  # matched nice-to-have, ordered by job.skills


def test_skill_overlap_without_required_split_treats_all_as_preferred():
    # A job predating the required/preferred split must not over-claim required hits.
    job = _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    ov = skill_overlap(["go", "python"], job)
    assert ov.required == []
    assert ov.preferred == ["Python", "Go"]


def test_skill_factor_ranks_required_above_preferred():
    job = _job(
        SeniorityLevel.SENIOR,
        skills=["Python", "Go", "Postgres", "Redis"],
        required_skills=["Python", "Go"],
    )
    both = skill_factor(skill_overlap(["python", "go", "postgres", "redis"], job), job)
    req_only = skill_factor(skill_overlap(["python", "go"], job), job)
    pref_only = skill_factor(skill_overlap(["postgres", "redis"], job), job)
    none = skill_factor(skill_overlap(["java"], job), job)
    assert both == 1.0  # matched everything listed
    assert both > req_only > pref_only > none
    assert none == 0.85  # matched nothing → the floor


def test_skill_factor_neutral_without_required_split():
    # Old job with no required/preferred split → fail-open, no skill penalty.
    job = _job(SeniorityLevel.SENIOR, skills=["Python", "Go"])
    assert skill_factor(skill_overlap(["python"], job), job) == 1.0


def test_required_match_outscores_preferred_only_in_calibrated():
    # Same cosine and seniority/education: the role whose MUST-HAVES the candidate
    # hits must score strictly higher than the one where only nice-to-haves match.
    prof = ResumeProfile(seniority=SeniorityRank.SENIOR, skills=["Python", "Go"])
    job_req = _job(
        SeniorityLevel.SENIOR, skills=["Python", "Redis"], required_skills=["Python"]
    )
    job_pref = _job(
        SeniorityLevel.SENIOR, skills=["Redis", "Go"], required_skills=["Redis"]
    )
    a = make_rescorer(prof, lambda _id: job_req)("j1", 0.7).calibrated
    b = make_rescorer(prof, lambda _id: job_pref)("j1", 0.7).calibrated
    assert a > b


def test_enrolled_student_penalized_on_senior_role():
    f, reason, cap = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 0.35 and cap == "possible" and "student" in reason.lower()


def test_working_professional_pursuing_a_degree_is_fail_open():
    # in_progress education but a senior title + real tenure → NOT the early-career
    # case, so the inverse rule must not fire (seniority_factor handles them).
    prof = ResumeProfile(
        education_status="in_progress", seniority=SeniorityRank.SENIOR, total_years=8.0
    )
    f, reason, cap = education_factor(prof, _job(SeniorityLevel.STAFF))
    assert f == 1.0 and reason is None and cap is None


def test_student_not_penalized_below_senior():
    # MID is below the senior threshold; the inverse education rule doesn't apply.
    f, _, _ = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.MID)
    )
    assert f == 1.0


def test_graduated_not_penalized_on_senior_role():
    # Only a *current* student trips the inverse rule; a graduate may have experience.
    f, _, _ = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 1.0


def test_overqualified_graduated_cannot_be_strong_even_as_top_result():
    profile = ResumeProfile(seniority=SeniorityRank.EXECUTIVE, education_status="graduated")
    rescore = make_rescorer(profile, lambda _id: _job(SeniorityLevel.INTERN))
    partial = rescore("j1", 0.9)
    assert partial.calibrated < 0.2  # seniority + enrollment penalties stack
    assert partial.tier_cap == "possible"
    fit = finalize_fit(partial, ratio=1.0)  # even as the candidate's #1
    assert fit.tier == "possible"
    assert any("enroll" in r.lower() for r in fit.reasons)


def _partial(calibrated: float) -> JobFitPartial:
    return JobFitPartial(
        calibrated=calibrated,
        reasons=[],
        matched_required=[],
        matched_preferred=[],
        tier_cap=None,
    )


def test_mediocre_top_match_is_not_strong_despite_perfect_ratio():
    # The bug: relative tiering alone makes the candidate's #1 "strong" even when its
    # absolute fit is weak. The absolute band must keep a 0.32 top out of "strong".
    assert finalize_fit(_partial(0.32), ratio=1.0).tier == "possible"


def test_absolute_good_band_caps_relative_strong():
    # 0.48 is a decent-but-not-great absolute fit: relative ratio 1.0 says "strong",
    # the absolute band says "good" → the conservative min wins.
    assert finalize_fit(_partial(0.48), ratio=1.0).tier == "good"


def test_strong_needs_both_absolute_and_relative():
    # Strong absolute fit but far below the candidate's best → relative caps it.
    assert finalize_fit(_partial(0.60), ratio=0.5).tier == "possible"
    # Strong on both axes → strong.
    assert finalize_fit(_partial(0.60), ratio=0.9).tier == "strong"


def test_exact_fit_keeps_score_and_can_be_strong():
    # Matches every listed skill, so skill_factor is 1.0 and calibrated == cosine.
    profile = ResumeProfile(
        seniority=SeniorityRank.SENIOR,
        education_status="unknown",
        skills=["Python", "Go", "Postgres"],
    )
    rescore = make_rescorer(
        profile,
        lambda _id: _job(
            SeniorityLevel.SENIOR,
            skills=["Python", "Go", "Postgres"],
            required_skills=["Python", "Postgres"],
        ),
    )
    partial = rescore("j1", 0.8)
    assert partial.calibrated == 0.8  # seniority 1.0 × education 1.0 × skill 1.0
    assert partial.matched_required == ["Python", "Postgres"]
    assert partial.matched_preferred == ["Go"]
    assert partial.tier_cap is None
    assert finalize_fit(partial, ratio=1.0).tier == "strong"
