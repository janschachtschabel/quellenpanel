"""store.py — in-memory data storage.

Loads the data truth (data/truth.json) into memory once and indexes it by id and by
Bezugsquelle "family" (a publisher plus its sub-channels). `_DATA` is updated in place so that
other modules that have imported it keep the same reference.
"""
import json

from config import TRUTH
from truth_text import _norm

_DATA = {"meta": {}, "records": [], "byId": {}, "byFamily": {}}

# Mirror of truth._SUBCHANNEL_SEPS (separators that introduce a sub-channel, e.g. "YouTube - X").
# Kept local on purpose so the serve path never imports the build module (truth.py pulls in
# network/fetch dependencies). Used only to read the already-validated BQ_SUBCHANNEL relationship.
_SUBCHANNEL_SEPS = (" - ", " – ", " — ", " | ")


def _parent_bezugsquelle(r):
    """The 'family' Bezugsquelle of a record: for a sub-channel (flagged BQ_SUBCHANNEL) the parent
    prefix — 'YouTube - Mathematrick' -> 'YouTube' — otherwise the record's own Bezugsquelle. The
    BQ_SUBCHANNEL flag was already validated against the real publisher set during the build."""
    bq = (r.get("identity") or {}).get("bezugsquelle") or ""
    if bq and "BQ_SUBCHANNEL" in r.get("flags", []):
        for sep in _SUBCHANNEL_SEPS:
            if sep in bq:
                return bq.split(sep)[0].strip()
    return bq


def _family_key(r):
    """Normalized grouping key so a publisher and all its sub-channels share one family."""
    return _norm(_parent_bezugsquelle(r))


def load():
    if not TRUTH.exists():
        raise RuntimeError("data/truth.json fehlt – erst truth.py laufen lassen.")
    d = json.loads(TRUTH.read_text(encoding="utf-8"))
    records = d["records"]
    by_id = {r["id"]: r for r in records}     # build the indexes first (the slow part)
    by_family = {}
    for r in records:
        k = _family_key(r)
        if k:
            by_family.setdefault(k, []).append(r)
    # then swap the keys back-to-back, indexes before records, so a concurrent request never sees
    # new records with a stale index (effectively atomic commit).
    _DATA["meta"] = d["meta"]
    _DATA["byId"] = by_id
    _DATA["byFamily"] = by_family
    _DATA["records"] = records


def family_count(r):
    """Number of OTHER sources in the same Bezugsquelle family (0 if none) — the cheap count for
    the tile/list badge. The full sibling list is `related_sources`."""
    key = _family_key(r)
    if not key:
        return 0
    n = len(_DATA["byFamily"].get(key, []))
    return n - 1 if n > 1 else 0


def related_sources(r, limit=12):
    """Other sources in the same Bezugsquelle family (publisher + its sub-channels) — e.g. all the
    YouTube channels grouped under 'YouTube'. Read-only display data: it does NOT affect any count,
    filter or aggregation (those are computed elsewhere over the records themselves). Returns None
    when the source has no Bezugsquelle or no siblings."""
    key = _family_key(r)
    if not key:
        return None
    group = [s for s in _DATA["byFamily"].get(key, []) if s["id"] != r["id"]]
    if not group:
        return None
    group.sort(key=lambda s: -(s.get("contentCount") or 0))
    return {
        "bezugsquelle": _parent_bezugsquelle(r),
        "count": len(group),
        "items": [{"id": s["id"], "name": s["name"],
                   "contentCount": s.get("contentCount") or 0,
                   "hasNode": bool((s.get("identity") or {}).get("nodeId"))}
                  for s in group[:limit]],
    }
