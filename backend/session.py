"""session.py — short-lived team sessions backed by an httpOnly cookie, so the browser
never stores the team password (an XSS cannot read the session token). The token store
is in memory and cleared on restart — fine for a single-process internal tool.

Scaling caveat: because the store is per-process, team sessions are NOT shared across
multiple workers or serverless instances (a request hitting another worker would not find
the token and fall back to a 403 until re-login). Run this app single-process (the default
uvicorn command / one container); for a horizontally scaled deployment replace this with a
shared store (e.g. Redis) or stateless signed tokens."""
import secrets
import time

COOKIE = "qe_session"
TTL = 12 * 3600                     # session lifetime in seconds
_tokens: dict[str, float] = {}     # token -> expiry (epoch seconds)


def issue() -> str:
    """Create a new session token and remember it until it expires."""
    token = secrets.token_urlsafe(32)
    _tokens[token] = time.time() + TTL
    return token


def valid(token: str | None) -> bool:
    """True if the token is a live (unexpired) session. Lazily evicts expired tokens."""
    if not token:
        return False
    exp = _tokens.get(token)
    if exp is None:
        return False
    if exp < time.time():
        _tokens.pop(token, None)
        return False
    return True


def revoke(token: str | None) -> None:
    if token:
        _tokens.pop(token, None)
