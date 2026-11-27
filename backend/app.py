"""app.py — Quellenpanel: one API, three audience tiers over the shared data-truth engine.

Tier 0 (end user) is the default and always open; tier 1 (Steckbrief: richer technical metadata)
is open by default and optionally password-gated; tier 2 (team: internal fields, data-problem
filters, audit/export) needs the team password. Each request is served at the EFFECTIVE tier
(see tiers.py) — the smaller of what it asked for and what it is allowed. The instance role
(QE_ROLE team/partner/public) caps it; below tier 2 every answer comes from the tier export
(exports.py / export_query.py), so it can only contain what the tier's serializer emitted.

This module is the thin web layer; logic lives in the domain modules (store, filtering, stats,
serialize, refresh, wlo_content) and the access policy in tiers.py / config.py / field_policy.py.
"""
import csv
import io
import logging
import re
import time
import urllib.error
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
import bootstrap
import embed
import enduser
import errors
import export_query
import exports as exports_mod
import export_store
import filtering
import openapi_doku
import protokoll
import ratelimit
import repo_profile
import refresh
import serialize
import session
import stats as stats_mod
import stats_team as stats_team_mod
import thumb
import team_routes
import tiers
import views
import obs
import wlo_content
from store import _DATA, family_count, load as _load, related_sources
from team_routes import require_team_role

log = logging.getLogger("quellenpanel")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Configure logging here (not at import): JSON lines on stdout per Diensteleitfaden.
    obs.setup_logging()
    role = config.role()                  # fail fast on an invalid QE_ROLE
    if role == "partner" and not config.TIER1_PW:
        log.warning("Rolle partner ohne QE_TIER1_PASSWORD: Stufe 1 (Details, Steckbrief) bleibt gesperrt")
    if role == "team":
        _DATA.update({"meta": {}, "records": [], "byId": {}, "byFamily": {}})
        if bootstrap.start_team() == "ready":
            log.info("Quellenpanel: %d records loaded", len(_DATA["records"]))
        refresh.start_scheduler(config.AUTO_REFRESH_HOUR)  # optional nightly refresh (daemon; no-op if unset)
    else:
        _start_from_export(role)
    yield
    if refresh.status().get("status") == "running":     # shutdown mid-rebuild: leave a readable trace
        bootstrap.write_status({**refresh.status(), "status": "abgebrochen",
                                "finishedAt": time.strftime("%Y-%m-%d %H:%M:%S")})


def _role_tiers(role: str) -> tuple[int, ...]:
    return tuple(range(config.ROLE_MAX_TIER[role] + 1))


def _start_from_export(role: str) -> None:
    """Partner/public: hold ONLY the export(s) of this role — never the merged records."""
    export_store.reset()
    _DATA.update({"meta": {}, "records": [], "byId": {}, "byFamily": {}})
    tiers_needed = _role_tiers(role)
    if config.export_source():
        for t in tiers_needed:
            export_store.load_tmp(t)          # last copy first (fast restart), then the source
            export_store.load_remote(t)
        export_store.start_polling(tiers_needed, config.export_poll_minutes())
    else:
        # Local development only (the image carries no data): build the exports once from a local
        # truth.json, then drop the records so only the export stays in memory.
        if not config.truth_path().is_file():
            log.error("Rolle %s ohne QE_EXPORT_SOURCE und ohne truth.json: keine Daten", role)
            return
        log.warning("Rolle %s ohne QE_EXPORT_SOURCE: Export einmalig aus der lokalen truth.json", role)
        _load()
        for t in tiers_needed:
            export_store.set_doc(t, exports_mod.build_export(_DATA["records"], _DATA["meta"], t))
        _DATA.update({"meta": {}, "records": [], "byId": {}, "byFamily": {}})
    log.info("Quellenpanel (%s): Export Stufe %s %s", role, max(tiers_needed),
             "geladen" if export_store.current(max(tiers_needed)) else "fehlt")


app = FastAPI(title="Quellenpanel", version=config.VERSION, lifespan=_lifespan)
errors.install(app)
app.include_router(thumb.router)   # /api/thumb — repository preview-image proxy (see thumb.py)

# CORS: PUBLIC (read-only) data is served to ANY origin WITHOUT credentials (wildcard). The team
# session cookie is only honoured for origins on the explicit trust list (config.ALLOWED_ORIGINS),
# which get an origin-specific, credentialed grant so an embedded widget can log in cross-origin —
# without turning the API into a credentialed open-CORS endpoint.
_CORS_METHODS = "GET, POST, PUT, DELETE, OPTIONS"
_CORS_REQ_HEADERS = "Content-Type, X-Team-Password, X-Tier1-Password, X-Zuordnung"

# Reject request bodies larger than this before they are buffered/parsed (defence in depth; a
# reverse proxy should cap too). Generous vs. the largest legitimate body (a batch of 100 ids).
_MAX_BODY_BYTES = 1_000_000


_NO_DATA_NEEDED = {"/api/health", "/api/capabilities", "/api/auth", "/api/auth/status", "/api/logout"}


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
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        cl = request.headers.get("content-length")
        limit = (team_routes.MAX_UPLOAD_BYTES if request.url.path.startswith("/api/team/")
                 else _MAX_BODY_BYTES)
        if cl and cl.isdigit() and int(cl) > limit:
            return errors.response(413, "Anfrage zu groß.", headers=_cors_headers(origin))
    # CORS preflight: the API declares no OPTIONS routes, so answer it here.
    if request.method == "OPTIONS" and origin is not None:
        headers = _cors_headers(origin)
        headers["Access-Control-Allow-Methods"] = _CORS_METHODS
        headers["Access-Control-Allow-Headers"] = _CORS_REQ_HEADERS
        headers["Access-Control-Max-Age"] = "600"
        return Response(status_code=204, headers=headers)
    # Team instance still building its first data set: data routes answer 503 with a retry hint.
    if (request.url.path.startswith("/api/") and request.url.path not in _NO_DATA_NEEDED
            and not request.url.path.startswith("/api/team/")
            and config.role() == "team" and not _DATA["records"]):
        resp = errors.response(503, "Daten werden aufgebaut", headers={"Retry-After": "60"}, retryAfter=60)
        for k, v in _cors_headers(origin).items():
            resp.headers[k] = v
        return resp
    resp = await call_next(request)
    for k, v in _cors_headers(origin).items():
        resp.headers[k] = v
    p = request.url.path
    if p.startswith("/api/") or p.startswith("/jobs/"):
        resp.headers["Cache-Control"] = "no-store"
    elif p == "/" or p.endswith((".js", ".css", ".html", ".svg")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    # Never let a browser MIME-sniff a response into a different content type (defence in depth).
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


def _rebuild_exports() -> None:
    """Team: tier-0/1 exports from the merged records (memory + $QE_DATA_DIR/exports/)."""
    export_store.rebuild_from_records(_DATA["records"], _DATA["meta"], config.data_dir() / "exports")


def _export(tier: int) -> dict:
    """The export every response below tier 2 is answered from."""
    doc = export_store.current(tier)
    if doc is None:
        raise errors.UpstreamError(503, "Daten werden geladen", 60)
    return doc


_TEAM_ONLY = [Depends(require_team_role)]


@app.get("/api/health")
def health():
    role = config.role()
    if role == "team":
        return {"status": "ok", "records": len(_DATA["records"])}
    docs = [export_store.current(t) for t in _role_tiers(role)]
    # Readiness probe (8080). It checks only the pod's OWN data, no external service: "ok" once EVERY
    # tier of the role is loaded (0 carries most traffic). Until then 503, so a rolling update with the
    # team down does not replace old pods that still serve the last valid export.
    if any(d is None for d in docs):
        return JSONResponse({"status": "starting", "role": role}, status_code=503)
    return {"status": "ok", "records": len(docs[0]["items"]), "role": role}


@app.get("/api/capabilities")
def capabilities(request: Request, x_team_password: str | None = Header(None),
                 x_tier1_password: str | None = Header(None)):
    """What the UI may offer: the highest tier this caller can reach, whether tier 1 is gated, and
    whether team login is possible at all (drives the header tier controls)."""
    return {
        "maxTier": tiers.max_tier(request, None, x_team_password, x_tier1_password),
        "role": config.role(),
        "publicOnly": config.public_only(),
        "tier1Gated": bool(config.TIER1_PW) or config.role() == "partner",
        "teamAvailable": bool(config.TEAM_PW) and config.role() == "team",
        "repoUrl": config.REPO_URL,   # which edu-sharing repo the data refers to (repo-neutral)
        "branding": _branding(),
    }


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _branding() -> dict:
    """Brand colours from the profile ([branding] in profil.toml); only valid #rrggbb values."""
    b = repo_profile.get().branding
    return {k: b[k] for k in ("primary", "accent") if isinstance(b.get(k), str) and _HEX.match(b[k])}


@app.get("/api/meta/filters")
def filter_options(tier: int = Depends(tiers.effective_tier)):
    if tier >= 2:
        return stats_mod.compute_filter_options(_DATA["records"])
    return _export(tier)["filters"]


def _filters(
    q: str = "",
    subject: str = "",
    level: str = "",
    erschliessung: str = "",
    oer: bool | None = Query(None),
    crawler: bool | None = Query(None),
    min_count: int = Query(1, ge=0),
    flag: str | None = Query(None),
    show_blacklist: bool = Query(False),
    sort: str = Query("contentCount", pattern="^(contentCount|name)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    only_field_profile: bool = Query(False),
    has_node: bool | None = Query(None),
    has_bezugsquelle: bool | None = Query(None),
    has_spider: bool | None = Query(None),
    lrt: str = "",
) -> dict:
    """The list/export filter dimensions declared ONCE (FastAPI dependency), so the list and both
    exports share one query definition — an export always matches the on-screen list, and a new
    filter is added in a single place. Returned as a plain dict spread into `_query_records`."""
    return {"q": q, "subject": subject, "level": level, "erschliessung": erschliessung, "oer": oer,
            "crawler": crawler, "min_count": min_count, "flag": flag, "show_blacklist": show_blacklist,
            "sort": sort, "order": order, "only_field_profile": only_field_profile, "has_node": has_node,
            "has_bezugsquelle": has_bezugsquelle, "has_spider": has_spider, "lrt": lrt}


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
    f: dict = Depends(_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=200),
):
    if tier < 2:
        return export_query.page(_export(tier), f, page, page_size)
    if tier >= 2 and not f["flag"] and not f["show_blacklist"]:
        # Default Audit view: fetch the hidden-REVEALED set ONCE (same filters, incl. lrt), then
        # split it into the visible list and the filter-scoped hidden breakdown — so we never run
        # the full filter twice. The split uses the same central rule (filtering.is_hidden_by_default)
        # that filter_records applies, so the visible list is byte-for-byte what the default query
        # would have returned. ZWEITDATENSATZ stay visible in the Quelldatensatz view (has_node=True).
        full = _query_records(tier, **{**f, "show_blacklist": True})
        recs = [r for r in full if not filtering.is_hidden_by_default(r, f["has_node"])]
        hb = filtering.hidden_breakdown(full, f["has_node"])
        hidden = {"blacklist": hb["blacklist"], "mehrfach": hb["zweitDatensatz"], "total": hb["total"]}
    else:
        recs = _query_records(tier, **f)
        # A team view with an explicit flag / show_blacklist already reveals everything → nothing is
        # hidden; below tier 2 the breakdown is not exposed at all.
        hidden = {"blacklist": 0, "mehrfach": 0, "total": 0} if tier >= 2 else None
    total = len(recs)
    start = (page - 1) * page_size
    items = [serialize.source(r, tier, family=family_count(r) if tier >= 2 else 0)
             for r in recs[start:start + page_size]]
    resp = {
        "tier": tier, "total": total, "page": page, "pageSize": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0, "items": items,
    }
    if hidden is not None:
        resp["hidden"] = hidden
    return resp


@app.get("/api/sources/{source_id:path}/contents")
def source_contents(request: Request, source_id: str, max_items: int = Query(12, ge=1, le=50),
                    skip: int = Query(0, ge=0), team: bool = Depends(tiers.is_team)):
    """Live example content of a source (NGSearch) — public, all tiers. Crawlers are matched by
    the replication-source property (the spider), other sources by the publisher property."""
    if not ratelimit.fetch_rate_ok(request):
        raise errors.UpstreamError(429, "Zu viele Anfragen. Bitte kurz warten.", int(ratelimit.FETCH_WINDOW))
    f = repo_profile.get().felder
    r = _DATA["byId"].get(source_id) if team else None
    if r:                                   # team login: full record (incl. hidden ones)
        idn = r.get("identity") or {}
        if r.get("kind") == "crawler" and idn.get("spider"):
            prop, value = f["replication_source"], idn["spider"]
        else:
            prop, value = f["publisher"], idn.get("bezugsquelle") or r.get("name") or ""
    else:                                   # everyone else: only what the public export shows
        doc = _export(0)
        if source_id not in export_query.index(doc):
            raise HTTPException(404, "Quelle nicht gefunden")
        target = export_query.contents_target(doc, source_id)
        prop, value = (f[target[0]], target[1]) if target else ("", "")
    if not value:
        return {"total": 0, "nodes": []}
    try:
        return wlo_content.fetch_contents(prop, value, max_items, skip)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:                 # the repository rate-limits us: pass its wait time on
            raise errors.UpstreamError(429, "Repository ausgelastet. Bitte später erneut versuchen.",
                                       errors.parse_retry_after((exc.headers or {}).get("Retry-After"))) from None
        if 400 <= exc.code < 500:           # our request was refused: waiting will not help
            raise HTTPException(502, _UPSTREAM_MSG) from None
        raise errors.UpstreamError(502, _UPSTREAM_MSG) from None
    except Exception:  # noqa: BLE001 — live API is best-effort; never 500 the detail
        raise errors.UpstreamError(502, _UPSTREAM_MSG) from None


_UPSTREAM_MSG = "Inhalte des Repositorys derzeit nicht abrufbar"


@app.get("/api/sources/{source_id:path}")
def source_detail(source_id: str, tier: int = Depends(tiers.effective_tier)):
    if tier < 2:
        d = export_query.detail(_export(tier), source_id)
        if d is None:
            raise HTTPException(404, "Quelle nicht gefunden")
        return d
    r = _DATA["byId"].get(source_id)
    if not r:
        raise HTTPException(404, "Quelle nicht gefunden")
    # The Bezugsquelle family is Audit-tier only (see serialize.source) — compute it only then.
    related = related_sources(r) if tier >= 2 else None
    return serialize.source(r, tier, detail=True, related=related)


# --- Team-login brute-force throttle --------------------------------------------------------
# Per-client failure budget (in-memory; single-process internal tool). A correct login clears it;
# too many wrong tries within the rolling window get a 429 until they roll off — turning the team
# password from "online-bruteforceable" into "not" without an external dependency.
_LOGIN_FAILS = ratelimit.PW_FAILS     # one budget for every password check (see ratelimit)
_LOGIN_WINDOW = ratelimit.PW_WINDOW
_LOGIN_MAX_FAILS = ratelimit.PW_MAX_FAILS


@app.post("/api/auth", dependencies=_TEAM_ONLY)
def auth(request: Request, response: Response, x_team_password: str | None = Header(None)):
    """Team login → httpOnly session cookie (so the password is never stored client-side).
    The password is accepted ONLY via the X-Team-Password header, never as a URL query
    parameter, so it cannot leak into proxy/access logs or browser history. Wrong attempts from one
    client share one failure budget with every other password check (429 when it is used up)."""
    retry = ratelimit.pw_retry_after(request)
    if retry:
        raise errors.UpstreamError(429, "Zu viele Fehlversuche. Bitte später erneut versuchen.", retry)
    if config.role() != "team" or not ratelimit.pw_check(
            request, lambda: config.check_pw(None, x_team_password)):
        raise HTTPException(403, "Falsches Passwort.")
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
@app.get("/api/stats")
def stats(tier: int = Depends(tiers.effective_tier)):
    """Statistics OVERVIEW: end-user figures (tier 0) or the full extended view (tier >= 1).
    The team's data-problem addendum is a separate, team-gated endpoint (/api/stats/team), so the
    team stats view is "full overview + problem section", mirroring the Quellensteckbriefe app."""
    if tier >= 2:
        return stats_mod.compute_stats_full(_DATA["records"], _DATA["meta"])
    return _export(tier)["stats"]


@app.get("/api/kennzahl")
def kennzahl(f: dict = Depends(_filters)):
    """Public key figure for widgets (always tier 0): number of sources and their contents."""
    items = export_query.query(_export(0), f)
    return {"quellen": len(items), "inhalte": sum(int(it["card"].get("contentCount") or 0) for it in items)}


@app.get("/embed/{name}", include_in_schema=False)
def embed_page(name: str, request: Request):
    return embed.seite(name, dict(request.query_params))


@app.get("/api/stats/team", dependencies=_TEAM_ONLY)
def stats_team(team: bool = Depends(tiers.is_team)):
    """Team-only data-problem / origin / spider / fill-level analysis, appended to the overview in
    the Audit tier. Fail-closed: no team login -> 403 (never leaks the problem breakdown)."""
    if not team:
        raise HTTPException(403, "Team-Login erforderlich.")
    return stats_team_mod.compute_stats_team(_DATA["records"], _DATA["meta"])


# ---------------------------------------------------------------------------
# Export — leak-safe flat view of the visible set; a data-work feature (tier 1+).
# ---------------------------------------------------------------------------
def _export_rows(tier: int, f: dict) -> list[dict]:
    """Flat rows: tier 1 from the export, tier 2 (team) from the records with every flag."""
    if tier < 2:
        return export_query.rows(_export(tier), f)
    return [views.flat(r, team=True) for r in _query_records(tier, **f)]


@app.get("/api/export.json")
def export_json(tier: int = Depends(tiers.effective_tier), f: dict = Depends(_filters)):
    if tier < 1:
        raise HTTPException(403, "Export ab Detailmodus.")
    rows = _export_rows(tier, f)
    return JSONResponse(rows, headers={"Content-Disposition": "attachment; filename=quellen_export.json"})


@app.get("/api/export.csv")
def export_csv(tier: int = Depends(tiers.effective_tier), f: dict = Depends(_filters)):
    if tier < 1:
        raise HTTPException(403, "Export ab Detailmodus.")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=views.EXPORT_COLS, delimiter=";", extrasaction="ignore")
    w.writeheader()
    for row in _export_rows(tier, f):
        w.writerow(views.csv_zeile(row))
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=quellen_export.csv"})


# ---------------------------------------------------------------------------
# Team only: data-problem protocol, multi-source PDF data, live refresh, reload.
# ---------------------------------------------------------------------------
@app.get("/api/protokoll.md", dependencies=_TEAM_ONLY)
def protokoll_md(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Nur intern (Team-Login nötig).")
    md = protokoll.build_protokoll(_DATA["records"], _DATA["meta"])
    return Response(md, media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=fehler-protokoll.md"})


@app.get("/api/protokoll.json", dependencies=_TEAM_ONLY)
def protokoll_json(team: bool = Depends(tiers.is_team)):
    """Machine-readable data-problem protocol (uncapped) — for consumption by other applications."""
    if not team:
        raise HTTPException(403, "Nur intern (Team-Login nötig).")
    data = protokoll.build_protokoll_data(_DATA["records"], _DATA["meta"])
    return JSONResponse(data, headers={"Content-Disposition": "attachment; filename=fehler-protokoll.json"})


@app.get("/api/protokoll.csv", dependencies=_TEAM_ONLY)
def protokoll_csv(team: bool = Depends(tiers.is_team)):
    """The protocol as FLAT rows (one line per category × case) — the spreadsheet-friendly shape."""
    if not team:
        raise HTTPException(403, "Nur intern (Team-Login nötig).")
    data = protokoll.build_protokoll_data(_DATA["records"], _DATA["meta"])
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["kennung", "rubrik", "quelle", "nodeId", "bezugsquelle",
                                        "inhalte", "fixHinweis"], delimiter=";")
    w.writeheader()
    for cat in data["categories"]:
        for c in cat["cases"]:
            w.writerow(views.csv_zeile({"kennung": cat["key"], "rubrik": cat["title"], "quelle": c["name"],
                                        "nodeId": c["nodeId"], "bezugsquelle": c["bezugsquelle"],
                                        "inhalte": c["contentCount"], "fixHinweis": c["detail"] or ""}))
    return StreamingResponse(iter(["﻿" + buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=fehler-protokoll.csv"})


@app.post("/api/sources/batch")
def sources_batch(ids: list[str] = Body(..., embed=True), tier: int = Depends(tiers.effective_tier)):
    """Several records at the granted tier — feeds the client-side multi-source PDF export."""
    if tier < 2:
        return {"items": export_query.batch(_export(tier), ids)}
    out = []
    for i in ids[:100]:
        r = _DATA["byId"].get(i)
        if r:
            out.append(serialize.source(r, tier, detail=True))
    return {"items": out}


@app.post("/jobs/refresh", dependencies=[*_TEAM_ONLY, Depends(team_routes.herkunft_pruefen)])
def jobs_refresh(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Team-Login erforderlich.")
    return refresh.start()


@app.get("/jobs/latest")
def jobs_latest():
    return refresh.status()


@app.post("/api/admin/reload", dependencies=[*_TEAM_ONLY, *team_routes.SCHREIBEN])
def admin_reload(team: bool = Depends(tiers.is_team)):
    if not team:
        raise HTTPException(403, "Nur intern.")
    _load()
    enduser.reload_supplements()
    _rebuild_exports()
    return {"ok": True, "meta": _DATA["meta"]}


app.include_router(team_routes.router)


# Registered LAST so it wraps every other middleware (add_middleware inserts outermost): trace
# context, response headers and the request line also cover the 413 / CORS-preflight answers.
app.add_middleware(obs.TraceMiddleware, on_error=errors.internal_error_parts)

# In production serve the built Angular SPA (frontend/dist/browser) at "/". In dev this folder
# does not exist → use `ng serve` (proxies /api). The web-component build is served the same way.
_DIST = config.FRONTEND / "dist" / "browser"

# ---- OpenAPI per role: an instance documents only what it serves --------------------------------
_OPENAPI_DESCRIPTION = (
    "Quellenpanel beschreibt die Quellen eines edu-sharing-Repositorys: als öffentliche Quellenliste "
    "mit Widgets (Stufe 0), als Steckbrief für Partner mit Passwort (Stufe 1) und als internes "
    "Team-Audit (Stufe 2). Jede Instanz läuft in genau einer Rolle (QE_ROLE = public, partner oder "
    "team) und beschreibt hier nur deren Pfade; Health, Readiness und Metriken liegen auf dem internen "
    "Port 9090.")
_openapi_cache: dict[str, dict] = {}


def _is_team_only(route) -> bool:
    return any(getattr(d, "dependency", None) is require_team_role
               for d in getattr(route, "dependencies", []) or [])


def _openapi() -> dict:
    role = config.role()
    if role not in _openapi_cache:
        from fastapi.openapi.utils import get_openapi
        routes = [r for r in app.routes
                  if not getattr(r, "path", "").startswith("/internal")
                  and (role == "team" or not _is_team_only(r))]
        _openapi_cache[role] = openapi_doku.ergaenze(
            get_openapi(title="Quellenpanel", version=config.VERSION,
                        description=_OPENAPI_DESCRIPTION, routes=routes))
    return _openapi_cache[role]


app.openapi = _openapi

_WIDGETS = config.FRONTEND / "dist-widgets"
if _WIDGETS.is_dir():
    app.mount("/widgets", StaticFiles(directory=str(_WIDGETS)), name="widgets")

if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
