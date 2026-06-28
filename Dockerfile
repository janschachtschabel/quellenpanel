# WLO Quellenpanel — serving container (FastAPI API + built Angular SPA in one image).
#
# Stage 1 builds the Angular SPA; stage 2 serves it together with the 3-tier API over the bundled
# data snapshot (backend/data/truth.json). Unlike the public-only Quellenliste image, this app has
# team features — set the access env at run time (all optional; unset = end-user-only):
#   QE_TEAM_PASSWORD   enables tier 2 (Audit / team)        — fail-closed: unset ⇒ no team access
#   QE_TIER1_PASSWORD  optional password gate for tier 1 (Details); unset ⇒ tier 1 open
#   QE_PUBLIC_ONLY=1   hard-cap everyone at tier 0 (public/embedded deployment)
#   QE_ALLOWED_ORIGINS comma-separated origins allowed a credentialed cross-origin team login
#                      (embedded widget on another origin); needs HTTPS. Empty = same-origin only

# ---- Stage 1: build the Angular SPA -> dist/browser ----
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: serving container (Python) ----
FROM python:3.12-slim

# Non-root user; /app belongs to it.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app/quellenpanel/backend

# Dependencies first — own layer for a better build cache.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code + data snapshot, then the SPA built in stage 1. app.py serves the SPA from
# ../frontend/dist/browser via StaticFiles, so it must land at that sibling path.
COPY backend/ /app/quellenpanel/backend/
COPY --from=frontend /build/dist/browser /app/quellenpanel/frontend/dist/browser

RUN chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
