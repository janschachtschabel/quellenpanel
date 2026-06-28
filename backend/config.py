"""config.py — configuration & security.

A single place for: loading .env without an extra dependency, the team password,
shared constants and paths. Imported by all other backend modules as a
dependency-free leaf module (avoids cycles).
"""
import hmac
import os
from pathlib import Path

HERE = Path(__file__).parent
TRUTH = HERE / "data" / "truth.json"
FRONTEND = HERE.parent / "frontend"


def _load_dotenv(path):
    """Loads KEY=VALUE lines from backend/.env (without an extra dependency).
    Already-set real environment variables take precedence (setdefault)."""
    try:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


_load_dotenv(HERE / ".env")
# No default password: if QE_TEAM_PASSWORD is unset, TEAM_PW is empty and check_pw
# always fails (fail closed) — team features are disabled rather than guarded by a
# known default. Set the variable in .env (dev) or via -e (deploy) to enable them.
TEAM_PW = os.environ.get("QE_TEAM_PASSWORD", "").strip()

# Tier 1 ("Detailmodus": richer technical metadata for Steckbrief creators) is OPEN by default.
# Set QE_TIER1_PASSWORD to gate it behind a lighter, separate password (below the team password).
TIER1_PW = os.environ.get("QE_TIER1_PASSWORD", "").strip()

# Hard public lock: when truthy, the app serves ONLY tier 0 (end-user) and the tier 1/2 routes
# refuse regardless of any password — for the embedded / public deployment, so internal data is
# unreachable even if an auth check were wrong.
PUBLIC_ONLY = os.environ.get("QE_PUBLIC_ONLY", "").strip().lower() in ("1", "true", "yes", "on")

# "Spiders" that are NOT real content crawlers but WLO migration/import.
WLO_SPIDERS = {"wirlernenonline_spider", "wirlernenonline_gsheet_spider"}


def _auto_refresh_hour():
    """Local-time hour (0–23) for the optional nightly data refresh; None disables it.
    Configured via QE_AUTO_REFRESH_HOUR (e.g. "3"); invalid/unset means off."""
    raw = os.environ.get("QE_AUTO_REFRESH_HOUR", "").strip()
    return int(raw) if raw.isdigit() and 0 <= int(raw) <= 23 else None


AUTO_REFRESH_HOUR = _auto_refresh_hour()

# Repository / search endpoints — configurable so the app can run against a different
# edu-sharing repository (e.g. staging) instead of production. All live queries (content
# lookup, render links, the refresh fetch) and the per-source "view in search" link are
# built from these. NOT covered: the bundled data snapshot (truth.json) and the curated
# blacklists / overlay lists, which reflect their source repository and must be
# regenerated / adjusted manually when switching repositories.
REPO_URL = os.environ.get("QE_REPO_URL", "https://redaktion.openeduhub.net").rstrip("/")
SEARCH_URL = os.environ.get("QE_SEARCH_URL", "https://suche.wirlernenonline.de").rstrip("/")


def _allowed_origins():
    """Origins that may use a CREDENTIALED (team-cookie) cross-origin request — comma-separated
    'scheme://host[:port]' entries. Empty (default) means the team session is same-origin only."""
    raw = os.environ.get("QE_ALLOWED_ORIGINS", "").strip()
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


# Cross-origin team login. By default the API serves PUBLIC data to any origin without credentials
# (wildcard CORS) and the team session cookie is same-origin only (SameSite=strict). To let the team
# log in from an embedded widget on a DIFFERENT origin, list those origins here: they receive an
# origin-specific, credentialed CORS grant and the login cookie is issued cross-site (SameSite=None;
# Secure → HTTPS required). Public wildcard access for every other origin is unchanged.
# Example: QE_ALLOWED_ORIGINS=https://wirlernenonline.de,https://www.wirlernenonline.de
ALLOWED_ORIGINS = _allowed_origins()


def check_pw(pw: str | None, header_pw: str | None) -> bool:
    # Constant-time compare to avoid leaking the password via response timing.
    token = (pw or header_pw or "").strip()
    return bool(TEAM_PW) and hmac.compare_digest(token.encode("utf-8"), TEAM_PW.encode("utf-8"))


def check_tier1_pw(pw: str | None, header_pw: str | None) -> bool:
    """Tier 1 access: open when QE_TIER1_PASSWORD is unset; otherwise a constant-time match."""
    if not TIER1_PW:
        return True
    token = (pw or header_pw or "").strip()
    return hmac.compare_digest(token.encode("utf-8"), TIER1_PW.encode("utf-8"))
