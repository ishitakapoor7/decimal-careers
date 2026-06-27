"""Calibrate the fit layer's absolute 0–5 anchors to the current embedding + weights.

The fit score (app/matching/fit.py) maps a weighted `base` onto an absolute 0–5
scale via the BASE_MIN/BASE_MAX anchors, and tiers it with fixed cutoffs. Those
anchors are calibrated against the `base` DISTRIBUTION, which shifts whenever the
embedding model OR any weight (W_SENIORITY/W_EDUCATION/W_SKILL) changes (cosine is
un-weighted — it multiplies into the base as-is).
Run this after either: it embeds representative résumés against the seeded catalog,
prints the resulting `base` distribution (per résumé and per team) plus the tier
counts the CURRENT anchors would produce, and suggests anchors so you can reset
BASE_MIN/BASE_MAX + the tier cutoffs and keep a sensible spread.

    PYTHONPATH=. .venv/bin/python scripts/calibrate_fit.py

It uses the real fit pipeline (encode_query → make_rescorer → to_score → tier_for),
so what it reports is exactly what the API serves. IMPORTANT: real résumés are the
calibration target, not the synthetic stand-ins below (which are written like job
descriptions and over-score). Drop a few real résumés into scripts/fixtures/resumes/
(*.pdf / *.docx — gitignored, kept out of the repo for PII) and they are picked up
automatically and treated as the primary anchors; the prose synthetics here are a
fallback so the script still runs on a fresh clone.
"""

from collections import defaultdict
from pathlib import Path

import numpy as np

from app.matching.fit import (
    BASE_MAX,
    BASE_MIN,
    W_EDUCATION,
    W_SENIORITY,
    W_SKILL,
    make_rescorer,
    tier_for,
    to_score,
)
from app.resume.parser import parse_resume
from app.resume.profile import HeuristicExtractor
from app.state import AppState

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "resumes"

# Realistic PROSE résumés (multi-section, verbose) — NOT job-style keyword lists —
# so they land in the same cosine band a real upload does. A strong on-domain SWE/ML
# résumé, an adjacent domain (marketing), a junior/new-grad, and a degenerate
# non-résumé (buzzword) that should match nothing — the noise floor for BASE_MIN.
SYNTHETIC = {
    "SWE_senior(prose)": """Jane Doe. Senior Software Engineer with 8 years building
backend services and machine learning platforms. At Acme I architected and operated
distributed microservices handling millions of requests, designed REST and gRPC APIs,
and led the migration of our data pipelines onto Kubernetes. Earlier I built model
training and serving infrastructure, fine-tuned transformer models for ranking, and
shipped recommendation features to production. I work day to day in Python, Go, and
Java across PostgreSQL, Kafka, Docker, and AWS, and I care about observability,
testing, and mentoring. B.S. in Computer Science, 2016.""",
    "Marketing_mid(prose)": """John Smith. Marketing Manager with five years driving
demand generation for B2B SaaS companies. I have owned the full marketing funnel —
SEO and content strategy, lifecycle and email campaigns, paid acquisition, and the
analytics behind them. At BrandCo I grew organic traffic substantially, ran A/B tests
on landing pages, and managed marketing automation and brand positioning across
channels. I collaborate closely with sales and product. B.A. in Communications, 2017.""",
    "NewGrad_SWE(prose)": """Alex Lee. Software engineer and recent graduate. B.S. in
Computer Science, graduated 2024. During a summer internship at a startup I built
internal tools in Python and React and wrote SQL against a Postgres database. My
coursework covered data structures, algorithms, operating systems, and databases, and
I enjoy working on small full-stack projects and learning new frameworks.""",
    "Buzzword(noise)": """Results-driven synergistic thought leader and strategic
visionary. Passionate about leveraging cross-functional paradigms to drive impactful
outcomes and unlock stakeholder value at scale. A dynamic self-starter who moves the
needle, thinks outside the box, and champions best-in-class transformational change.""",
}


def _load_resumes() -> dict[str, str]:
    resumes = dict(SYNTHETIC)
    if _FIXTURES.is_dir():
        for f in sorted(_FIXTURES.iterdir()):
            if f.suffix.lower() in (".pdf", ".docx"):
                text = parse_resume(f.name, f.read_bytes())
                if text:
                    resumes[f"REAL:{f.stem}"] = text
    return resumes


def main() -> None:
    state = AppState.seeded()
    ext = HeuristicExtractor()
    resumes = _load_resumes()
    real = [n for n in resumes if n.startswith("REAL:")]
    print(
        f"weights: cosine=1.0 (un-weighted) seniority={W_SENIORITY} "
        f"education={W_EDUCATION} skill={W_SKILL}"
    )
    print(f"current anchors: BASE_MIN={BASE_MIN} BASE_MAX={BASE_MAX}")
    print(f"real résumés in {_FIXTURES}: {real or 'NONE (using prose synthetics only)'}\n")

    genuine_tops: list[float] = []
    noise_tops: list[float] = []
    for name, text in resumes.items():
        prof = ext.extract(text)
        qv = state.embedder.encode_query(text)
        rescore = make_rescorer(prof, state.jobs_by_id.get)
        rows = [
            (rescore(jid, cos).base, state.jobs_by_id[jid].team.value)
            for jid, cos in state.index.search(qv, 5000)
        ]
        bases = [b for b, _ in rows]
        by_team = defaultdict(list)
        for b, team in rows:
            by_team[team].append(b)
        counts = defaultdict(int)
        for b in bases:
            counts[tier_for(to_score(b)) or "DROP"] += 1

        print(f"== {name}  (seniority={prof.seniority} edu={prof.education_status})")
        print(
            f"   base: max={max(bases):.3f} p90={np.percentile(bases, 90):.3f} "
            f"p75={np.percentile(bases, 75):.3f} med={np.median(bases):.3f}"
        )
        print(
            f"   tiers @ current anchors: strong={counts['strong']} "
            f"good={counts['good']} possible={counts['possible']} DROP={counts['DROP']}"
        )
        top_team = max(by_team, key=lambda t: max(by_team[t]))
        print(f"   top team: {top_team} (max base {max(by_team[top_team]):.3f})\n")

        if "Buzzword" in name or "noise" in name:
            noise_tops.append(max(bases))
        else:
            genuine_tops.append(max(bases))

    # Suggested anchors: BASE_MAX = the best genuine match (so an exact fit → ~5),
    # BASE_MIN = the off-domain/buzzword noise floor (its best match → ~0, dropped).
    # e5 similarities run high and tightly packed, so the noise floor — not 0 — is the
    # load-bearing BASE_MIN: it's what still drops an off-domain résumé to the empty state.
    print("-- suggested anchors --")
    print(f"   BASE_MAX ≈ {max(genuine_tops):.3f}  (best genuine match across résumés)")
    print(f"   BASE_MIN ≈ {max(noise_tops):.3f}  (buzzword / off-domain noise floor)")
    if real:
        print(f"   (genuine set includes real résumés: {real})")


if __name__ == "__main__":
    main()
