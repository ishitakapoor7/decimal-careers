# Next Improvements & Scalability

The design spec ([`specs/design.md`](specs/design.md)) covers what's built; this covers what's *not* built yet and why, plus the path from a few hundred jobs to aggregator scale.

The guiding rule throughout: **the résumé is a prior, not a gate, and every signal
fails open.** Each improvement below is additive as it slots behind an interface that
already exists, so none of it requires rearchitecting Phase 1.

---

## 1. Next improvements (Phase 2)

### 1.1 LLM résumé extraction
Today a dependency-free heuristic extractor reads seniority, education, skills, and
inferred domain from the résumé text. It's deterministic, fast, and good enough to
make matching credible — but it's pattern-matching, so it misses anything phrased
unusually and can't reason about ambiguous or non-standard résumés.

The swap is already seam'd: `LlmExtractor` sits behind the same `Extractor` protocol
as the heuristic one, selected at startup by the presence of an API key. The work is
to harden it for production — one Claude call at upload returning a structured profile
`{seniority, total_years, education_status, grad_year, skills, domain, confidence}` —
and to **fall back to the heuristic extractor on any failure** (timeout, malformed
output, no key), so the upload path never hard-depends on the LLM. Extraction stays a
single bounded call per upload, never per-job.

A second payoff: the richer profile can **pre-fill the filter bar** as editable
defaults (level, location, work mode), so a candidate lands on a sensible view before
touching a control — while explicit filter choices still win.

### 1.2 Location as a matching factor 
Location is currently a **hard filter** (city/state/country drive a SQL `WHERE`), but
it's binary — you either filter on a city or you don't. Yet almost every résumé states
a location, and proximity is one of the strongest real signals of fit. I'd add it as a
**soft factor** in the calibrated fit layer, parallel to the existing seniority /
education / skill / domain factors:

- Parse the candidate's location from the résumé during extraction (add `location` to
  `ResumeProfile`).
- Add a `location_factor(candidate_loc, job)` that scores geographic fit on a graded
  scale rather than a yes/no: **same city → full, same metro/state → mild, same country
  → milder, remote-friendly role → neutral regardless of distance, otherwise →
  downgrade.** Remote roles should never be penalized on distance.
- Fold it into `base` as one more downgrade-only multiplier with its own tunable weight,
  and surface a human reason ("This role is in Austin; your résumé reads as NYC-based")
  exactly like the other factors already do.
- Keep it **fail-open**: no parseable location → factor 1.0, no penalty.

This is deliberately a *soft* factor, not a tightening of the hard filter — a great match
one state over should sink slightly, not vanish. It reuses the entire factor machinery
that's already in `fit.py`, so it's a small, well-contained change with outsized effect.

### 1.3 LLM "why this fits" re-ranking
For the **top ~20 retrieved jobs only**, a single batched Claude call could re-rank and
write a one-line fit/gap explanation per job ("Strong on the ML stack; a stretch on team
size"). Bounded to the top slice, it stays cheap and never runs over the full catalog.
This layers on top of the calibrated score — the score orders and tiers; the LLM adds
nuance and prose to the handful a candidate actually reads.

### 1.4 Relevance feedback from applies / saves
The app already records applications and saved jobs. Those are the cleanest possible
interest signal. I'd nudge the query vector toward them —
`query = normalize(resume_vec + β · mean(applied_and_saved_job_vecs))` — and re-retrieve,
so recommendations drift toward demonstrated intent over a session. Small β, so the
résumé stays the dominant prior.

---

## 2. Scalability

The deployed catalog is realistic-sized (hundreds to a few thousand). 500k is an
aggregator-scale thought experiment — not a believable single-company catalog — but the
request path is written as if it were already there. Nothing scalability-related leaks
into the product UI.

**What's already built for scale:**
- **Swappable vector index** — `JobIndex` is a protocol with `NumpyIndex` (exact
  matrix-multiply + top-k, zero deps) and `FaissIndex` (`IndexFlatIP`, BLAS/SIMD), chosen
  by a size threshold. The rest of the app only knows `search(query, k)`.
- **Pagination everywhere** — `/jobs` always returns a bounded page; never "all jobs."
- **Filters push down to the store** — indexed SQL `WHERE`, never Python loops over rows.
- **Embeddings computed once at ingest, batched** — and baked into the image at build, so
  the request path only embeds the résumé + one index search. Per-query cost stays flat as
  the catalog grows.
- **Stateless API** — candidate state lives in storage, so the app scales horizontally
  behind a load balancer.

**Measured — search latency, numpy vs FAISS** (`scripts/benchmark.py --random`):

| jobs    | numpy (ms/query) | FAISS (ms/query) |
|--------:|-----------------:|-----------------:|
| 5       |            0.004 |            0.05  |
| 500     |            0.027 |            0.031 |
| 50,000  |             3.5  |             0.80 |
| 500,000 |            42.8  |             7.15 |

Mean of 20 queries, k=100, on local CPU (representative figures; small-scale numbers
are sub-millisecond and dominated by fixed overhead, so the ordering there is noise).
Both backends are *exact* (numpy matmul; FAISS `IndexFlatIP` brute force), so search
latency depends only on catalog size and dimension, not vector contents — `--random`
measures it on same-shape random unit vectors in seconds, without embedding 500k jobs.
The crossover is the whole argument for the `FAISS_THRESHOLD` (~20k): numpy is fastest
when tiny, FAISS wins decisively past tens of thousands (~6× at 500k), and even numpy's
~43 ms at 500k confirms exact search is fast enough at realistic scale — the
approximate-ANN swap (step 1 below) is only needed well beyond it.

**The path from here, in order of when each becomes necessary:**

1. **Approximate ANN search (≈100k+ jobs).** Swap `IndexFlatIP` for `IndexHNSWFlat`/IVF
   behind the *same* `JobIndex` interface — sub-linear search, nothing else changes. Not
   built yet because at the current scale exact search is free and perfect, so approximation
   would be all cost and no benefit. It's a one-class swap when the constant finally hurts.
2. **Metadata → Postgres.** SQLite is zero-config and right for now; the `Database` class
   is the single seam. Move to Postgres for concurrent writes and real indexes when traffic
   or catalog size demands it. The query shapes don't change.
3. **Vectors → pgvector / managed vector DB.** Once the index no longer fits comfortably in
   one process's RAM, move vectors to pgvector or a managed vector store. Same `search`
   interface; only the engine behind it changes.
4. **Async ingest queue.** Today vectors are baked at build for a static catalog. At scale,
   job ingest/embedding moves to an async worker queue so writes don't block reads and new
   jobs become searchable shortly after posting.
5. **Horizontal scale-out + caching.** The API is already stateless, so it scales by adding
   replicas behind a load balancer. Hot reads (popular filter combinations, the same
   candidate paginating) cache cheaply; the per-candidate ranking is already cached per
   `candidate_id` and invalidated on résumé re-upload.

The throughline: **every scaling step is an engine swap behind an interface that already
exists** — `JobIndex`, `Database`, `Embedder`, `Extractor`. The algorithms and the API
contract don't move; only the implementations behind them do.

---

## 3. Known limitations I'd address

- **Embedding domain separation.** e5-small-v2 produces high, tightly-packed cosines —
  even off-domain pairs sit high — which is exactly why the calibrated fit layer (especially
  the team-affinity factor) carries so much of the credibility. A stronger or fine-tuned
  retrieval model would widen the raw separation and let the structured layer do less
  correcting.
- **Skill catalog coupling.** Domain inference and skill overlap read from the synthetic
  generator's skill catalog. A real deployment would want a maintained, deduplicated skills
  taxonomy (and would treat genuinely cross-domain terms — e.g. "Compliance" — as
  domain-neutral rather than pinned to one team).
- **Heuristic extraction ceiling.** The heuristic extractor is good but bounded; §1.1 is
  the real fix, with the heuristic kept as the always-available fallback.
