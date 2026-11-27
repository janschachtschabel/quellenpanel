"""tiers.py — the access-tier model that lets three audiences share one app.

Three serialization tiers over the same record:
  0  end user    — clean public minimum (no data problems, no provenance). Always open.
  1  Steckbrief  — richer public / technical metadata (provenance, field generation,
                   confidence). Open by default; optionally gated by QE_TIER1_PASSWORD.
  2  team        — internal fields + all data-problem flags + audit/export. Team password.

A request asks for a tier (?tier=); this module returns the EFFECTIVE tier = the smaller of the
requested tier and what the caller is allowed. The instance role (config.role()) caps it:
team 2, partner 1, public 0 — so a public / embedded deployment cannot serve tier 1/2 data even if
an auth check were wrong. On a partner instance tier 1 always needs QE_TIER1_PASSWORD.
"""
from fastapi import Header, Query, Request

import config
import ratelimit
import session


def max_tier(request: Request, team_pw: str | None, team_header: str | None,
             tier1_header: str | None) -> int:
    """Highest tier the caller may access. Team (cookie or password) wins; otherwise tier 1 if
    it is open or the tier-1 password matches; otherwise tier 0."""
    role = config.role()
    cap = config.ROLE_MAX_TIER[role]
    if cap == 0:
        return 0
    if role == "team" and (session.valid(request.cookies.get(session.COOKIE))
                           or _team_pw_ok(request, team_pw or team_header)):
        return 2
    if role == "partner":
        # Fail-closed: without a configured partner password tier 1 stays shut on this instance.
        ok = bool(config.TIER1_PW) and _tier1_pw_ok(request, tier1_header)
        return 1 if ok else 0
    if not config.TIER1_PW or _tier1_pw_ok(request, tier1_header):  # tier 1 open, or pw matches
        return min(1, cap)
    return 0


def _team_pw_ok(request: Request, given: str | None) -> bool:
    """A sent team password, checked within the client's failure budget (ratelimit.pw_check)."""
    return bool(given) and ratelimit.pw_check(request, lambda: config.check_pw(None, given))


def _tier1_pw_ok(request: Request, given: str | None) -> bool:
    return bool(given) and ratelimit.pw_check(request, lambda: config.check_tier1_pw(None, given))


def effective_tier(
    request: Request,
    tier: int = Query(0, ge=0, le=2, description="Requested view tier (0 end user, 1 Steckbrief, 2 team)"),
    x_team_password: str | None = Header(None),
    x_tier1_password: str | None = Header(None),
) -> int:
    """FastAPI dependency: the tier actually granted for this request (min of requested + allowed).
    Passwords are read ONLY from headers (never a URL query parameter), so they cannot leak into logs."""
    return min(tier, max_tier(request, None, x_team_password, x_tier1_password))


def is_team(request: Request, x_team_password: str | None = Header(None)) -> bool:
    """Team authorization for write/export/audit routes (session cookie or team password header)."""
    if config.role() != "team":
        return False
    return session.valid(request.cookies.get(session.COOKIE)) or _team_pw_ok(request, x_team_password)
