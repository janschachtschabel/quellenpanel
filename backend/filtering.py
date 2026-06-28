"""filtering.py — filter logic for the source list.

Pure function over the records (no web/IO dependency). Maps the frontend's
selection dimensions; the provenance rules (real binding, WLO migration,
blacklist hiding) are documented centrally here.
"""
from config import WLO_SPIDERS
from field_policy import HIDDEN_BY_DEFAULT


def filter_records(recs, q, kind, oer, subject, level, min_count, has_node, only_field_profile,
                   license_=None, language=None, lrt=None, flag=None,
                   has_bezugsquelle=None, spider_real=False, wlo_migration=False, exclude_wlo=False,
                   show_blacklist=False, has_spider=None):
    out = []
    ql = q.lower().strip() if q else None
    for r in recs:
        # Hide problem records from the default view only. ZWEITDATENSATZ are distinct
        # source-dataset OBJECTS that merely share a Bezugsquelle tag (not real
        # duplicates), so they stay visible in the Quelldatensatz/object view
        # (has_node=True) and are only collapsed in the default + Bezugsquelle (tag)
        # view, where they would over-count distinct Bezugsquellen. Blacklist is always
        # hidden. A team filter (flag=<NAME>) or show_blacklist reveals everything.
        _hidden = ("BLACKLIST",) if has_node is True else HIDDEN_BY_DEFAULT
        if not show_blacklist and not flag \
                and any(h in r.get("flags", []) for h in _hidden):
            continue
        if kind and r["kind"] != kind:
            continue
        if has_node is not None and bool(r["identity"].get("nodeId")) != has_node:
            continue
        if has_bezugsquelle is not None and bool(r["identity"].get("bezugsquelle")) != has_bezugsquelle:
            continue
        if has_spider is not None and bool(r["identity"].get("spider")) != has_spider:
            continue
        if spider_real:
            _g = str((r.get("internal") or {}).get("general_identifier", "")).strip()
            _rs = str((r.get("internal") or {}).get("replicationsource", "")).strip()
            # real binding = general_identifier OR replicationsource != wirlernenonline_spider
            if not (_g or (_rs and _rs != "wirlernenonline_spider")):
                continue
        _sp = str(r["identity"].get("spider", "")).strip()
        if exclude_wlo and _sp in WLO_SPIDERS:
            continue
        if wlo_migration and not (
                str((r.get("internal") or {}).get("replicationsource", "")) == "wirlernenonline_spider"
                or _sp in WLO_SPIDERS):
            continue
        if oer is not None and ("OER" in r.get("flags", [])) != oer:
            continue
        if min_count and (r["contentCount"] or 0) < min_count:
            continue
        if only_field_profile and not r.get("fieldGeneration"):
            continue
        if license_ and r["public"].get("Lizenz", "") != license_:
            continue
        if language and r["public"].get("Sprache", "") != language:
            continue
        if lrt and not any(lrt.lower() in s.lower() for s in r["public"].get("Inhaltstypen", [])):
            continue
        if flag and flag not in r.get("flags", []):
            continue
        if subject and not any(subject.lower() in s.lower() for s in r["public"].get("Faecher", [])):
            continue
        if level and not any(level.lower() in s.lower() for s in r["public"].get("Bildungsstufen", [])):
            continue
        if ql:
            hay = " ".join([r["name"], r["identity"].get("bezugsquelle", ""),
                            str(r["public"].get("Beschreibung", "")),
                            " ".join(r["public"].get("Faecher", []))]).lower()
            if ql not in hay:
                continue
        out.append(r)
    return out


def hidden_breakdown(full, has_node):
    """Count, by reason, how many records the default view hides for a query — so the
    displayed total can be reconciled with the raw data. `full` is the match set with the
    default hide turned off (show_blacklist=True). Mirrors the hide rule in filter_records:
    BLACKLIST is always hidden; ZWEITDATENSATZ only outside the Quelldatensatz/object view
    (has_node=True). Returns {total, blacklist, zweitDatensatz}."""
    bl = sum(1 for r in full if "BLACKLIST" in r.get("flags", []))
    zw = (sum(1 for r in full if "ZWEITDATENSATZ" in r.get("flags", [])
              and "BLACKLIST" not in r.get("flags", []))
          if has_node is not True else 0)
    return {"total": bl + zw, "blacklist": bl, "zweitDatensatz": zw}
