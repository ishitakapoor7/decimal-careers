# decimal · careers — frontend

The candidate-facing career site: a master–detail job browser that personalizes
its ranking against an uploaded résumé. React + Vite + TypeScript, talking to the
FastAPI backend in `../backend`.

## Run it

```bash
# 1. Start the backend (from ../backend) on :8000
#    uvicorn app.main:app --reload

# 2. Then, here:
npm install
npm run dev          # http://localhost:5173, proxies /api → :8000
```

`npm run build` type-checks and produces a static bundle in `dist/`.

## How it talks to the API

`src/api/client.ts` wraps every endpoint with typed methods; `src/api/types.ts`
mirrors the backend Pydantic schemas. In dev, Vite proxies `/api/*` to the
backend (see `vite.config.ts`); set `VITE_API_BASE` for a deployed build.

## Identity & personalization

There is no login. On résumé upload the backend mints an opaque `candidate_id`,
which we persist in `localStorage` (`src/lib/candidate.ts`) and attach to `/jobs`,
`/apply`, `/saved`, and `/applications`. **Start over** clears it, returning the
list to an unpersonalized browse.

## Structure

```
src/
  api/        typed client + wire types
  lib/        candidate identity, formatting helpers
  state/      CandidateContext — id, saved set, applied set
  components/ Header, FilterBar, JobCard, JobDetail, ApplyDrawer, …
  pages/      BrowsePage (master–detail), MyActivityPage (Applications | Saved)
```

The visual design (warm, candidate-first) is built from the approved Paper
artboards — tokens live as CSS variables in `src/index.css`.
