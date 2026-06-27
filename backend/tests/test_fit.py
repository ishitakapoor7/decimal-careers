from app.matching.fit import (
    BASE_MAX,
    BASE_MIN,
    T_GOOD,
    T_POSSIBLE,
    T_STRONG,
    JobFitPartial,
    education_factor,
    finalize_fit,
    make_rescorer,
    seniority_factor,
    skill_factor,
    skill_overlap,
    team_affinity_factor,
    tier_for,
    to_score,
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


# --- penalty factors (now return (factor, reason); the tier is derived later) ----


def test_seniority_factor_exact_is_full():
    f, reason = seniority_factor(SeniorityRank.SENIOR, SeniorityRank.SENIOR)
    assert f == 1.0 and reason is None


def test_seniority_factor_vp_to_intern_is_crushed():
    f, reason = seniority_factor(SeniorityRank.EXECUTIVE, SeniorityRank.INTERN)
    assert f == 0.25 * 0.6  # |d|>=4 → 0.25, over-qualified ≥3 → ×0.6
    assert reason and "intern" in reason


def test_seniority_factor_unknown_candidate_is_fail_open():
    assert seniority_factor(None, SeniorityRank.INTERN) == (1.0, None)


def test_education_factor_graduated_into_internship_is_penalized():
    f, reason = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.INTERN)
    )
    assert f == 0.10 and "enroll" in reason.lower()


def test_education_factor_in_progress_is_fine():
    f, reason = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.INTERN)
    )
    assert f == 1.0 and reason is None


def test_education_factor_only_applies_to_internships():
    f, _ = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 1.0


def test_enrolled_student_penalized_on_senior_role():
    f, reason = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 0.35 and "student" in reason.lower()


def test_working_professional_pursuing_a_degree_is_fail_open():
    # in_progress education but a senior title + real tenure → NOT the early-career
    # case, so the inverse rule must not fire (seniority_factor handles them).
    prof = ResumeProfile(
        education_status="in_progress", seniority=SeniorityRank.SENIOR, total_years=8.0
    )
    f, reason = education_factor(prof, _job(SeniorityLevel.STAFF))
    assert f == 1.0 and reason is None


def test_student_not_penalized_below_senior():
    f, _ = education_factor(
        ResumeProfile(education_status="in_progress"), _job(SeniorityLevel.MID)
    )
    assert f == 1.0


def test_graduated_not_penalized_on_senior_role():
    f, _ = education_factor(
        ResumeProfile(education_status="graduated"), _job(SeniorityLevel.SENIOR)
    )
    assert f == 1.0


# --- skills: overlap list (display) + skill_factor (downgrade-only, scored) ------


def test_skill_overlap_is_ordered_by_job():
    job = _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    assert skill_overlap(["go", "python"], job) == ["Python", "Go"]


def test_skill_factor_is_downgrade_only():
    assert skill_factor(0) == 0.6
    assert skill_factor(1) == 0.9
    assert skill_factor(2) == 1.0
    assert skill_factor(5) == 1.0  # never exceeds 1.0 — can't reward stuffing


def test_skill_overlap_now_lowers_base_when_thin():
    # Skills now enter the score (downgrade-only): same cosine/seniority/education,
    # but a role with no overlap scores strictly below one with full overlap.
    prof = ResumeProfile(seniority=SeniorityRank.SENIOR, skills=["Python", "Go"])
    job_match = _job(SeniorityLevel.SENIOR, skills=["Python", "Go"])
    job_nomatch = _job(SeniorityLevel.SENIOR, skills=["Rust", "Scala"])
    a = make_rescorer(prof, lambda _id: job_match)("j1", 0.7).base
    b = make_rescorer(prof, lambda _id: job_nomatch)("j1", 0.7).base
    assert a == 0.7  # 2 matched → factor 1.0, base is the raw (un-weighted) cosine
    assert b < a  # 0 matched → factor 0.6 ** 0.5 pulls it down


# --- team / domain affinity (downgrade jobs outside the résumé's domain) ---------


def test_team_affinity_unknown_domain_is_fail_open():
    assert team_affinity_factor(None, Team.FINANCE) == (1.0, None)


def test_team_affinity_same_team_is_full():
    assert team_affinity_factor(Team.ENGINEERING, Team.ENGINEERING) == (1.0, None)


def test_team_affinity_adjacent_team_is_mild():
    f, reason = team_affinity_factor(Team.ENGINEERING, Team.PRODUCT)
    assert 0.8 <= f < 1.0 and reason is None  # adjacent: still reachable, no callout


def test_team_affinity_unrelated_team_is_hard_and_explained():
    f, reason = team_affinity_factor(Team.ENGINEERING, Team.FINANCE)
    assert f <= 0.6 and reason and "finance" in reason.lower()


def test_unrelated_domain_scores_below_same_domain():
    # Same cosine/seniority/skills: an engineering résumé scores strictly lower on a
    # finance role than on an engineering role — the domain factor is what separates
    # them (cosine alone can't, the bug this fixed).
    prof = ResumeProfile(seniority=SeniorityRank.SENIOR, domain=Team.ENGINEERING)
    eng = _job(SeniorityLevel.SENIOR)  # Team.ENGINEERING
    fin = Job(
        id="j2", title="Senior Financial Analyst", team=Team.FINANCE,
        employment_type=EmploymentType.FULL_TIME, seniority_level=SeniorityLevel.SENIOR,
        city="SF", state_region="CA", country="USA", work_mode=WorkMode.REMOTE,
        skills=["Python", "Go", "Postgres"], company="Acme", company_about="",
        summary="", about_role="", responsibilities=[], required_quals=[],
        preferred_quals=[], benefits=[], salary_min=0, salary_max=0,
        posted_date="2026-06-01",
    )
    a = make_rescorer(prof, lambda _id: eng)("j1", 0.8).base
    b = make_rescorer(prof, lambda _id: fin)("j2", 0.8).base
    assert b < a


# --- score mapping + tiering (the single axis driving rank and label) -----------


def test_to_score_anchors_and_clamps():
    assert to_score(BASE_MIN) == 0.0
    assert to_score(BASE_MAX) == 5.0
    assert to_score(BASE_MIN - 0.1) == 0.0  # clamp low
    assert to_score(BASE_MAX + 0.1) == 5.0  # clamp high
    mid = to_score((BASE_MIN + BASE_MAX) / 2)
    assert abs(mid - 2.5) < 1e-9


def test_tier_for_thresholds():
    # Symbolic in the cutoffs so a retune of the constants doesn't break the test.
    assert tier_for(5.0) == "strong"
    assert tier_for(T_STRONG) == "strong"
    assert tier_for(T_STRONG - 0.01) == "good"
    assert tier_for(T_GOOD) == "good"
    assert tier_for(T_GOOD - 0.01) == "possible"
    assert tier_for(T_POSSIBLE) == "possible"
    assert tier_for(T_POSSIBLE - 0.01) is None  # below the floor → dropped


def test_finalize_fit_drops_below_floor():
    # base maps to a score under T_POSSIBLE → dropped (None), not shown.
    partial = JobFitPartial(base=BASE_MIN + 0.01, reasons=[], matched_skills=[])
    assert finalize_fit(partial) is None


def test_finalize_fit_sets_tier_and_score_from_base():
    partial = JobFitPartial(base=BASE_MAX, reasons=["note"], matched_skills=["Python"])
    fit = finalize_fit(partial)
    assert fit is not None
    assert fit.tier == "strong" and fit.score == 5.0
    assert fit.reasons == ["note"] and fit.matched_skills == ["Python"]


def test_overqualified_graduated_is_dropped():
    # A VP-level, graduated résumé against an enrollment-only intern role stacks the
    # seniority + education penalties hard enough that the score falls below the floor
    # and the role drops out entirely — it can never surface as a "strong" match.
    profile = ResumeProfile(
        seniority=SeniorityRank.EXECUTIVE, education_status="graduated"
    )
    rescore = make_rescorer(profile, lambda _id: _job(SeniorityLevel.INTERN))
    partial = rescore("j1", 0.9)
    assert partial.base < 0.2  # seniority + enrollment penalties stack
    assert finalize_fit(partial) is None


def test_exact_fit_keeps_full_base_and_is_strong():
    profile = ResumeProfile(
        seniority=SeniorityRank.SENIOR, education_status="unknown", skills=["Python", "Go"]
    )
    rescore = make_rescorer(
        profile, lambda _id: _job(SeniorityLevel.SENIOR, skills=["Python", "Go", "Postgres"])
    )
    # A genuine top-match cosine (near BASE_MAX) with no penalties must reach
    # "strong" under the calibrated bar; a middling cosine would only be "good".
    partial = rescore("j1", 0.85)
    # seniority 1.0 × education 1.0 × skill 1.0 (2 matched) → base == raw cosine
    assert partial.base == 0.85
    assert partial.matched_skills == ["Python", "Go"]
    fit = finalize_fit(partial)
    # No penalties → "strong". Symbolic in the cutoff so a retune of the anchors
    # (BASE_MIN/MAX) doesn't pin this to a stale absolute score.
    assert fit is not None and fit.tier == "strong" and fit.score >= T_STRONG
