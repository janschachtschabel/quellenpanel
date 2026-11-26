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
    # remote address, see deploy/): the FIRST XFF entry, i.e. the address our proxy saw.
    if config.trust_proxy():
        first = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        if first:
            return first
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
