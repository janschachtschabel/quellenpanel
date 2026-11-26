# WLO Quellenpanel — serving container (FastAPI API + built Angular SPA in one image).
#
# Stage 1 builds the Angular SPA; stage 2 serves it together with the 3-tier API. The image carries
# NO data: the team instance seeds/builds it in $QE_DATA_DIR (/data, a volume) at first start, the
# partner/public instances fetch their export from the team. Two ports: 8080 (API + SPA) and 9090
# (internal: /health, /ready, /metrics, /internal/exports — never publish it). Base images are pinned
# by digest; bump them deliberately. Set the access env at run time (all optional):
#   QE_TEAM_PASSWORD   enables tier 2 (Audit / team)        — fail-closed: unset ⇒ no team access
#   QE_ROLE            team (default) | partner | public — caps the tier; partner/public hold only
#                      their tier export (QE_EXPORT_SOURCE, re-fetched every QE_EXPORT_POLL_MINUTES)
#   QE_TIER1_PASSWORD  password gate for tier 1 (Details); unset ⇒ open on team, shut on partner
#   QE_PUBLIC_ONLY=1   transitional alias for QE_ROLE=public
#   QE_ALLOWED_ORIGINS comma-separated origins allowed a credentialed cross-origin team login
#                      (embedded widget on another origin); needs HTTPS. Empty = same-origin only

# ---- Stage 1: build the Angular SPA -> dist/browser ----
FROM node:22-slim@sha256:be979e5523c76fa4d5ca4ebd3099078f220aa47ec39c48ad5b5df9314debd6eb AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: serving container (Python) ----
FROM python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b

# Non-root user; /app and the data directory /data belong to it.
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser:appuser /data

WORKDIR /app/quellenpanel/backend

# Dependencies first — own layer for a better build cache.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code (data excluded by .dockerignore), then the SPA built in stage 1. app.py serves the SPA from
# ../frontend/dist/browser via StaticFiles, so it must land at that sibling path.
COPY backend/ /app/quellenpanel/backend/
# Repository profiles (profil.toml only — the curated starting data stays out, see .dockerignore).
COPY profiles/ /app/quellenpanel/profiles/
COPY --from=frontend /build/dist/browser /app/quellenpanel/frontend/dist/browser

RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 QE_DATA_DIR=/data LOG_FORMAT=json
VOLUME ["/data"]
EXPOSE 8080 9090

# Liveness only (the process answers); readiness is /ready on the same port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9090/health', timeout=3)"

CMD ["python", "serve.py"]
