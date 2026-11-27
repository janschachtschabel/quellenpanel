"""gateway.py — does a request come through the services proxy of the b-api?

Diensteleitfaden 2.2: behind the b-api a service receives a delegation token `bdt_…`, by default as
`Authorization: Bearer`, or raw in the header the b-api admin configured (`delegationHeader`, here
B_API_DELEGATION_HEADER). Quellenpanel calls no b-api function, so it never forwards the token; it
only uses its PRESENCE to adapt per request, which lets one instance run with and without b-api:

  via b-api   no own login (no tier 2, no team area, team paths left out of the spec); tier 0
              anonymously, tier 1 only with X-Tier1-Password if the proxy entry allows that header
  direct      unchanged (cookies, passwords, all tiers of the role)

The token is never parsed, verified, stored or logged. Detection only ever REMOVES rights, so a
client that fakes the header gains nothing.
"""
import os

_PREFIX = "bearer bdt_"


def _delegation_header() -> str:
    return os.environ.get("B_API_DELEGATION_HEADER", "").strip().lower()


def via_bapi(request) -> bool:
    """True when the request carries a b-api delegation token (header present, value unread)."""
    custom = _delegation_header()
    if custom and request.headers.get(custom):
        return True
    return (request.headers.get("authorization") or "")[:len(_PREFIX)].lower() == _PREFIX


def name(request) -> str:
    """How the request reached the service: 'b-api' or 'direkt' (for /api/capabilities)."""
    return "b-api" if via_bapi(request) else "direkt"
