"""Ad-hoc diagnostic: show the top matches for a résumé with every factor exposed.

Usage: PYTHONPATH=. .venv/bin/python scripts/diag_matches.py <path-to-resume>
"""

import sys
from pathlib import Path

import numpy as np

from app.matching.fit import (
    education_factor,
    job_seniority_rank,
    make_rescorer,
    seniority_factor,
    skill_overlap,
    to_score,
    tier_for,
)
from app.resume.parser import parse_resume
from app.resume.profile import HeuristicExtractor
from app.state import AppState


def main(path: str) -> None:
    text = parse_resume(Path(path).name, Path(path).read_bytes())
    ext = HeuristicExtractor()
    profile = ext.extract(text)
    print(f"=== {Path(path).name} ===")
    print(f"tokens(words)={len(text.split())}")
    print(f"seniority={profile.seniority} years={profile.total_years} "
          f"edu={profile.education_status} grad_year={profile.grad_year} "
          f"domain={profile.domain}")
    print(f"skills={profile.skills}\n")

    state = AppState.seeded()
    qv = state.embedder.encode_query(text)
    sims = state.index.search(qv, k=len(state.jobs_by_id))  # all jobs
    rescore = make_rescorer(profile, state.jobs_by_id.get)

    rows = []
    for job_id, cos in sims:
        job = state.jobs_by_id.get(job_id)
        if job is None:
            continue
        partial = rescore(job_id, cos)
        score = to_score(partial.base)
        tier = tier_for(score)
        sf, _ = seniority_factor(profile.seniority, job_seniority_rank(job))
        ef, _ = education_factor(profile, job)
        ov = skill_overlap(profile.skills, job)
        rows.append((score, tier, cos, sf, ef, ov, job))

    rows.sort(key=lambda r: r[0], reverse=True)
    kept = [r for r in rows if r[1] is not None]
    from collections import Counter
    by_team = Counter(r[6].team.value for r in kept)
    by_tier = Counter(r[1] for r in kept)
    print(f"KEPT {len(kept)}/{len(rows)}  tiers={dict(by_tier)}")
    print(f"kept by team: {dict(by_team)}\n")

    print("TOP 25:")
    for score, tier, cos, sf, ef, ov, job in rows[:25]:
        print(f"  {score:4.2f} {str(tier):8s} cos={cos:.3f} sen={sf:.2f} edu={ef:.2f} "
              f"sk={len(ov)} | {job.team.value:11s} {job.seniority_level.value:8s} {job.title}")


if __name__ == "__main__":
    main(sys.argv[1])
