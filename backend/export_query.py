"""export_query.py — list, detail, batch and export rows over ONE tier export (see exports.py).

Every response below tier 2 is answered from here, so it can only contain what the tier's
serializer put into the export. Mirrors the record query (app._query_records +
filtering.filter_records) for the filters available below tier 2; the team-only filters
(flag, show_blacklist, erschliessung) are ignored, exactly as they are below tier 2 today.

One documented difference: `q` searches the card text the user sees — including the curated
source supplement description — where the record query searched only the record's own text.
"""
from __future__ import annotations


def index(doc: dict) -> dict[str, dict]:
    """id -> item, built once per document (cached under a runtime key that is never written)."""
    idx = doc.get("_index")
    if idx is None:
        idx = {it["id"]: it for it in doc["items"]}
        doc["_index"] = idx
    return idx


def _contains(values, needle: str) -> bool:
    n = needle.lower()
    return any(n in str(v).lower() for v in values)


def _match(it: dict, f: dict, ql: str | None) -> bool:
    k, c = it["k"], it["card"]
    has_node = f.get("has_node")
    if k["zweit"] and has_node is not True:            # same hide rule as filtering.is_hidden_by_default
        return False
    if has_node is not None and k["hasNode"] != has_node:
        return False
    if f.get("has_bezugsquelle") is not None and k["hasBq"] != f["has_bezugsquelle"]:
        return False
    if f.get("has_spider") is not None and k["hasSpider"] != f["has_spider"]:
        return False
    if f.get("oer") is not None and k["oer"] != f["oer"]:
        return False
    if f.get("min_count") and (c.get("contentCount") or 0) < f["min_count"]:
        return False
    if f.get("only_field_profile") and not k["fieldProfile"]:
        return False
    if f.get("lrt") and not _contains(c.get("contentTypes", []), f["lrt"]):
        return False
    if f.get("subject") and not _contains(c.get("subjects", []), f["subject"]):
        return False
    if f.get("level") and not _contains(c.get("educationalContext", []), f["level"]):
        return False
    if ql:
        hay = " ".join([c.get("name", ""), c.get("bezugsquelle", ""), str(c.get("description", "")),
                        " ".join(c.get("subjects", []))]).lower()
        if ql not in hay:
            return False
    if f.get("crawler") and k["kind"] != "crawler":
        return False
    return True


def query(doc: dict, f: dict) -> list[dict]:
    """Filtered + sorted items (stable: ties keep the export order = record order)."""
    q = f.get("q") or ""
    ql = q.lower().strip() or None
    items = [it for it in doc["items"] if _match(it, f, ql)]
    if f.get("sort") == "name":
        keyfn = lambda it: (it["card"].get("name") or "").lower()  # noqa: E731
    else:
        keyfn = lambda it: it["card"].get("contentCount") or 0  # noqa: E731
    return sorted(items, key=keyfn, reverse=f.get("order", "desc") == "desc")


def page(doc: dict, f: dict, page_no: int, page_size: int) -> dict:
    """Same response shape as /api/sources below tier 2."""
    items = query(doc, f)
    total = len(items)
    start = (page_no - 1) * page_size
    return {
        "tier": doc["tier"], "total": total, "page": page_no, "pageSize": page_size,
        "pages": (total + page_size - 1) // page_size if total else 0,
        "items": [it["card"] for it in items[start:start + page_size]],
    }


def detail(doc: dict, source_id: str) -> dict | None:
    it = index(doc).get(source_id)
    return it["detail"] if it else None


def batch(doc: dict, ids: list[str]) -> list[dict]:
    idx = index(doc)
    return [idx[i]["detail"] for i in ids[:100] if i in idx]


def rows(doc: dict, f: dict) -> list[dict]:
    """Flat export rows (tier 1 only; a tier-0 export has none)."""
    return [it["row"] for it in query(doc, f) if "row" in it]


def contents_target(doc: dict, source_id: str) -> tuple[str, str] | None:
    """(profile field key, value) for the live example contents of a source."""
    it = index(doc).get(source_id)
    if not it or not it["k"].get("contents"):
        return None
    key, value = it["k"]["contents"]
    return key, value
