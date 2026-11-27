"""internal_app.py — the internal port (QE_INTERNAL_PORT, default 9090): never exposed publicly.

  GET /health    200 while the process lives; data state, data age and rebuild status
  GET /ready     200 when the role's data is in memory, else 503 (no dependency affects the code;
                 the upstream check below is informational and runs at most every 30 s)
  GET /metrics   Prometheus text format
  GET /internal/exports/stufe{tier}.json   team only: the tier export for partner/public (ETag)
Runs in the same process as app.py (serve.py), so it sees the same in-memory data.
"""
from __future__ import annotations

import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

import config
import bootstrap
import errors
import export_store
import exports
import obs
import refresh
from store import _DATA

SOURCE_CHECK_SECONDS = 30
_SOURCE_TIMEOUT = 5
_SOURCE: dict = {"ok": None, "at": None, "checkedAt": None}
_SOURCE_LOCK = threading.Lock()

app = FastAPI(title="Quellenpanel intern", openapi_url=None, docs_url=None, redoc_url=None)
errors.install(app)


def _role_tiers(role: str) -> tuple[int, ...]:
    return tuple(range(config.ROLE_MAX_TIER[role] + 1))


def _generated_at() -> str | None:
    if config.role() == "team":
        return (_DATA.get("meta") or {}).get("generatedAt") or None
    doc = export_store.current(0)
    return (doc or {}).get("generatedAt") or None


def _age_seconds(generated_at: str | None) -> float | None:
    """Age of a 'YYYY-MM-DD HH:MM' (local time of the builder) or ISO-8601 timestamp."""
    if not isinstance(generated_at, str) or not generated_at:
        return None                     # the remote export is only checked for the key's presence
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        epoch = ts.timestamp() if ts.tzinfo else time.mktime(ts.timetuple())
    except (ValueError, OverflowError, OSError):
        return None
    return max(0.0, time.time() - epoch)


def data_age() -> float:
    try:                                # a gauge callback must never break the whole scrape
        age = _age_seconds(_generated_at())
    except Exception:  # noqa: BLE001
        return math.nan
    return math.nan if age is None else age


obs.DATA_AGE.set_function(data_age)


def data_ready() -> bool:
    role = config.role()
    if role == "team":
        return bool(_DATA.get("records"))
    return all(export_store.current(t) is not None for t in _role_tiers(role))


def _data_state() -> str:
    if data_ready():
        return "ready"
    if config.role() == "team" and (bootstrap.loading() or refresh.status().get("status") == "running"):
        return "building"
    return "missing"


def _check_source() -> bool:
    """One reachability probe of what the role depends on (repository or export source)."""
    if config.role() == "team":
        target, url = "repository", config.REPO_URL
    else:
        target, url = "export_source", (config.export_source() or "").format(tier=0)
    try:
        if url.startswith(("http://", "https://")):
            r = requests.head(url, timeout=_SOURCE_TIMEOUT, allow_redirects=False,
                              headers=obs.outgoing_headers())
            ok = r.status_code < 500
        else:
            ok = bool(url) and Path(url).is_file()
    except requests.RequestException:
        ok = False
    obs.UPSTREAM.labels(target, "ok" if ok else "error").inc()
    return ok


def _source_status() -> dict:
    with _SOURCE_LOCK:
        now = time.monotonic()
        if _SOURCE["at"] is None or now - _SOURCE["at"] >= SOURCE_CHECK_SECONDS:
            _SOURCE.update(ok=_check_source(), at=now,
                           checkedAt=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        return {"ok": _SOURCE["ok"], "checkedAt": _SOURCE["checkedAt"]}


@app.get("/health")
def health():
    gen = _generated_at()
    age = _age_seconds(gen)
    return {"status": "ok", "role": config.role(), "version": config.VERSION,
            "data": {"state": _data_state(), "generatedAt": gen if isinstance(gen, str) else None,
                     "ageSeconds": None if age is None else round(age)},
            "rebuild": {**refresh.status(), "last": bootstrap.read_status()}}


@app.get("/ready")
def ready():
    body = {"status": "ready" if data_ready() else "not_ready", "role": config.role(),
            "source": _source_status()}
    return JSONResponse(body, status_code=200 if body["status"] == "ready" else 503)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(obs.REGISTRY), media_type=CONTENT_TYPE_LATEST)


@app.get("/internal/exports/stufe{tier}.json")
def internal_export(tier: int, if_none_match: str | None = Header(None)):
    """Team: the tier export for the partner/public instances (conditional GET via ETag)."""
    if config.role() != "team" or tier not in exports.TIERS:
        raise HTTPException(404, "Not Found")
    doc = export_store.current(tier)
    if doc is None:
        raise HTTPException(503, "Daten werden geladen")
    tag = export_store.etag(tier)
    if if_none_match and if_none_match == tag:
        return Response(status_code=304, headers={"ETag": tag})
    return Response(exports.dumps(doc), media_type="application/json", headers={"ETag": tag})
