"""tiers.py — the access-tier model that lets three audiences share one app.

Three serialization tiers over the same record:
  0  end user    — clean public minimum (no data problems, no provenance). Always open.
  1  Steckbrief  — richer public / technical metadata (provenance, field generation,
                   confidence). Open by default; optionally gated by QE_TIER1_PASSWORD.
  2  team        — internal fields + all data-problem flags + audit/export. Team password.

A request asks for a tier (?tier=); this module returns the EFFECTIVE tier = the smaller of the
requested tier and what the caller is allowed. QE_PUBLIC_ONLY hard-caps everyone at tier 0, so a
public / embedded deployment cannot serve tier 1/2 data even if an auth check were wrong.
"""
from fastapi import Header, Query, Request

import config
import session


def max_tier(request: Request, team_pw: str | None, team_header: str | None,
             tier1_header: str | None) -> int:
    """Highest tier the caller may access. Team (cookie or password) wins; otherwise tier 1 if
    it is open or the tier-1 password matches; otherwise tier 0."""
    if config.PUBLIC_ONLY:
        return 0
    if session.valid(request.cookies.get(session.COOKIE)) or config.check_pw(team_pw, team_header):
        return 2
    if config.check_tier1_pw(None, tier1_header):  # True when tier 1 is open OR the pw matches
        return 1
    return 0


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
    if config.PUBLIC_ONLY:
        return False
    return session.valid(request.cookies.get(session.COOKIE)) or config.check_pw(None, x_team_password)
