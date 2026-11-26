"""exports.py — one export document per public tier (0 end user, 1 Steckbrief).

The team instance builds these from truth.json; partner/public instances load ONLY their export
and answer every request from it. Each entry is produced by the very serializers that answer the
tier today (serialize.source, views.flat, stats.*), so an instance holding only the export cannot
show anything the tier's serializer would not.

Shape (schema 1):
  {schema, tier, generatedAt, meta, stats, filters,
   items: [{id, card, detail, row?, k}]}
  card/detail  serialize.source(r, tier[, detail=True])
  row          views.flat(r, team=False) — tier 1 only (CSV/JSON export rows)
  k            filter keys: booleans plus the public value for the live example contents
Top-level keys starting with "_" are runtime caches (see export_query) and never written.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import filtering
import serialize
import stats
import views

SCHEMA = 1
TIERS = (0, 1)
_META_KEYS = ("total", "byKind", "withFieldProfile", "withNode", "totalContents", "wloProdContent",
              "generatedAt")
_REQUIRED = ("schema", "tier", "meta", "stats", "filters", "items")


def _keys(r: dict) -> dict:
    idn = r.get("identity") or {}
    flags = r.get("flags", [])
    if r.get("kind") == "crawler" and idn.get("spider"):
        contents = ["replication_source", idn["spider"]]
    else:
        value = idn.get("bezugsquelle") or r.get("name") or ""
        contents = ["publisher", value] if value else None
    return {
        "kind": r.get("kind", ""),
        "hasNode": bool(idn.get("nodeId")),
        "hasSpider": bool(idn.get("spider")),
        "hasBq": bool(idn.get("bezugsquelle")),
        "zweit": "ZWEITDATENSATZ" in flags,
        "oer": "OER" in flags,
        "fieldProfile": bool(r.get("fieldGeneration")),
        "contents": contents,
    }


def build_export(records: list[dict], meta: dict, tier: int) -> dict:
    """The export document of one public tier (0 or 1)."""
    if tier not in TIERS:
        raise ValueError(f"Export nur für Stufe 0 oder 1, nicht {tier}")
    items = []
    for r in records:
        if "BLACKLIST" in r.get("flags", []):
            continue
        it = {"id": r["id"], "card": serialize.source(r, tier),
              "detail": serialize.source(r, tier, detail=True), "k": _keys(r)}
        if tier == 1:
            it["row"] = views.flat(r, team=False)
        items.append(it)
    pub_meta = {k: meta.get(k) for k in _META_KEYS}
    if tier == 0:
        visible = filtering.filter_records(records, None, None, None, None, None, 0, None, False)
        st = stats.compute_enduser_stats(visible, pub_meta)
    else:
        st = stats.compute_stats_full(records, pub_meta)
    filters = {**stats.compute_filter_options(records), "erschliessung": []}  # exact codes are internal
    return {
        "schema": SCHEMA, "tier": tier, "generatedAt": meta.get("generatedAt", ""),
        "meta": pub_meta,
        "stats": st, "filters": filters, "items": items,
    }


def dumps(doc: dict) -> bytes:
    """Canonical compact bytes (runtime keys starting with '_' left out)."""
    clean = {k: v for k, v in doc.items() if not k.startswith("_")}
    return json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def etag(doc: dict) -> str:
    return '"' + hashlib.sha256(dumps(doc)).hexdigest() + '"'


def validate(doc: dict, tier: int) -> None:
    """Raise ValueError unless `doc` is a schema-1 export of `tier`."""
    if not isinstance(doc, dict):
        raise ValueError("Export ist kein Objekt")
    missing = [k for k in _REQUIRED if k not in doc]
    if missing:
        raise ValueError(f"Export unvollständig: {', '.join(missing)} fehlt")
    if doc["schema"] != SCHEMA:
        raise ValueError(f"Export-Schema {doc['schema']} statt {SCHEMA}")
    if doc["tier"] != tier:
        raise ValueError(f"Export der Stufe {doc['tier']} statt {tier}")
    if not isinstance(doc["items"], list):
        raise ValueError("Export: items ist keine Liste")
    for name in ("meta", "stats", "filters"):
        if not isinstance(doc[name], dict):
            raise ValueError(f"Export: {name} ist kein Objekt")
    for i, it in enumerate(doc["items"]):
        if not (isinstance(it, dict) and isinstance(it.get("id"), str)
                and all(isinstance(it.get(k), dict) for k in ("card", "detail", "k"))):
            raise ValueError(f"Export: Eintrag {i} unvollständig")


def write_doc(doc: dict, path: Path) -> None:
    """Atomic write of one export document (temp file + os.replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(dumps(doc))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_exports(records: list[dict], meta: dict, out_dir: Path) -> dict[int, str]:
    """Write stufe0.json and stufe1.json atomically; return {tier: etag}."""
    tags = {}
    for tier in TIERS:
        doc = build_export(records, meta, tier)
        write_doc(doc, Path(out_dir) / f"stufe{tier}.json")
        tags[tier] = etag(doc)
    return tags
