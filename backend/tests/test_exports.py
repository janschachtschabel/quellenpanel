"""Exporte je Stufe: gebaut mit den Stufen-Serializern, ohne interne Felder/Flags (Etappe 2)."""
import json
import re

import pytest

import field_policy as fp
import serialize
import views
from test_golden import _reset_profile, build_golden  # noqa: F401  (autouse fixture reused)

import exports

# "spider" is also the public binding key of the tier-1 detail (binding.spider, by design in
# serialize.source); as a crawler-table column name it is internal — so it is excluded here.
BANNED_KEYS = (set(fp.NODE_INTERNAL) | set(fp.NODE_INTERNAL.values())
               | (set(fp.CRAWLER_INTERNAL_KEYS) - {"spider"})
               | {"internal", "provenance", "flags", "confidence", "related", "familyCount", "bind"})


@pytest.fixture
def golden(monkeypatch, tmp_path):
    records = build_golden(monkeypatch, tmp_path)
    # The fixture has no ZWEITDATENSATZ case; mark one visible source-dataset record as such.
    zweit = next(r for r in records if r["kind"] == "manuell" and "BLACKLIST" not in r["flags"])
    zweit["flags"] = [*zweit["flags"], "ZWEITDATENSATZ"]
    return records, meta_of(records)


def meta_of(records):
    """Same shape as truth.main() writes."""
    return {
        "total": len(records),
        "byKind": {k: sum(1 for r in records if r["kind"] == k) for k in ("crawler", "manuell", "bezugsquelle")},
        "withFieldProfile": sum(1 for r in records if r.get("fieldGeneration")),
        "withNode": sum(1 for r in records if r["identity"]["nodeId"]),
        "totalContents": sum(r.get("contentCount") or 0 for r in records if r["kind"] != "bezugsquelle"),
        "wloProdContent": 1000, "generatedAt": "2026-11-26 00:00",
    }


def _walk(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield ("key", k, path)
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(x, list):
        for v in x:
            yield from _walk(v, path)
    elif isinstance(x, str):
        yield ("str", x, path)


@pytest.mark.parametrize("tier", [0, 1])
def test_no_internal_in_export(golden, tier):
    doc = exports.build_export(*golden, tier)
    # Tier 1 keeps today's public Steckbrief identity: the node id in the export row (views.flat)
    # is a public edu-sharing render link, as in the tier-1 detail binding. Tier 0 has none of it.
    banned = BANNED_KEYS - {"nodeId"} if tier == 1 else BANNED_KEYS | {"spider", "nodeId"}
    if tier == 0:
        # The spider name is public (repository property, shown at tier 1); at tier 0 it may only
        # appear as the value for the live example contents, k.contents[1].
        spiders = {r["identity"]["spider"] for r in golden[0] if r["identity"].get("spider")}
        for it in doc["items"]:
            c = it["k"]["contents"]
            assert c is None or c[0] in ("replication_source", "publisher")
        stripped = {**doc, "items": [{**it, "k": {**it["k"], "contents": None}} for it in doc["items"]]}
        for kind, val, path in _walk(stripped):
            assert not (kind == "str" and val in spiders), f"Spider {val!r} unter {path}"
    rows = [it.pop("row") for it in doc["items"] if "row" in it]
    for kind, val, path in _walk(doc):
        if kind == "key":
            assert val not in banned, f"interner Schlüssel {val!r} unter {path}"
        assert val not in fp.INTERNAL_FLAGS, f"internes Flag {val!r} unter {path}"
    # Tier-1 export rows (views.flat, team=False): public flag set only, never the confidence.
    for row in rows:
        assert set(row) == set(views.EXPORT_COLS)
        assert set(filter(None, row["flags"].split(" | "))) <= fp.PUBLIC_FLAGS
        assert row["confidence"] == ""
    for it in doc["items"]:
        for part in ("card", "detail"):
            assert not re.match(r"^\d+\.", it[part].get("erschliessungsstatus", ""))


@pytest.mark.parametrize("tier", [0, 1])
def test_blacklist_absent_zweit_marked(golden, tier):
    records, _ = golden
    doc = exports.build_export(*golden, tier)
    by_id = {it["id"]: it for it in doc["items"]}
    black = [r["id"] for r in records if "BLACKLIST" in r["flags"]]
    zweit = [r["id"] for r in records if "ZWEITDATENSATZ" in r["flags"] and "BLACKLIST" not in r["flags"]]
    assert black and zweit, "Fixture muss beide Fälle enthalten"
    assert not set(black) & set(by_id)
    assert all(by_id[i]["k"]["zweit"] is True for i in zweit)


@pytest.mark.parametrize("tier", [0, 1])
def test_card_detail_match_serializer(golden, tier):
    records, _ = golden
    doc = exports.build_export(*golden, tier)
    by_id = {r["id"]: r for r in records}
    for it in doc["items"]:
        r = by_id[it["id"]]
        assert it["card"] == serialize.source(r, tier)
        assert it["detail"] == serialize.source(r, tier, detail=True)


def test_row_only_tier1(golden):
    assert all("row" in it for it in exports.build_export(*golden, 1)["items"])
    assert not any("row" in it for it in exports.build_export(*golden, 0)["items"])


def test_filters_without_erschliessung(golden):
    assert exports.build_export(*golden, 0)["filters"]["erschliessung"] == []


def test_tier2_rejected(golden):
    with pytest.raises(ValueError):
        exports.build_export(*golden, 2)


def test_write_exports_atomic_and_etag(golden, tmp_path):
    out = tmp_path / "exports"
    tags = exports.write_exports(*golden, out)
    for tier in (0, 1):
        doc = json.loads((out / f"stufe{tier}.json").read_text(encoding="utf-8"))
        assert exports.etag(doc) == tags[tier]
        assert tags[tier].startswith('"') and tags[tier].endswith('"')
    assert exports.write_exports(*golden, out) == tags
    assert not list(out.glob("*.tmp"))


def test_validate_rejects_wrong_tier(golden):
    doc = exports.build_export(*golden, 0)
    exports.validate(doc, 0)
    with pytest.raises(ValueError):
        exports.validate(doc, 1)
    with pytest.raises(ValueError):
        exports.validate({"schema": 1, "tier": 0}, 0)


@pytest.mark.parametrize("tier", [0, 1])
def test_blacklisted_names_nowhere_in_export(golden, tier):
    # Zwischenreview: auch Statistik-Listen (topByContent/topCrawler) nennen keine Blacklist-Quelle.
    records, _ = golden
    raw = exports.dumps(exports.build_export(*golden, tier)).decode("utf-8")
    for r in records:
        if "BLACKLIST" in r["flags"]:
            assert r["id"] not in raw and json.dumps(r["name"], ensure_ascii=False) not in raw, r["name"]


def test_stats_meta_is_whitelisted(golden):
    records, meta = golden
    doc = exports.build_export(records, {**meta, "geheim": "x"}, 1)
    assert "geheim" not in exports.dumps(doc).decode("utf-8")


def test_write_doc_unique_tmp(golden, tmp_path, monkeypatch):
    # Zwischenreview: parallele Schreiber dürfen sich die Temp-Datei nicht teilen.
    import os
    seen = []
    real = os.replace
    monkeypatch.setattr(exports.os, "replace", lambda a, b: (seen.append(str(a)), real(a, b)))
    doc = exports.build_export(*golden, 0)
    exports.write_doc(doc, tmp_path / "stufe0.json")
    exports.write_doc(doc, tmp_path / "stufe0.json")
    assert len(set(seen)) == 2


@pytest.mark.parametrize("tier", [0, 1])
def test_filter_options_ignore_blacklisted_records(golden, tier):
    # Abschluss-Audit: a subject only a blacklisted record carries must not show up publicly.
    records, meta = golden
    bl = next(r for r in records if "BLACKLIST" in r.get("flags", []))
    marker = dict(bl, public={**bl["public"], "Faecher": ["Geheimfach-XYZ"],
                              "Bildungsstufen": ["Geheimstufe-XYZ"]})
    recs = [marker if r is bl else r for r in records]
    doc = exports.build_export(recs, meta, tier)
    text = json.dumps(doc["filters"], ensure_ascii=False)
    assert "Geheimfach-XYZ" not in text and "Geheimstufe-XYZ" not in text


def test_export_source_template_with_other_braces():
    # Abschluss-Audit: a query string with other {} in QE_EXPORT_SOURCE must not crash the start.
    import export_store
    assert export_store.export_url("https://t.example/stufe{tier}.json?x={a}", 1) == \
        "https://t.example/stufe1.json?x={a}"
