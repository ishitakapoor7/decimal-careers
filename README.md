# Personalized Career Site

A career site where candidates browse open roles, upload a résumé, and see the
listings re-ranked to their profile — semantic retrieval plus a calibrated,
explainable fit layer. Built as a take-home for Decimal AI.

- **Design & reasoning:** [`docs/specs/design.md`](docs/specs/design.md)
- **Next steps & scalability:** [`docs/report.md`](docs/report.md)

## Core capabilities

- Browse jobs across teams with hard filters (team, seniority, location, work mode).
- Upload a résumé (PDF/DOCX) → jobs re-rank within the active filters.
- Each personalized match gets a **`strong` / `good` / `possible` tier** and plain-language
  reasons for any downgrade.
- Apply to and save jobs; the candidate sees their applied and saved lists. No login —
  an opaque `candidate_id` is minted on upload and replayed from `localStorage`.

## How it works 

Jobs and résumés embed into a shared 384-dim space with `intfloat/e5-small-v2` (jobs as
`passage:`, the résumé chunked, pooled, and embedded as `query:`). A retrieval step
(`JobIndex` → numpy or FAISS) returns the top matches by cosine; a **calibrated fit layer**
then turns each cosine into a 0–5 score by applying downgrade-only factors — seniority,
education, skill overlap, and team-affinity (domain) — and maps that to a tier. Every factor
fails open: an unreadable signal contributes no penalty. Filters are the authoritative
eligibility layer; the résumé is a prior, never a gate. Full rationale in the
[design spec](docs/specs/design.md).

## Run it locally

**Backend** (from `backend/`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://localhost:8000  (seeds an in-memory catalog)
```

**Frontend** (from `frontend/`):

```bash
npm install
npm run dev                          # http://localhost:5173, proxies /api → :8000
```

**Tests** (from `backend/`):

```bash
PYTHONPATH=. .venv/bin/python -m pytest -q
```

## Run it as one container

The Dockerfile builds the React bundle, bakes the embedding model and the seeded catalog's
job vectors into the image, and serves the SPA and the API from one origin (no CORS):

```bash
docker build -t career-site .
docker run -p 8000:8000 career-site  # http://localhost:8000
```

## Deployed

The repository is deployed at - https://decimal-careers.up.railway.app/

## Layout

```
backend/    FastAPI app, matching engine, résumé parsing, synthetic generator, tests
frontend/   React + Vite + TypeScript SPA  (see frontend/README.md)
docs/        design spec + next-steps report
Dockerfile   single-image build (frontend bundle + FastAPI runtime)
```
