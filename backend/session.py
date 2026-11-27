"""session.py — short-lived team sessions in an httpOnly cookie, so the browser never stores the team
password (an XSS cannot read the session token).

The token is stateless and signed: "<exp>.<nonce>.<sig>", sig = HMAC-SHA256 over "<exp>.<nonce>"
with QE_SESSION_SECRET. Any process holding the same secret accepts it, so sessions survive restarts
and work across replicas. Without QE_SESSION_SECRET each process makes its own random secret (logged
as a warning): sessions then end on restart.

Documented limit: logout puts the nonce on a revocation list in THIS process's memory until the token
expires. On a second replica (or after a restart) a revoked token stays valid until its expiry
(at most TTL). The team instance runs as one replica (Recreate), so this holds in practice.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time

import config

COOKIE = "qe_session"
TTL = 12 * 3600                        # session lifetime in seconds
_MAX_LEN = 256
_TOKEN_RE = re.compile(r"^(\d{1,12})\.([A-Za-z0-9_-]{16,64})\.([A-Za-z0-9_-]{43})$")
_revoked: dict[str, float] = {}        # nonce -> expiry (epoch seconds)


def _sign(payload: str) -> str:
    mac = hmac.new(config.session_secret(), payload.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")


def issue() -> str:
    """A new signed session token valid for TTL seconds."""
    payload = f"{int(time.time()) + TTL}.{secrets.token_urlsafe(16)}"
    return f"{payload}.{_sign(payload)}"


def _parse(token) -> tuple[int, str] | None:
    """(exp, nonce) of a well-formed, correctly signed token; None otherwise. Never raises."""
    if not isinstance(token, str) or len(token) > _MAX_LEN:
        return None
    m = _TOKEN_RE.match(token)
    if not m:
        return None
    exp, nonce, sig = m.groups()
    if not hmac.compare_digest(sig, _sign(f"{exp}.{nonce}")):
        return None
    return int(exp), nonce


def valid(token) -> bool:
    """True for a correctly signed, unexpired, unrevoked token."""
    try:
        parsed = _parse(token)
        if parsed is None:
            return False
        exp, nonce = parsed
        return exp >= time.time() and nonce not in _revoked
    except Exception:  # noqa: BLE001 — a session check must never fail the request
        return False


def revoke(token) -> None:
    """Block a valid token until it expires (this process only, see module docstring)."""
    try:
        parsed = _parse(token)
    except Exception:  # noqa: BLE001
        return
    now = time.time()
    for n in [n for n, e in _revoked.items() if e < now]:
        _revoked.pop(n, None)
    if parsed and parsed[0] >= now:
        _revoked[parsed[1]] = parsed[0]
