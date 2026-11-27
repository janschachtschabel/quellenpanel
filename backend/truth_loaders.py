"""truth_loaders.py — reading all information sources (I/O).

Reads the curated CSVs (crawler table, corrections) and the live API caches (source
datasets, facets, vocabulary, preview images). Paths come from config (data dir first,
then the profile's starting data); property names and special cases from the repository
profile, so this module carries no repository-specific constants.
"""
from __future__ import annotations
import csv
import json
import logging
import re
import sys

import config
import field_policy as fp
import repo_profile
from korrekturen import load_korrekturen
from truth_text import (
    _age,
    _clean_q,
    _norm,
    _nurl,
    p1,
    pA,
)


log = logging.getLogger("truth")


# ---------------------------------------------------------------------------
# 1) Crawler profiles from datencrawler.csv
# ---------------------------------------------------------------------------
def load_crawler_profiles():
    path = config.crawler_csv_path()
    if not path:
        return {}
    prof = repo_profile.get()
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    line0 = text.splitlines()[0]
    sep = ";" if line0.count(";") >= line0.count(",") else ","
    rd = csv.DictReader(text.splitlines(), delimiter=sep)
    cols = rd.fieldnames or []
    # normalized column lookup
    norm_col = {_norm(c): c for c in cols}

    def col(name):
        return norm_col.get(_norm(name))

    pub_map = {col(k): v for k, v in prof.crawler_spalten.items() if col(k) and v in fp.CRAWLER_PUBLIC_KEYS}
    int_map = {col(k): v for k, v in prof.crawler_spalten.items() if col(k) and v in fp.CRAWLER_INTERNAL_KEYS}
    base_cols = set(pub_map) | set(int_map)
    # Real field-generation columns: "<Item> - <feld> – Status" (with item separator " - ").
    # Excludes base columns like "Bemerkung/Status" (no " - ").
    status_cols = [c for c in cols
                   if _norm(c).endswith("status") and " - " in c and c not in base_cols]

    profiles = {}
    for r in rd:
        spider = (r.get(col(prof.crawler_spider_spalte)) or "").strip()
        if not spider or spider.lower() in ("", "nein", "-", "none"):
            continue
        # field-generation status grouped by item
        field_gen = []
        active = 0
        for c in status_cols:
            v = (r.get(c) or "").strip()
            if not v or v.lower() == "inaktiv":
                continue
            label = re.split(r"\s[-‐-―]\s*Status\s*$", c)[0]
            parts = re.split(r"\s-\s", label, maxsplit=1)
            item = parts[0].strip()
            field = parts[1].strip() if len(parts) > 1 else label
            how = ""
            if "|" in v:
                _, how = v.split("|", 1)
                how = how.strip()
            field_gen.append({"item": item, "field": field, "status": v,
                              "how": how, "aktiv": v.lower().startswith("aktiv")})
            if v.lower().startswith("aktiv"):
                active += 1
        public = {v: (r.get(k) or "").strip() for k, v in pub_map.items()}
        internal = {v: (r.get(k) or "").strip() for k, v in int_map.items()}
        profiles[spider] = {
            "spider": spider,
            "public": public,
            "internal": internal,
            "fieldGeneration": field_gen,
            "fieldActiveCount": active,
            "hasFieldProfile": bool(field_gen),
        }
    return profiles


# ---------------------------------------------------------------------------
# 2) Live API caches
# ---------------------------------------------------------------------------
def _parse_node(n):
    prof = repo_profile.get()
    f = prof.felder
    props = n.get("properties", {})
    ref = n.get("ref") or {}
    lrt = pA(props, f["lrt"])
    gi = [v for v in pA(props, f["general_identifier"]) if prof.spider_kennung in v.lower()]
    gi_val = gi[0] if gi else ""
    crawler_spider = gi_val if (gi_val and gi_val not in prof.ignore_spiders) else ""
    oer_raw = p1(props, f["license_oer"]).lower()
    return {
        "nodeId": ref.get("id") or p1(props, f["node_uuid"]),
        "title": p1(props, f["title"]) or n.get("title") or "",
        "wwwUrl": _nurl(n.get("content", {}).get("url") or p1(props, f["www_url"])),
        "previewUrl": (n.get("preview") or {}).get("url") or "",
        "description": p1(props, f["description"]),
        "publisher": p1(props, f["publisher"]),
        "license": p1(props, f["license"]),
        "oer": oer_raw in ("true", "1") or "/oer/" in oer_raw,
        "subjects": pA(props, f["subjects"]),
        "educationalContext": pA(props, f["educational_context"]),
        "oehLrt": lrt,
        "language": p1(props, f["language"]) or p1(props, f["language_fallback"]),
        "keywords": pA(props, f["keywords"])[:12],
        "author": re.sub(r"\s*[\r\n]+\s*", ", ", p1(props, f["author"])).strip().strip(",").strip(),
        "quality": {lbl: _clean_q(p1(props, k)) for lbl, k in prof.qualitaet if _clean_q(p1(props, k))},
        "targetGroup": pA(props, f["target_group"]),
        "languageLevel": pA(props, f["language_level"]),
        "languageTarget": p1(props, f["language_target"]),
        "curriculum": [c for c in pA(props, f["curriculum"]) if c.strip().lower() != "null"],
        "fsk": p1(props, f["fsk"]),
        "ageRange": _age(props),
        "replicationSource": p1(props, f["replication_source"]),
        "generalIdentifier": gi_val,
        "crawlerSpider": crawler_spider,
        "editorialStatus": p1(props, f["editorial_status"]),
        "wfStatus": p1(props, f["wf_status"]),
        "modified": n.get("modifiedAt") or "",
        "multiType": len(lrt) > 1,
    }


def load_nodes():
    """Search-visible source datasets (quellen_nodes.json) PLUS search-INvisible
    source datasets fetched via the node API (extra_nodes.json, e.g. bpb – the
    node ID comes from the CSV column 'Quelldatensatz (Prod)')."""
    raw_dir = config.raw_dir()
    fpath = raw_dir / "quellen_nodes.json"
    if not fpath.exists():
        sys.exit(f"{fpath} fehlt – erst den Live-Abruf (fetcher.refresh_all) laufen lassen.")
    raw = json.loads(fpath.read_text(encoding="utf-8"))
    epath = raw_dir / "extra_nodes.json"
    if epath.exists():
        try:
            raw = raw + json.loads(epath.read_text(encoding="utf-8"))
        except Exception:
            pass
    out, seen = [], set()
    for n in raw:
        rec = _parse_node(n)
        nid = rec["nodeId"]
        if not nid or nid in seen:        # search-visible node wins (comes first)
            continue
        seen.add(nid)
        out.append(rec)
    return out


def load_facet(name):
    for fn in (f"cache_facet_{name}.json", f"facet_{name}.json"):
        fpath = config.raw_dir() / fn
        if fpath.exists():
            d = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(d, list):  # facet_*.json shape
                return {v["value"]: int(v["count"]) for v in d[0]["values"]}
            return d
    return {}


def load_vocab():
    fpath = config.raw_dir() / "vocab_sources.json"
    if not fpath.exists():
        return {}
    d = json.loads(fpath.read_text(encoding="utf-8"))
    out = {}
    for c in d.get("hasTopConcept", []):
        uuid = c.get("id", "").rsplit("/", 1)[-1].lower()
        lbl = (c.get("prefLabel") or {}).get("de") or (c.get("prefLabel") or {}).get("en") or ""
        out[uuid] = {"label": lbl, "url": c.get("url") or ""}
    return out


def load_bq_previews():
    """norm(Bezugsquelle) -> previewUrl (from the fetcher's preview enrichment)."""
    fpath = config.raw_dir() / "bq_previews.json"
    if not fpath.exists():
        return {}
    try:
        d = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {_norm(k): v for k, v in d.items() if v}


def load_korrektur():
    """{nodeId: {liste, bezugsquelle, spider}} from the long-format corrections CSV."""
    ks = load_korrekturen(config.korrekturen_csv_path())
    ks.melden(log)
    return ks.als_node_dict()


def load_spider_top_publisher():
    """spider -> dominant publisher (the real Bezugsquelle of the crawler content)."""
    p = config.raw_dir() / "replication_publisher_gap.csv"
    out = {}
    if not p.exists():
        return out
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    for r in csv.DictReader(text.splitlines(), delimiter=";"):
        sp = (r.get("spider") or "").strip()
        top = (r.get("topPublisher") or "").strip()
        if sp and top and _norm(top) not in repo_profile.get().platzhalter_bq:
            out[sp] = top
    return out
