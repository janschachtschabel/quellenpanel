"""truth_text.py — text normalization & small parser/vocabulary helpers.

Pure functions (no I/O): normalization of names/URLs, property access on
edu-sharing nodes, and resolution of spider/vocabulary identifiers. Shared
leaf module for truth_loaders and truth (avoids cycles).
"""
from __future__ import annotations
import re
import unicodedata

# Spiders that are NOT a real crawler binding but the migration origin of the
# dataset node (wirlernenonline_spider) -> do not anchor as a crawler.
IGNORE_SPIDERS = {"wirlernenonline_spider"}

PLACEHOLDER_BQ = {"wirlernenonline"}

# Node ID from a render/component link (CSV column 'Quelldatensatz (Prod)')
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def _node_id_from_url(url):
    m = _UUID_RE.search(url or "")
    return m.group(0) if m else ""


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def _represents(name, bq):
    """True if the title represents the Bezugsquelle (= a real source dataset)
    and not an individual item below it. Matches on a substring in either
    direction OR an overlap of significant word stems (>=4 chars, accent/case-insensitive)."""
    n, b = _norm(name), _norm(bq)
    if not n or not b:
        return False
    if b in n or n in b:
        return True
    nt = {w for w in re.findall(r"\w+", n) if len(w) >= 4}
    bt = {w for w in re.findall(r"\w+", b) if len(w) >= 4}
    return bool(nt & bt)


def _nurl(u):
    if not u:
        return ""
    u = re.sub(r"^http://", "https://", str(u).strip())
    u = re.sub(r"^(https://)www\.", r"\1", u)
    return u.rstrip("/").lower()


def p1(props, key):
    v = props.get(key)
    if isinstance(v, list):
        return str(v[0]) if v and v[0] not in (None, "") else ""
    return str(v) if v not in (None, "") else ""


def pA(props, key):
    return [str(v) for v in (props.get(key) or []) if v]


def _clean_q(v):
    """Remove asterisks (jsPDF/display), normalize whitespace."""
    v = re.sub(r"[✰★☆⭐]", "", str(v or "")).strip()
    return re.sub(r"\s+", " ", v)


def _age(props):
    """Typical age range as 'x–y Jahre'; the default 0–99 (= all) is omitted."""
    af = p1(props, "ccm:educationaltypicalagerange_from")
    at = p1(props, "ccm:educationaltypicalagerange_to")
    if not af and not at:
        return ""
    if af in ("0", "") and at in ("99", ""):
        return ""
    return f"{af or '?'}–{at or '?'} Jahre"


def _is_junk_bq(bq):
    """Junk Bezugsquelle (e.g. "0", pure numbers, empty) — do not use as a source/name."""
    s = (bq or "").strip().lower()
    return s in ("", "0", "-", "–", "null", "none", "n/a", "k.a.", "keine") or s.isdigit()


def spider_vocab_name(spider, vocab):
    if spider.startswith("http"):
        return vocab.get(spider.rsplit("/", 1)[-1].lower(), {}).get("label", "")
    return ""


def _resolve_rs(rs, vocab):
    """Make replicationsource human-readable: legacy URI (…/vocabs/sources/<uuid>) → vocab name.
    Technical names (e.g. bpb_spider) and wirlernenonline_spider stay unchanged,
    so that filters/statistics can keep checking against them."""
    s = (rs or "").strip()
    if "vocabs/sources/" in s:
        uid = s.rstrip("/").rsplit("/", 1)[-1].lower()
        return (vocab.get(uid) or {}).get("label") or s
    return s
