"""app.py — Quellenpanel: one API, three audience tiers over the shared data-truth engine.

Tier 0 (end user) is the default and always open; tier 1 (Steckbrief: richer technical metadata)
is open by default and optionally password-gated; tier 2 (team: internal fields, data-problem
filters, audit/export) needs the team password. Each request is served at the EFFECTIVE tier
(see tiers.py) — the smaller of what it asked for and what it is allowed. QE_PUBLIC_ONLY hard-caps
everyone at tier 0 for the public/embedded deployment.

This module is the thin web layer; logic lives in the domain modules (store, filtering, stats,
serialize, refresh, wlo_content) and the access policy in tiers.py / config.py / field_policy.py.
"""
import csv
import io
import logging
import time
from contextlib import asynccontextmanager
from urllib.parse import urlparse

import requests
from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
import filtering
import protokoll
import refresh
import serialize
import session
import stats as stats_mod
import stats_team as stats_team_mod
import tiers
import views
import wlo_content
from store import _DATA, family_count, load as _load, related_sources

log = logging.getLogger("quellenpanel")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Configure logging here (not at import) so importing the app never reconfigures the
    # root logger of a host process / ASGI server that embeds it. Skip it entirely when the host
    # has already installed handlers, so an embedding server keeps full control of its logging.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    _load()
    log.info("Quellenpanel: %d records loaded", len(_DATA["records"]))
    refresh.start_scheduler(config.AUTO_REFRESH_HOUR)  # optional nightly refresh (daemon; no-op if unset)
    yield


app = FastAPI(title="Quellenpanel", version="0.1.0", lifespan=_lifespan)

# CORS: PUBLIC (read-only) data is served to ANY origin WITHOUT credentials (wildcard). The team
# session cookie is only honoured for origins on the explicit trust list (config.ALLOWED_ORIGINS),
# which get an origin-specific, credentialed grant so an embedded widget can log in cross-origin —
# without turning the API into a credentialed open-CORS endpoint.
_CORS_METHODS = "GET, POST, OPTIONS"
_CORS_REQ_HEADERS = "Content-Type, X-Team-Password, X-Tier1-Password"

# Reject request bodies larger than this before they are buffered/parsed (defence in depth; a
# reverse proxy should cap too). Generous vs. the largest legitimate body (a batch of 100 ids).
_MAX_BODY_BYTES = 1_000_000


def _cors_headers(origin: str | None) -> dict[str, str]:
    """A credentialed, origin-specific grant for a trusted origin; otherwise the public wildcard."""
    if not origin:
        return {}
    if origin in config.ALLOWED_ORIGINS:
        return {"Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Vary": "Origin"}
    return {"Access-Control-Allow-Origin": "*"}


@app.middleware("http")
async def _http_mw(request: Request, call_next):
    origin = request.headers.get("origin")
    # Cap oversized uploads up front, based on the declared Content-Length (as proxies do), so a
    # huge payload is refused before FastAPI buffers and parses it.
    if request.method in ("POST", "PUT", "PATCH"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
            return JSONResponse({"detail": "Anfrage zu groß."}, status_code=413,
                                headers=_cors_headers(origin))
    # CORS preflight: the API declares no OPTIONS routes, so answer it here.
    if request.method == "OPTIONS" and origin is not None:
        headers = _cors_headers(origin)
        headers["Access-Control-Allow-Methods"] = _CORS_METHODS
        headers["Access-Control-Allow-Headers"] = _CORS_REQ_HEADERS
        headers["Access-Control-Max-Age"] = "600"
        return Response(status_code=204, headers=headers)
    resp = await call_next(request)
    for k, v in _cors_headers(origin).items():
        resp.headers[k] = v
    p = request.url.path
    if p.startswith("/api/") or p.startswith("/jobs/"):
        resp.headers["Cache-Control"] = "no-store"
    elif p == "/" or p.endswith((".js", ".css", ".html", ".svg")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


@app.get("/api/health")
def health():
    return {"status": "ok", "records": len(_DATA["records"])}


@app.get("/api/capabilities")
def capabilities(request: Request, x_team_password: str | None = Header(None),
                 x_tier1_password: str | None = Header(None)):
    """What the UI may offer: the highest tier this caller can reach, whether tier 1 is gated, and
    whether team login is possible at all (drives the header tier controls)."""
    return {
        "maxTier": tiers.max_tier(request, None, x_team_password, x_tier1_password),
        "publicOnly": config.PUBLIC_ONLY,
        "tier1Gated": bool(config.TIER1_PW),
        "teamAvailable": bool(config.TEAM_PW) and not config.PUBLIC_ONLY,
        "repoUrl": config.REPO_URL,   # which edu-sharing repo the data refers to (repo-neutral)
    }


@app.get("/api/meta/filters")
def filter_options():
    return stats_mod.compute_filter_options(_DATA["records"])


def _query_records(tier, q="", subject="", level="", erschliessung="", oer=None, crawler=None,
                   min_count=1, flag=None, show_blacklist=False, sort="contentCount", order="desc",
                   only_field_profile=False, has_node=None, has_bezugsquelle=None, has_spider=None, lrt=None):
    """Shared filter + sort for the list AND the exports, so an export always matches the list the
    user sees. Team-only filters (flag / show_blacklist) are honored ONLY at tier 2 — below that
    they are ignored so end users can never reveal hidden/blacklisted records."""
    team = tier >= 2
    recs = filtering.filter_records(
        _DATA["records"], q or None, None, oer, subject or None, level or None, min_count,
        has_node, only_field_profile, None, None, lrt,
        flag if team else None,                # data-problem filter (team)
        has_bezugsquelle, False, False, False,
        show_blacklist if team else False,     # reveal hidden (team)
        has_spider,
    )
    if erschliessung:
        recs = [r for r in recs
                if (r.get("internal") or {}).get("Erschliessungsstatus (genau)") == erschliessung]
    if crawler:
        recs = [r for r in recs if r.get("kind") == "crawler"]
    rev = order == "desc"
    keyfn = (lambda r: (r.get("name") or "").lower()) if sort == "name" \
        else (lambda r: r.get("contentCount") or 0)
    return sorted(recs, key=keyfn, reverse=rev)


@app.get("/api/sources")
def sources(
    tier: int = Depends(tiers.effective_tier),
    q: str = "",
    subject: str = "",
    level: str = "",
    erschliessung: str = "",
    oer: bool | None = Query(None),
    crawler: bool | None = Query(None),
    min_count: int = Query(1, ge=0),
    sort: str = Query("contentCount", pattern="^(contentCount|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
    flag: str | None = Query(None),
    show_blacklist: bool = Query(False),
    only_field_profile: bool = Query(False),
    has_node: bool | None = Query(None),
    has_bezugsquelle: bool | None = Query(None),
    has_spider: bool | None = Query(None),
    lrt: str = "",
):
    recs = _query_records(tier, q, subject, level, erschliessung, oer, crawler, min_count,
                          flag, show_blacklist, sort, order, only_field_profile,
                          has_node, has_bezugsquelle, has_spider, lrt or None)
    total = len(recs)
    start = (page - 1) * page_size
    items = [serialize.source(r, tier, family=family_count(r)) for r in recs[start:start + page_size]]
    resp = {
        "tier": tier, "total": total, "page": page, "pageSize": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0, "items": items,
    }
    if tier >= 2:
        # Filter-scoped hidden breakdown: re-run the same query with show_blacklist=True to
        # count how many records the default view hides IN THE CURRENT FILTER — not globally.
        # ZWEITDATENSATZ are only hidden when has_node is not True (they are visible in the
        # Quelldatensatz view). Mirrors the quellenerschliessung-app behaviour.
        if not flag and not show_blacklist:
            # Re-run with the SAME filters (incl. lrt) but show_blacklist=True, then count what the
            # default view hides via the shared helper — so the breakdown is always scoped to the
            # exact filter the user sees (a content-type filter changes the hidden count too).
            full = _query_records(tier, q, subject, level, erschliessung, oer, crawler, min_count,
                                  flag, True, sort, order, only_field_profile,
                                  has_node, has_bezugsquelle, has_spider, lrt or None)
            hb = filtering.hidden_breakdown(full, has_node)
            resp["hidden"] = {"blacklist": hb["blacklist"], "mehrfach": hb["zweitDatensatz"],
                              "total": hb["total"]}
        else:
            resp["hidden"] = {"blacklist": 0, "mehrfach": 0, "total": 0}
    return resp


@app.get("/api/sources/{source_id:path}/contents")
def source_contents(source_id: str, max_items: int = Query(12, ge=1, le=50), skip: int = Query(0, ge=0)):
    """Live example content of a source (NGSearch) — public, all tiers. Crawlers are matched by
    ccm:replicationsource (the spider), other sources by ccm:oeh_publisher_combined."""
    r = _DATA["byId"].get(source_id)
    if not r:
        raise HTTPException(404, "Quelle nicht gefunden")
    idn = r.get("identity") or {}
    if r.get("kind") == "crawler" and idn.get("spider"):
        prop, value = "ccm:replicationsource", idn["spider"]
    else:
        prop, value = "ccm:oeh_publisher_combined", idn.get("bezugsquelle") or r.get("name") or ""
    if not value:
        return {"total": 0, "nodes": []}
    try:
        return wlo_content.fetch_contents(prop, value, max_items, skip)
    except Exception:  # noqa: BLE001 — live API is best-effort; never 500 the detail
        raise HTTPException(502, "WLO-Inhalte derzeit nicht abrufbar") from None


@app.get("/api/sources/{source_id:path}")
def source_detail(source_id: str, tier: int = Depends(tiers.effective_tier)):
    r = _DATA["byId"].get(source_id)
    if not r:
        raise HTTPException(404, "Quelle nicht gefunden")
    # The Bezugsquelle family is public (it only references public list data) → show at every tier.
    return serialize.source(r, tier, detail=True, related=related_sources(r))


# --- Team-login brute-force throttle --------------------------------------------------------
# Per-client failure budget (in-memory; single-process internal tool). A correct login clears it;
# too many wrong tries within the rolling window get a 429 until they roll off — turning the team
# password from "online-bruteforceable" into "not" without an external dependency.
_LOGIN_FAILS: dict[str, list[float]] = {}
_LOGIN_WINDOW = 300.0     # rolling window (seconds)
_LOGIN_MAX_FAILS = 8      # wrong attempts allowed per window per client


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd
            else (request.client.host if request.client else "?"))


@app.post("/api/auth")
def auth(request: Request, response: Response, x_team_password: str | None = Header(None)):
    """Team login → httpOnly session cookie (so the password is never stored client-side).
    The password is accepted ONLY via the X-Team-Password header, never as a URL query
    parameter, so it cannot leak into proxy/access logs or browser history. Repeated wrong
    attempts from one client are rate-limited (429) to thwart online brute force."""
    ip = _client_ip(request)
    now = time.time()
    fails = [t for t in _LOGIN_FAILS.get(ip, []) if now - t < _LOGIN_WINDOW]
    if len(fails) >= _LOGIN_MAX_FAILS:
        _LOGIN_FAILS[ip] = fails
        raise HTTPException(429, "Zu viele Fehlversuche. Bitte später erneut versuchen.")
    if config.PUBLIC_ONLY or not config.check_pw(None, x_team_password):
        fails.append(now)
        _LOGIN_FAILS[ip] = fails
        raise HTTPException(403, "Falsches Passwort.")
    _LOGIN_FAILS.pop(ip, None)   # success clears the failure budget
    token = session.issue()
    origin = request.headers.get("origin")
    if origin and origin in config.ALLOWED_ORIGINS:
        # Trusted cross-origin login (embedded widget): the cookie must be sendable cross-site,
        # which requires SameSite=None; Secure (and therefore HTTPS).
        response.set_cookie(session.COOKIE, token, max_age=session.TTL,
                            httponly=True, samesite="none", secure=True)
    else:
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.set_cookie(session.COOKIE, token, max_age=session.TTL,
                            httponly=True, samesite="strict", secure=secure)
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    session.revoke(request.cookies.get(session.COOKIE))
    # Clear with the SAME attributes used when the cookie was set, otherwise the browser keeps
    # the (now server-side revoked) cookie around because the delete directive does not match.
    origin = request.headers.get("origin")
    if origin and origin in config.ALLOWED_ORIGINS:
        response.delete_cookie(session.COOKIE, path="/", samesite="none", secure=True, httponly=True)
    else:
        secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        response.delete_cookie(session.COOKIE, path="/", samesite="strict", secure=secure, httponly=True)
    return {"ok": True}


@app.get("/api/auth/status")
def auth_status(request: Request):
    return {"team": session.valid(request.cookies.get(session.COOKIE))}


# ---------------------------------------------------------------------------
# Statistics (tiered): end-user figures (0) · extended public (1) · data problems (2, team)
# ---------------------------------------------------------------------------
def _visible_records():
    """Default end-user visible set (blacklist + secondary datasets hidden)."""
    return filtering.filter_records(_DATA["records"], None, None, None, None, None, 0, None, False)


@app.get("/api/stats")
def stats(tier: int = Depends(tiers.effective_tier)):
    """Statistics OVERVIEW: end-user figures (tier 0) or the full extended view (tier >= 1).
    The team's data-problem addendum is a separate, team-gated endpoint (/api/stats/team), so the
    team stats view is "full overview + problem section", mirroring the Quellensteckbriefe app."""
    if tier >= 1:
        return stats_mod.compute_stats_full(_DATA["records"], _DATA["meta"])
    return stats_mod.compute_enduser_stats(_visible_records(), _DATA["meta"])


@app.get("/api/stats/team")
def stats_team(team: bool = Depends(tiers.is_team)):
    """Team-only data-problem / origin / spider / fill-level analysis, appended to the overview in
    the Audit tier. Fail-closed: no team login -> 403 (never leaks the problem breakdown)."""
    if not team:
        raise HTTPException(403, "Team-Login erforderlich.")
    return stats_team_mod.compute_stats_team(_DATA["records"], _DATA["meta"])


# ---------------------------------------------------------------------------
# Export — leak-safe flat view of the visible set; a data-work feature (tier 1+).
# ---------------------------------------------------------------------------
@app.get("/api/export.json")
def export_json(
    tier: int = Depends(tiers.effective_tier),
    q: str = "", subject: str = "", level: str = "", erschliessung: str = "",
    oer: bool | None = Query(None), crawler: bool | None = Query(None),
    min_count: int = Query(1, ge=0), flag: str | None = Query(None),
    show_blacklist: bool = Query(False),
    sort: str = Query("contentCount", pattern="^(contentCount|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    only_field_profile: bool = Query(False),
    has_node: bool | None = Query(None),
    has_bezugsquelle: bool | None = Query(None),
    has_spider: bool | None = Query(None),
    lrt: str = "",
):
    if tier < 1:
        raise HTTPException(403, "Export ab Detailmodus.")
    team = tier >= 2
    rows = [views.flat(r, team=team) for r in _query_records(tier, q, subject, level, erschliessung,
                                                            oer, crawler, min_count, flag, show_blacklist, sort, order,
                                                            only_field_profile, has_node, has_bezugsquelle, has_spider, lrt or None)]
    return JSONResponse(rows, headers={"Content-Disposition": "attachment; filename=quellen_export.json"})


@app.get("/api/export.csv")
def export_csv(
    tier: int = Depends(tiers.effective_tier),
    q: str = "", subject: str = "", level: str = "", erschliessung: str = "",
    oer: bool | None = Query(None), crawler: bool | None = Query(None),
    min_count: int = Query(1, ge=0), flag: str | None = Query(None),
    show_blacklist: bool = Query(False),
    sort: str = Query("contentCount", pattern="^(contentCount|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    only_field_profile: bool = Query(False),
    has_node: bool | None = Query(None),
    has_bezugsquelle: bool | None = Query(None),
    has_spider: bool | None = Query(None),
    lrt: str = "",
):
    if tier < 1:
        raise HTTPException(403, "Export ab Detailmodus.")
    team = tier >= 2
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=views.EXPORT_COLS, delimiter=";", extrasaction="ignore")
    w.writeheader()
    for r in _query_records(tier, q, subject, level, erschliessung, oer, crawler, min_count,
                            flag, show_blacklist, sort, order, only_field_profile,
                            has_node, has_bezugsquelle, has_spider, lrt or None):
        w.writerow(views.flat(r, team=team))
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=quellen_export.csv"})


# ---------------------------------------------------------------------------
# Team only: data-problem protocol, multi-source PDF data, live refresh, reload.
# ---------------------------------------------------------------------------
@app.get("/api/protokoll.md")
def protokoll_md(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Nur intern (Team-Login nötig).")
    md = protokoll.build_protokoll(_DATA["records"], _DATA["meta"])
    return Response(md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=fehler-protokoll.md"})


@app.post("/api/sources/batch")
def sources_batch(ids: list[str] = Body(..., embed=True), tier: int = Depends(tiers.effective_tier)):
    """Several records at the granted tier — feeds the client-side multi-source PDF export."""
    out = []
    for i in ids[:100]:
        r = _DATA["byId"].get(i)
        if r:
            out.append(serialize.source(r, tier, detail=True))
    return {"items": out}


@app.post("/jobs/refresh")
def jobs_refresh(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Team-Login erforderlich.")
    return refresh.start()


@app.get("/jobs/latest")
def jobs_latest():
    return refresh.status()


@app.post("/api/admin/reload")
def admin_reload(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Nur intern.")
    _load()
    return {"ok": True, "meta": _DATA["meta"]}


# ---------------------------------------------------------------------------
# Preview-image proxy for the PDF export (works around the canvas CORS taint so
# jsPDF.addImage can draw repository thumbnails). Only the configured repository
# host is allowed (repo-neutral; not an open proxy).
# ---------------------------------------------------------------------------
_THUMB_CACHE: dict[str, tuple[bytes, str]] = {}
_REPO_HOST = (urlparse(config.REPO_URL).hostname or "").lower()
_THUMB_MAX_BYTES = 5 * 1024 * 1024   # hard cap per preview image (5 MB)


@app.get("/api/thumb")
def thumb(url: str = Query(..., description="Preview URL on the configured repository host")):
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    # HTTPS only, and only the EXACT configured repository host (or a sub-domain of it) — repo-neutral,
    # never an open proxy. Matching the exact host (not the registrable domain) means a deployment
    # against a multi-label TLD (e.g. example.co.uk) cannot accidentally widen the allow-list.
    if parts.scheme != "https" or not (host == _REPO_HOST or host.endswith("." + _REPO_HOST)):
        raise HTTPException(400, "Host nicht erlaubt.")
    cached = _THUMB_CACHE.get(url)
    if cached is None:
        rr = None
        try:
            rr = requests.get(url, timeout=8, stream=True)
            rr.raise_for_status()
            ct = rr.headers.get("Content-Type", "image/jpeg")
            # Raster images only — reject SVG (can embed script) and any non-image payload.
            if not ct.startswith("image/") or "svg" in ct.lower():
                raise HTTPException(415, "Kein Bild.")
            # Reject oversized images: trust the declared length when present, and enforce the cap
            # while streaming so a lying/absent Content-Length cannot bust the memory budget.
            declared = rr.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > _THUMB_MAX_BYTES:
                raise HTTPException(413, "Vorschau zu groß.")
            buf = bytearray()
            for chunk in rr.iter_content(8192):
                buf.extend(chunk)
                if len(buf) > _THUMB_MAX_BYTES:
                    raise HTTPException(413, "Vorschau zu groß.")
            content = bytes(buf)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "Vorschau nicht abrufbar.") from None
        finally:
            if rr is not None:
                rr.close()
        cached = (content, ct)
        if len(_THUMB_CACHE) < 2000:
            _THUMB_CACHE[url] = cached
    content, ct = cached
    return Response(content=content, media_type=ct,
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


# In production serve the built Angular SPA (frontend/dist/browser) at "/". In dev this folder
# does not exist → use `ng serve` (proxies /api). The web-component build is served the same way.
_DIST = config.FRONTEND / "dist" / "browser"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
