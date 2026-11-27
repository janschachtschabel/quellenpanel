"""ratelimit.py — small in-process, per-client request throttles.

One place for the client-identity + rolling-window logic shared by the team-login brute-force
guard, the live-content endpoint and the thumbnail proxy. In-memory and per-process (fine for a
single-process internal tool; see session.py for the same scaling caveat). No external dependency.
"""
import time

import config
from fastapi import Request


def client_ip(request: Request) -> str:
    # Rate-limit key. Without TRUST_PROXY: the socket peer (request.client.host), never a raw
    # X-Forwarded-For — a client could rotate a forged XFF per request and get a fresh budget each
    # time. With TRUST_PROXY=1 (only behind our reverse proxy, which overwrites XFF with the real
    # remote address, see deploy/): the RIGHTMOST XFF entry, i.e. the address our proxy saw. Behind a
    # proxy that appends instead, the left entries are client-controlled; rightmost then fails safe
    # (one shared bucket per proxy hop) instead of open (a fresh budget per forged value).
    if config.trust_proxy():
        entries = [e.strip() for e in (request.headers.get("x-forwarded-for") or "").split(",")]
        entries = [e for e in entries if e]
        if entries:
            return entries[-1]
    return request.client.host if request.client else "?"


def sweep(bucket: dict[str, list[float]], window: float, now: float) -> None:
    """Drop buckets whose timestamps have all aged out, so a one-shot client IP does not leave a
    permanent entry. Bounds the memory of these in-process throttles without an external store."""
    if len(bucket) <= 2048:
        return
    for k in [k for k, ts in bucket.items() if not ts or now - ts[-1] >= window]:
        bucket.pop(k, None)


# --- Outbound-fetch throttle (public, unauthenticated) --------------------------------------
# /api/thumb and /api/sources/{id}/contents each trigger ONE upstream request (repo image / NGSearch)
# per call, without auth. A per-client budget stops an anonymous caller from using them to hammer the
# upstream repository (DoS amplification). Generous enough for a legitimate burst — a page of tiles
# backfilling previews via /contents — while capping sustained abuse. FETCH_MAX is module-level so
# tests can lower it.
FETCH_HITS: dict[str, list[float]] = {}
FETCH_WINDOW = 60.0
FETCH_MAX = 600      # requests per window per client across the two fetch endpoints


def fetch_rate_ok(request: Request) -> bool:
    """Record one fetch-endpoint hit for the client and report whether it is within budget."""
    ip = client_ip(request)
    now = time.time()
    hits = [t for t in FETCH_HITS.get(ip, []) if now - t < FETCH_WINDOW]
    hits.append(now)
    FETCH_HITS[ip] = hits
    sweep(FETCH_HITS, FETCH_WINDOW, now)
    return len(hits) <= FETCH_MAX


# --- Password failure budget --------------------------------------------------------------------
# One budget per client for EVERY password check (team login, X-Team-Password, X-Tier1-Password), so a
# header on an ordinary read route cannot be used to guess around the login throttle. Once used up,
# a password is not even compared until the window rolls on: a right guess looks like a wrong one.
PW_FAILS: dict[str, list[float]] = {}
PW_WINDOW = 300.0
PW_MAX_FAILS = 8


def _pw_fails(request: Request, now: float) -> tuple[str, list[float]]:
    ip = client_ip(request)
    sweep(PW_FAILS, PW_WINDOW, now)
    return ip, [t for t in PW_FAILS.get(ip, []) if now - t < PW_WINDOW]


def pw_retry_after(request: Request) -> int:
    """Seconds until this client may try a password again; 0 = budget left."""
    now = time.time()
    _, fails = _pw_fails(request, now)
    if len(fails) < PW_MAX_FAILS:
        return 0
    return max(1, int(PW_WINDOW - (now - fails[0])) + 1)


def pw_check(request: Request, check) -> bool:
    """Run check() (a password comparison) within the client's failure budget."""
    if pw_retry_after(request):
        return False
    ok = bool(check())
    ip = client_ip(request)
    if ok:
        PW_FAILS.pop(ip, None)
    else:
        PW_FAILS.setdefault(ip, []).append(time.time())
    return ok
