# syntax=docker/dockerfile:1

# ---- Stage 1: build the React/Vite frontend --------------------------------
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty API base ⇒ the client calls /jobs, /upload-resume, … on its own origin,
# which is exactly what the FastAPI app below serves. No CORS, one URL.
ENV VITE_API_BASE=""
RUN npm run build

# ---- Stage 2: FastAPI runtime that also serves the built frontend ----------
FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend_dist \
    CAREER_DB_PATH=/data/career.db

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
# Bake the embedding model into the image so the first request needs no network
# download and cold start is just model load + seeding, not a ~80MB fetch.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# The model is now in the image's HF cache. Go fully offline for the runtime so
# SentenceTransformer loads straight from that cache and NEVER contacts the HF
# Hub on boot — an unauthenticated Hub revision check gets rate-limited and
# hangs, stalling startup forever and failing the healthcheck. Set AFTER the
# build-time download above (which does need the network).
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY backend/ ./
COPY --from=frontend /app/frontend/dist ./frontend_dist

EXPOSE 8000
# Railway injects $PORT; default to 8000 for local `docker run`. One worker only:
# the in-memory index, job map, and the single SQLite connection are per-process.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
