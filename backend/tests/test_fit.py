from app.matching.fit import (
    JobFitPartial,
    education_factor,
    finalize_fit,
    make_rescorer,
    percentile_tier,
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
    # Flat list of the job's skills that appear in the résumé, in job order. Skill
    # overlap is NOT scored (calibrated has no skill term) — it only explains.
    job = _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    assert skill_overlap(["go", "python"], job) == ["Python", "Go"]


def test_skill_overlap_does_not_affect_calibrated():
    # Two jobs, same cosine/seniority/education, different skill overlap → identical
    # calibrated score. Skill overlap must not move the rank.
    prof = ResumeProfile(seniority=SeniorityRank.SENIOR, skills=["Python", "Go"])
    job_match = _job(SeniorityLevel.SENIOR, skills=["Python", "Go"])
    job_nomatch = _job(SeniorityLevel.SENIOR, skills=["Rust", "Scala"])
    a = make_rescorer(prof, lambda _id: job_match)("j1", 0.7).calibrated
    b = make_rescorer(prof, lambda _id: job_nomatch)("j1", 0.7).calibrated
    assert a == b == 0.7


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
    fit = finalize_fit(partial, rank=0, total=10)  # even as the candidate's #1
    assert fit.tier == "possible"
    assert any("enroll" in r.lower() for r in fit.reasons)


def _partial(calibrated: float, tier_cap=None) -> JobFitPartial:
    return JobFitPartial(
        calibrated=calibrated, reasons=[], matched_skills=[], tier_cap=tier_cap
    )


def test_percentile_tier_bands():
    # Top 10% strong, next 30% good (i.e. up to 40%), the rest possible. With 10
    # relevant matches: rank 0 strong; ranks 1–3 good; ranks 4–9 possible.
    assert percentile_tier(0, 10) == "strong"
    assert percentile_tier(1, 10) == "good"
    assert percentile_tier(3, 10) == "good"
    assert percentile_tier(4, 10) == "possible"
    assert percentile_tier(9, 10) == "possible"


def test_percentile_tier_single_match_is_strong():
    # A lone relevant match is the candidate's best by definition → strong.
    assert percentile_tier(0, 1) == "strong"


def test_percentile_tier_empty_is_possible():
    assert percentile_tier(0, 0) == "possible"


def test_top_match_is_strong_by_percentile():
    # The candidate's #1 relevant match (rank 0) with no penalty cap is "strong",
    # regardless of its absolute calibrated value — tiering is positional now.
    assert finalize_fit(_partial(0.32), rank=0, total=10).tier == "strong"
    assert finalize_fit(_partial(0.60), rank=0, total=10).tier == "strong"


def test_penalty_cap_lowers_percentile_tier():
    # A role that ranks in the strong band but carries a penalty cap is held down to
    # the cap — the over-qualified / ineligible role can't top the page.
    capped = _partial(0.9, tier_cap="possible")
    assert finalize_fit(capped, rank=0, total=10).tier == "possible"
    good_cap = _partial(0.9, tier_cap="good")
    assert finalize_fit(good_cap, rank=0, total=10).tier == "good"


def test_tail_match_is_possible():
    # Deep in the ranking → possible even with a healthy calibrated score.
    assert finalize_fit(_partial(0.60), rank=8, total=10).tier == "possible"


def test_exact_fit_keeps_score_and_can_be_strong():
    profile = ResumeProfile(
        seniority=SeniorityRank.SENIOR, education_status="unknown", skills=["Python", "Go"]
    )
    rescore = make_rescorer(
        profile, lambda _id: _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    )
    partial = rescore("j1", 0.8)
    assert partial.calibrated == 0.8  # seniority 1.0 × education 1.0, skills not scored
    assert partial.matched_skills == ["Python", "Go"]
    assert partial.tier_cap is None
    assert finalize_fit(partial, rank=0, total=10).tier == "strong"
