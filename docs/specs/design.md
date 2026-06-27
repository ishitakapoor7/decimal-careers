# Personalized Career Site — Design Spec

A personalized career site (inspired by Eightfold AI–powered career sites such as Morgan Stanley's): candidates browse open positions, upload a résumé, and see jobs re-ranked to match their profile. The design prioritizes **product thinking, scalability, and tradeoff reasoning** (performance vs. simplicity vs. UX). Scalability is expressed through how the code is built — not surfaced in the product UI.

---

## 1. Goal & Core Capabilities

A personalized career website where candidates browse open positions, upload a resume, and see jobs re-ranked to match their profile. Core capabilities:

1. Display a list of open positions across many teams (Engineering, Sales, Product, Marketing, Design, Finance, Ops).
2. Allow a candidate to upload a resume (PDF/DOCX).
3. After upload, re-rank the displayed jobs to better match the candidate's profile.
4. Be architected to scale from 5 → 500 → 50,000 → 500,000 jobs.

The product must feel like a real career site — no dead buttons. Candidates can also **apply** to jobs, and applications become a signal that improves recommendations (Phase 2).

---

## 2. Scope & Phasing

Phases are **build order with always-working checkpoints**, not a user-facing journey. The end user sees one cohesive product; phasing is how construction is sequenced so there is always something fully functional to ship.

### Phase 1 — MVP (built; fully functional, no LLM dependency in the core)
- Browse jobs across teams with working filters: **team, seniority level, geographic location (city/state/country), work mode (on-site/hybrid/remote)**.
- Job detail view.
- Upload resume (PDF/DOCX) → semantic re-rank of jobs *within* the filtered set.
- Apply to / save a job → records a real application; candidate sees their applied and saved jobs.
- **Structured profile extraction + calibrated fit** (see §4). A dependency-free heuristic extractor parses seniority, education status, skills, and inferred domain at upload; the fit layer turns raw cosine into a 0–5 score and a `strong`/`good`/`possible` tier, applying seniority, education, skill-overlap, and team-affinity factors. This is the part that makes matching *credible* rather than just topical.

Filters are the **authoritative hard-eligibility layer** (explicit user intent). Semantic similarity re-ranks within them, and the calibrated fit layer scores/tiers what survives.

### Phase 2 — Depth layers (next; each self-contained, added on top of Phase 1)
- **LLM resume extraction:** swap the heuristic extractor for one Claude call at upload → a richer, more robust structured profile (the `LlmExtractor` seam already exists behind the same `Extractor` protocol). Also used to **auto-prefill the filters** as editable defaults.
- **LLM "why this fits" re-ranking:** LLM re-ranks only the top ~20 retrieved jobs and writes a one-line fit/gap explanation. Never run over all jobs.
- **Location as a soft matching factor:** most résumés state a location; parse it and fold candidate↔job geography into the fit score (proximity / same-metro / remote-friendly), beyond the existing hard location filter.
- **Relevance feedback:** applied/saved jobs nudge the query vector so recommendations shift toward demonstrated interest.

The forward-looking detail for these lives in [`../report.md`](../report.md).

---

## 3. Architecture

Four cleanly separated layers; arrows are the only cross-layer communication.

```
React SPA (Vite, TS)
  Job list + filters · Job detail · Resume upload · Apply · Applied view
        │  JSON over HTTP
FastAPI backend (thin: validate + route)
  /jobs · /jobs/{id} · /upload-resume · /apply · /applications
        │                 │                  │
Matching service     Storage (SQLite)    Resume parser
  embedder             jobs metadata        PDF / DOCX → text
  JobIndex (numpy/     applications
    FAISS)             candidate state
  retrieve→rank
  relevance feedback
```

**Key flows:**
- **Browse:** `GET /jobs?filters` → SQL `WHERE` push-down → bounded page of jobs.
- **Personalize:** `POST /upload-resume` → parse → embed → `JobIndex.search(vector, k)` → re-ranked list within active filters.

The FastAPI layer stays thin and delegates; all logic lives in independently-testable modules.

---

## 4. Matching Pipeline

Two-stage **retrieve → rank**, hybrid (semantic similarity + structured fit).

1. **Embedding:** both jobs and resume use `intfloat/e5-small-v2` (384-dim) so they share a vector space. e5 is an **asymmetric** retrieval model: jobs are embedded as `passage: …`, the résumé as `query: …`, which separates the two roles well on real, prose-heavy résumés. Jobs embed `title + skills + summary` once at ingest (the display prose — about-the-role, responsibilities, prose qualifications, benefits, company blurb — is deliberately excluded so it can't dilute the vector). The résumé is **chunked into ~60-word windows, each embedded with the `query:` prefix, then mean-pooled and re-normalized** into one vector — so a long multi-section résumé is fully represented instead of truncated at the model's token cap. That vector is persisted on the candidate row so pagination/re-rank reuse it.

   *Why e5-small-v2:* it represents long real résumés (often 1500+ tokens) without truncation via its 512-token context, separates on-domain from off-domain far better than a short-context symmetric model, keeps a compact 384 dims, runs locally with no API key, and fits a 1GB container.
2. **`JobIndex` interface** — the swappable scalability seam:
   ```python
   class JobIndex(Protocol):
       def add(self, job_ids: list[str], vectors: np.ndarray) -> None: ...
       def search(self, query: np.ndarray, k: int) -> list[tuple[str, float]]: ...
   ```
   - `NumpyIndex` (small scale): exact, single matrix-multiply + top-k, zero deps.
   - `FaissIndex` (large scale): `IndexFlatIP` — **exact** inner-product search,
     hardware-optimized (BLAS/SIMD). Same O(N) complexity as numpy but a much
     faster constant. Approximate ANN (`IndexHNSWFlat`/IVF, sub-linear at 500k)
     is the *next* swap behind the same interface — not built, since at our scale
     exact is free and perfect, so approximation would be all cost, no benefit.
   The rest of the app only knows `search(...)`; swapping backends touches nothing else.
3. **Retrieve** (always): top-K by vector similarity (K≈100), fast at any scale.
4. **Rank** (calibrated fit): each retrieved job's cosine is turned into a 0–5 **fit score** and a `strong`/`good`/`possible` tier. LLM re-ranking of the top ~20 + written explanations is the Phase-2 layer on top.
5. **Hybrid structured fit:**
   - **Hard filters** (categorical eligibility, user-driven): employment type, level band, location, work mode. Drive SQL `WHERE`.
   - **Calibrated fit layer** (graded): the raw cosine is multiplied by four downgrade-only factors, then mapped onto an absolute 0–5 scale:
     `base = cosine · seniority_factor^Wₛ · education_factor^Wₑ · skill_factor^Wₖ · team_affinity_factor^Wₐ`, and `score = 5·clamp((base − BASE_MIN)/(BASE_MAX − BASE_MIN), 0, 1)`.
     - **Seniority** — asymmetric distance penalty; a wildly under-leveled match (new grad → staff) is heavily penalized, an adjacent stretch is mild.
     - **Education** — penalizes structural mismatches (e.g. an enrollment-required internship against an already-graduated résumé).
     - **Skill overlap** — *downgrade-only*: concrete overlap is neutral, thin/absent overlap pulls the score down.
     - **Team affinity (domain)** — the résumé's domain is inferred from its skills (specificity-weighted); a job on an unrelated team is penalized, an adjacent discipline mildly so. This is what stops a high-but-generic cosine from leaking, e.g., finance roles onto an engineering résumé.
     - The anchors (`BASE_MIN`/`BASE_MAX`) and tier cutoffs are **calibrated on real résumés**, with an off-domain/buzzword résumé as the noise-floor reference — so a genuinely unrelated match drops below the floor entirely rather than showing as a weak "possible." All weights, anchors, and cutoffs live as documented, tunable constants in `matching/fit.py`.
6. **Relevance feedback** (Phase 2): `query = normalize(resume_vec + β·mean(applied_job_vecs))`, then re-retrieve.

**Robustness principle:** the resume is a **prior, not a gate**. Explicit user filter choices always beat inference. Every fit factor **fails open** — when a signal can't be read confidently (seniority unknown, domain too thin/ambiguous to call), that factor returns 1.0 and contributes no penalty, so the match falls back to similarity-only on that dimension. We under-filter rather than silently exclude — wrongly hiding a qualified match is worse than showing a slightly-off one.

**Why the structured layer matters:** embeddings measure topical similarity, not eligibility/direction — "senior engineer" and "engineering intern" embed close together. The structured fit layer is what makes matching credible. Retrieval quality is capped by the embedding (if the right job isn't in top-K, re-ranking can't recover it), so K is a deliberate recall/cost tradeoff.

---

## 5. Data Model & Storage

**SQLite** for structured records; **job** vectors live in the `JobIndex` keyed by `job_id` (kept separate so metadata and the searched vector store scale/swap independently). The **resume** vector is a single keyed lookup (never searched), so it sits on the `candidates` row as a BLOB — the "separate stores" principle is about access pattern (ANN search vs. point lookup), not "no vectors in SQL."

```
Job
  id, title, team(enum), employment_type(enum: full_time|internship|contract),
  seniority_level(enum: intern|entry|mid|senior|staff),
  city, state_region, country, work_mode(enum: onsite|hybrid|remote),
  skills(list), company, company_about, summary,
  about_role, responsibilities(list), required_quals(list), preferred_quals(list),
  benefits(list), salary_min, salary_max, posted_date   # display fields (§3);
  # only `summary` (+ skills) is embedded — see §4. The single `description` blob
  # was split into these structured sections; qualifications are PROSE sentences,
  # not bare skill words. Job embedding lives in JobIndex, not the row.

Candidate
  id (anonymous, server-minted opaque UUID; pseudonymous, no auth/signup wall —
     client stores it in localStorage and replays it; production binds it to a
     real session via OAuth/magic-link),
  resume_text, resume_vector(BLOB, persisted so re-rank/pagination reuse it),
  profile(json: seniority, education_status, grad_year, skills, domain —
     extracted at upload, read back at ranking; drives the calibrated fit), created_at

Application
  id, candidate_id, job_id, status(enum: applied|...), created_at
```

`min_years_exp` is intentionally not in the model: seniority fit is computed from
the level enum, not a per-job year count. It would return as an independent per-job
number only if a future need (display or a years-based factor) called for it.

**Synthetic job generator** (`generator.py`) — a developer tool, not user-facing:
- Multi-company catalog (the platform matches across many fake companies — the only framing for which a 500k scale story is coherent).
- Per-team **role variants** (e.g. Backend / Frontend / ML / DevOps within Engineering), each with its own coherent skill subpool, so matching resolves to the right *kind* of role within a team, not just the right team.
- Rich JDs assembled from hand-authored pools as **structured display fields** (about-the-role, responsibilities, required/preferred qualifications, benefits, company blurb) the frontend styles section-by-section. Qualifications render as **prose sentences** with skill names woven in (Reducto-style), not bare skill words. Only the short `summary` is embedded; the prose is display-only.
- Level/type coherence (internships → intern/internship) and coherent display salaries (rise with seniority, scaled by team and country).
- `generate(n)` scales from 5 to 500,000 with one deterministic code path (same seed → same catalog). Used to (1) seed the deployed DB with a realistic catalog and (2) run the offline benchmark.

---

## 6. Scalability (built into the code, documented in the repo)

Principle: write every request-path piece as if 500k jobs were already present, even though the deployed catalog is realistic-sized (hundreds–few thousand; 500k is an aggregator-scale thought experiment, not a believable single-company catalog). Nothing scalability-related is shown in the product UI.

1. **Swappable index** — `JobIndex` chooses backend by size threshold (numpy/​FAISS).
2. **Pagination everywhere** — `GET /jobs` always returns a bounded page; never "all jobs."
3. **Filters push down to the store** — indexed SQL `WHERE`, never in-Python loops over all rows.
4. **Embeddings computed once at ingest, batched** — request path embeds only the resume + one index search; per-query cost stays flat as the catalog grows.
5. **Stateless API** — candidate state in storage, enabling horizontal scaling behind a load balancer.
6. **Offline benchmark harness** (`scripts/benchmark.py`) — measures numpy vs FAISS query latency across 5/500/50k/500k jobs (`--random` measures search latency on same-shape random vectors in seconds, since latency is content-independent for these exact indexes). Measured numbers and the numpy→FAISS crossover are in [`../report.md`](../report.md).
7. **Documented production path** (README): metadata → Postgres, vectors → pgvector/managed vector DB, embeddings → async ingest queue. Interfaces don't change — only the engines.

---

## 7. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React + Vite (TypeScript) | Author's strength; polished SPA matching the inspiration |
| Backend | FastAPI (Python) | ML in-process (no network hop); async; Pydantic typed/validated contracts; auto OpenAPI docs |
| Embeddings | sentence-transformers `intfloat/e5-small-v2` (local, 384-dim, 512-token, asymmetric query/passage) | Free, no API key, batch-embeds 500k without cost/rate limits; represents long real résumés without truncation, fits a 1GB container |
| Vector search | `JobIndex` → numpy / FAISS | Swappable seam; the scalability spine |
| Metadata store | SQLite | Zero-config; documented Postgres path for prod |
| Resume parsing | pypdf/pdfplumber + python-docx | PDF + DOCX coverage |
| LLM (Phase 2) | Claude API | Richer resume extraction + "why this fits" re-ranking |
| Deploy | Railway (single Docker image: FastAPI serves the built React bundle on one origin) | One container, no CORS; ~600MB RAM for the baked model; model + job vectors baked at build so cold start is just model-load |

---

## 8. Repo Structure

```
resume-matching/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, routes (thin)
│   │   ├── schemas.py         # Pydantic models
│   │   ├── matching/
│   │   │   ├── embedder.py    # text → vector (e5-small-v2, query/passage)
│   │   │   ├── index.py       # JobIndex + Numpy/Faiss impls
│   │   │   ├── ranker.py      # retrieve→rank, fit rescore, relevance feedback
│   │   │   └── fit.py         # calibrated 0–5 fit score + tier (the factors)
│   │   ├── storage/
│   │   │   ├── db.py
│   │   │   └── models.py      # Job, Candidate, Application, enums
│   │   ├── resume/
│   │   │   ├── parser.py      # PDF/DOCX → text
│   │   │   └── profile.py     # Heuristic + (dormant) LLM extractor → ResumeProfile
│   │   └── generator.py       # synthetic jobs
│   ├── scripts/
│   │   ├── seed.py                  # seed a DB file from the generator
│   │   ├── precompute_embeddings.py # bake job vectors (.npz) at image build
│   │   ├── benchmark.py             # numpy vs FAISS latency at 5/500/50k/500k
│   │   └── calibrate_fit.py         # derive fit anchors from real résumés (local)
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/        # JobList, JobCard, JobDetail, FilterPanel,
│       │                      #   ResumeUpload, ApplyButton, AppliedView
│       ├── api/               # typed API client
│       └── App.tsx
├── docs/                      # architecture, benchmark results, decisions
└── README.md
```

---

## 9. Testing

Weighted to where bugs hurt:
- **Matching (heaviest, TDD):** embedder (related texts score higher than unrelated); `NumpyIndex` and `FaissIndex` tested against the **same suite** to prove equivalence (safe scale swap); ranker (filters exclude correctly, seniority penalty demotes mismatches, relevance feedback shifts results).
- **Resume parser:** fixture PDF/DOCX → expected text; malformed/empty degrades gracefully.
- **API:** FastAPI `TestClient` — shapes, statuses, pagination bounds, 422 on bad input.
- **Generator:** determinism (same seed → same catalog); coherent jobs (intern level ↔ internship type; title + skills drawn from one team role-variant cluster); display salary rises with seniority.
- **Frontend (light):** a couple of component tests; lowest-risk, most-changing layer.

---

## 10. Build & Commit Strategy

Incremental commits, one coherent piece at a time (not everything at once), aligned to the vertical-slice phasing. Each commit leaves the product/tests in a working state.

---

## 11. Key Decisions & Tradeoffs

- **Python backend + FastAPI:** ML in-process; async; typed contracts; auto docs. (Flask: hand-rolled validation/docs. Django: too heavy for a thin API over a matching engine.)
- **Embeddings core, LLM re-rank as optional layer:** semantic substance + scalability spine in one choice; LLM bounded to top-K for cost/latency.
- **Synthetic data with deliberate noise:** only source that scales to 500k on command; real messiness lives in resume parsing (unavoidable) and is handled there.
- **`JobIndex` interface (numpy→FAISS), build first two tiers / document the third:** benchmark what's honestly demonstrable; document operational scaling (pgvector/managed DB) where value is operational, not algorithmic.
- **Filters authoritative, resume a prior:** explicit user intent wins; extraction sets editable defaults; under-filter rather than silently exclude.
- **Scalability in the code, docs in the repo:** product stays clean; reasoning + benchmark live in GitHub.
