"""config.py — configuration & security.

A single place for: loading .env without an extra dependency, the team password,
shared constants and paths. Imported by all other backend modules as a
dependency-free leaf module (avoids cycles).
"""
import hmac
import logging
import os
import secrets
import tomllib
from pathlib import Path

import repo_profile

HERE = Path(__file__).parent


def _read_version(path: Path) -> str:
    """[project].version from backend/pyproject.toml (the one version source); "0.0.0" if missing."""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0"


VERSION = _read_version(HERE / "pyproject.toml")


def _revision() -> str:
    """Git commit the image was built from (build arg QE_REVISION, set by CI); "" when unknown."""
    rev = os.environ.get("QE_REVISION", "").strip()
    return "" if rev in ("", "unknown") else rev[:12]


REVISION = _revision()


def _built(path: Path) -> str:
    """Build time of the image (file BUILD_TIME, written by the Dockerfile); "" outside an image."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


BUILT = _built(HERE.parent / "BUILD_TIME")
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


# --- Data paths ---------------------------------------------------------------------------
# Read on every call (not frozen at import), so a deployment or a test can repoint them via env.
def data_dir() -> Path:
    """Writable data directory: truth.json, raw/ caches, and team-maintained crawler.csv /
    korrekturen.csv (which take precedence over the profile's starting data)."""
    return Path(os.environ.get("QE_DATA_DIR", "").strip() or HERE / "data")


def raw_dir() -> Path:
    """Live-fetch caches (written by fetcher, read by truth_loaders)."""
    return data_dir() / "raw"


def truth_path() -> Path:
    return data_dir() / "truth.json"


def _curated(name: str) -> Path | None:
    for p in (data_dir() / name, repo_profile.get().daten_dir / name):
        if p.is_file():
            return p
    return None


def crawler_csv_path() -> Path | None:
    """The crawler table: data dir first (team upload), else the profile's starting copy."""
    return _curated("crawler.csv")


def korrekturen_csv_path() -> Path | None:
    """The corrections CSV: data dir first (team edits), else the profile's starting copy."""
    return _curated("korrekturen.csv")


# No default password: if QE_TEAM_PASSWORD is unset, TEAM_PW is empty and check_pw
# always fails (fail closed) — team features are disabled rather than guarded by a
# known default. Set the variable in .env (dev) or via -e (deploy) to enable them.
TEAM_PW = os.environ.get("QE_TEAM_PASSWORD", "").strip()

# Tier 1 ("Detailmodus": richer technical metadata for Steckbrief creators) is OPEN by default.
# Set QE_TIER1_PASSWORD to gate it behind a lighter, separate password (below the team password).
TIER1_PW = os.environ.get("QE_TIER1_PASSWORD", "").strip()

# Role of this instance (one image, three deployments). The role caps the access tier:
#   team     tier 2 — builds truth.json + the per-tier exports (internal only)
#   partner  tier 1 — serves only the tier-0/1 exports; tier 1 needs QE_TIER1_PASSWORD (fail-closed)
#   public   tier 0 — serves only the tier-0 export (embeddable)
# QE_PUBLIC_ONLY=1 is the transitional alias for QE_ROLE=public.
ROLES = ("team", "partner", "public")
ROLE_MAX_TIER = {"team": 2, "partner": 1, "public": 0}


def role() -> str:
    """The instance role, read from the environment on every call (tests/deployments switch it)."""
    raw = os.environ.get("QE_ROLE", "").strip().lower()
    alias = os.environ.get("QE_PUBLIC_ONLY", "").strip().lower() in ("1", "true", "yes", "on")
    if not raw:
        return "public" if alias else "team"
    if alias and raw != "public":
        # Never fail open: an old public deployment that gains QE_ROLE=team must not unlock tiers.
        raise ValueError(f"QE_PUBLIC_ONLY=1 widerspricht QE_ROLE='{raw}'")
    if raw not in ROLES:
        raise ValueError(f"QE_ROLE='{raw}' ungültig (erlaubt: {', '.join(ROLES)})")
    return raw


def frame_ancestors() -> str:
    """CSP frame-ancestors for the /embed/* pages: QE_FRAME_ANCESTORS (space-separated sources),
    default '*' (public widgets embeddable anywhere); the internal team instance only 'self'."""
    raw = os.environ.get("QE_FRAME_ANCESTORS", "").strip()
    if raw:
        # one header value: keep only plain source tokens (no ';', quotes only around keywords)
        tokens = [t for t in raw.split() if all(c not in t for c in ";,\r\n") and len(t) < 200]
        if tokens:
            return " ".join(tokens)
    return "'self'" if role() == "team" else "*"


def public_only() -> bool:
    """Hard public lock: only tier 0 is served, whatever password is sent."""
    return role() == "public"


def export_source() -> str:
    """Partner/public: where the tier export comes from — URL or file path with '{tier}',
    e.g. http://quellenpanel-team-internal:9090/internal/exports/stufe{tier}.json (QE_EXPORT_SOURCE)."""
    return os.environ.get("QE_EXPORT_SOURCE", "").strip()


def export_poll_minutes() -> int:
    """Partner/public: re-fetch interval of the export in minutes (QE_EXPORT_POLL_MINUTES, 0 = off)."""
    raw = os.environ.get("QE_EXPORT_POLL_MINUTES", "").strip()
    return int(raw) if raw.isdigit() else 10


def thumb_cache_bytes() -> int:
    """Memory budget of the preview-image cache (QE_THUMB_CACHE_MB, default 16, 0 = off)."""
    raw = os.environ.get("QE_THUMB_CACHE_MB", "").strip()
    return (int(raw) if raw.isdigit() else 16) * 1024 * 1024


def seed_url() -> str:
    """QE_SEED_URL: base URL holding crawler.csv, korrekturen.csv and optionally truth.json."""
    return os.environ.get("QE_SEED_URL", "").strip()


_GENERATED_SECRET: bytes | None = None
_TRUE = ("1", "true", "yes", "on")


def session_secret() -> bytes:
    """HMAC key for team sessions (QE_SESSION_SECRET). Without it the team keeps a random key in
    <data dir>/session.key (created once, mode 600), so logins survive restarts; if that file cannot
    be read or written: one random key per process."""
    global _GENERATED_SECRET
    raw = os.environ.get("QE_SESSION_SECRET", "").strip()
    if raw:
        return raw.encode("utf-8")
    if _GENERATED_SECRET is None:
        _GENERATED_SECRET = _stored_secret()
    if _GENERATED_SECRET is None:
        _GENERATED_SECRET = secrets.token_bytes(32)
        logging.getLogger("quellenpanel").warning(
            "QE_SESSION_SECRET fehlt: zufälliger Schlüssel, Sitzungen überleben keinen Neustart")
    return _GENERATED_SECRET


def _stored_secret() -> bytes | None:
    """The team's key file in the data dir, created on first use; None when that is not possible."""
    if role() != "team":
        return None
    path = data_dir() / "session.key"
    try:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            key = path.read_bytes().strip()
            return key if len(key) >= 32 else None
        key = secrets.token_hex(32).encode("ascii")
        with os.fdopen(fd, "wb") as f:
            f.write(key)
        logging.getLogger("quellenpanel").info("Sitzungsschlüssel in %s angelegt", path)
        return key
    except OSError:
        return None


def trust_proxy() -> bool:
    """TRUST_PROXY: take the client IP from the rightmost X-Forwarded-For entry (set by our proxy)."""
    return os.environ.get("TRUST_PROXY", "").strip().lower() in _TRUE


# Kept for compatibility (read once at import); code paths use public_only()/role().
PUBLIC_ONLY = public_only()


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
# Defaults come from the active repository profile; QE_REPO_URL / QE_SEARCH_URL override them.
REPO_URL = (os.environ.get("QE_REPO_URL", "").strip() or repo_profile.get().repo_url).rstrip("/")
SEARCH_URL = (os.environ.get("QE_SEARCH_URL", "").strip() or repo_profile.get().search_url).rstrip("/")


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
# Example: QE_ALLOWED_ORIGINS=https://portal.example.org,https://www.portal.example.org
ALLOWED_ORIGINS = _allowed_origins()


def check_pw(pw: str | None, header_pw: str | None) -> bool:
    # Constant-time compare to avoid leaking the password via response timing.
    token = (pw or header_pw or "").strip()
    return bool(TEAM_PW) and hmac.compare_digest(token.encode("utf-8"), TEAM_PW.encode("utf-8"))


def check_tier1_pw(pw: str | None, header_pw: str | None) -> bool:
    """Tier 1 access: a constant-time match; fail-closed when QE_TIER1_PASSWORD is unset."""
    if not TIER1_PW:
        return False
    token = (pw or header_pw or "").strip()
    return hmac.compare_digest(token.encode("utf-8"), TIER1_PW.encode("utf-8"))
