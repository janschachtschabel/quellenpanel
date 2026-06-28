"""truth_loaders.py — reading all information sources (I/O).

Reads the curated CSVs (crawler profiles, correction list) and the live API
caches (source datasets, facets, vocabulary, preview images). The path anchor
is `backend/` (Path(__file__).parent) — hence a flat sibling module, not a
subpackage.
"""
from __future__ import annotations
import csv
import json
import re
import sys
from pathlib import Path

import field_policy as fp
from truth_text import (
    IGNORE_SPIDERS,
    PLACEHOLDER_BQ,
    _age,
    _clean_q,
    _norm,
    _nurl,
    p1,
    pA,
)

HERE = Path(__file__).parent


def _find(*cands):
    for c in cands:
        p = Path(c)
        if p.exists():
            return p
    return None


# --- Input paths (with fallbacks) ------------------------------------------
# Order: first the original repos (source of truth on the dev machine), last
# the bundled copy in backend/data/inputs/ — this makes the app self-contained
# (container/standalone checkout without the sibling repos).
ROOT = HERE.parents[1]                       # wlo-suche
RAW = _find(ROOT / "quellen-analyse/raw")
DATENCRAWLER = _find(
    ROOT / "Wissen/wlo-quellensteckbriefe/public/data/datencrawler.csv",
    ROOT / "Wissen/quellen-liste/data/datencrawler.csv",
    HERE / "data/inputs/datencrawler.csv",
)
KORREKTUR = _find(
    ROOT.parent / "Quellen-Steckbriefe-2026/wissen/wlo-quellenliste-api/data/quellen_korrektur.csv",
    HERE / "data/inputs/quellen_korrektur.csv",
)


# Quality/accessibility metadata (DISPLAYNAME = human-readable). Only filled ones are kept.
QUALITY_FIELDS = [
    ("Sachrichtigkeit", "ccm:oeh_quality_correctness_DISPLAYNAME"),
    ("Aktualität", "ccm:oeh_quality_currentness_DISPLAYNAME"),
    ("Neutralität", "ccm:oeh_quality_neutralness_DISPLAYNAME"),
    ("Sprachl. Angemessenheit", "ccm:oeh_quality_language_DISPLAYNAME"),
    ("Medial passend", "ccm:oeh_quality_medial_DISPLAYNAME"),
    ("Didaktik/Methodik", "ccm:oeh_quality_didactics_DISPLAYNAME"),
    ("Transparenz", "ccm:oeh_quality_transparentness_DISPLAYNAME"),
    ("Für Bildung geeignet", "ccm:oeh_quality_relevancy_for_education_DISPLAYNAME"),
    ("Jugendschutz", "ccm:oeh_quality_protection_of_minors_DISPLAYNAME"),
    ("Datenschutz (rechtl.)", "ccm:oeh_quality_data_privacy_DISPLAYNAME"),
    ("Persönlichkeitsrechte", "ccm:oeh_quality_personal_law_DISPLAYNAME"),
    ("Strafrecht", "ccm:oeh_quality_criminal_law_DISPLAYNAME"),
    ("Urheberrecht", "ccm:oeh_quality_copyright_law_DISPLAYNAME"),
    ("Login", "ccm:conditionsOfAccess_DISPLAYNAME"),
    ("Kosten", "ccm:price_DISPLAYNAME"),
    ("Werbung", "ccm:containsAdvertisement_DISPLAYNAME"),
    ("DSGVO", "ccm:dataProtectionConformity_DISPLAYNAME"),
    ("Barrierefreiheit", "ccm:accessibilitySummary_DISPLAYNAME"),
]


# ---------------------------------------------------------------------------
# 1) Crawler profiles from datencrawler.csv
# ---------------------------------------------------------------------------
def load_crawler_profiles():
    if not DATENCRAWLER:
        return {}
    text = DATENCRAWLER.read_text(encoding="utf-8-sig", errors="replace")
    line0 = text.splitlines()[0]
    sep = ";" if line0.count(";") >= line0.count(",") else ","
    rd = csv.DictReader(text.splitlines(), delimiter=sep)
    cols = rd.fieldnames or []
    # normalized column lookup
    norm_col = {_norm(c): c for c in cols}

    def col(name):
        return norm_col.get(_norm(name))

    pub_map = {col(k): v for k, v in fp.CRAWLER_PUBLIC_BASE.items() if col(k)}
    int_map = {col(k): v for k, v in fp.CRAWLER_INTERNAL_BASE.items() if col(k)}
    base_cols = set(pub_map) | set(int_map)
    # Real field-generation columns: "<Item> - <feld> – Status" (with item separator " - ").
    # Excludes base columns like "Bemerkung/Status" (no " - ").
    status_cols = [c for c in cols
                   if _norm(c).endswith("status") and " - " in c and c not in base_cols]

    profiles = {}
    for r in rd:
        spider = (r.get(col("Crawler (Spider)")) or "").strip()
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
    props = n.get("properties", {})
    ref = n.get("ref") or {}
    lrt = pA(props, "ccm:oeh_lrt_aggregated_DISPLAYNAME")
    gi = [v for v in pA(props, "ccm:general_identifier") if "spider" in v.lower()]
    gi_val = gi[0] if gi else ""
    crawler_spider = gi_val if (gi_val and gi_val not in IGNORE_SPIDERS) else ""
    oer_raw = p1(props, "ccm:license_oer").lower()
    return {
        "nodeId": ref.get("id") or p1(props, "sys:node-uuid"),
        "title": p1(props, "cclom:title") or n.get("title") or "",
        "wwwUrl": _nurl(n.get("content", {}).get("url") or p1(props, "ccm:wwwurl")),
        "previewUrl": (n.get("preview") or {}).get("url") or "",
        "description": p1(props, "cclom:general_description"),
        "publisher": p1(props, "ccm:oeh_publisher_combined"),
        "license": p1(props, "ccm:commonlicense_key"),
        "oer": oer_raw in ("true", "1") or "/oer/" in oer_raw,
        "subjects": pA(props, "ccm:taxonid_DISPLAYNAME"),
        "educationalContext": pA(props, "ccm:educationalcontext_DISPLAYNAME"),
        "oehLrt": lrt,
        "language": p1(props, "cclom:general_language_DISPLAYNAME") or p1(props, "cclom:general_language"),
        "keywords": pA(props, "cclom:general_keyword")[:12],
        "author": re.sub(r"\s*[\r\n]+\s*", ", ", p1(props, "ccm:author_freetext")).strip().strip(",").strip(),
        "quality": {lbl: _clean_q(p1(props, k)) for lbl, k in QUALITY_FIELDS if _clean_q(p1(props, k))},
        "targetGroup": pA(props, "ccm:educationalintendedenduserrole_DISPLAYNAME"),
        "languageLevel": pA(props, "ccm:oeh_languageLevel_DISPLAYNAME"),
        "languageTarget": p1(props, "ccm:oeh_languageTarget"),
        "curriculum": [c for c in pA(props, "ccm:curriculum_DISPLAYNAME") if c.strip().lower() != "null"],
        "fsk": p1(props, "ccm:fskRating_DISPLAYNAME"),
        "ageRange": _age(props),
        "replicationSource": p1(props, "ccm:replicationsource"),
        "generalIdentifier": gi_val,
        "crawlerSpider": crawler_spider,
        "editorialStatus": p1(props, "ccm:editorial_checklist_DISPLAYNAME"),
        "wfStatus": p1(props, "ccm:wf_status"),
        "modified": n.get("modifiedAt") or "",
        "multiType": len(lrt) > 1,
    }


def load_nodes():
    """Search-visible source datasets (quellen_nodes.json) PLUS search-INvisible
    source datasets fetched via the node API (extra_nodes.json, e.g. bpb – the
    node ID comes from the CSV column 'Quelldatensatz (Prod)')."""
    fpath = RAW / "quellen_nodes.json" if RAW else None
    if not fpath or not fpath.exists():
        sys.exit("quellen_nodes.json fehlt – erst quellen-analyse/analyze_sources.py laufen lassen.")
    raw = json.loads(fpath.read_text(encoding="utf-8"))
    epath = RAW / "extra_nodes.json" if RAW else None
    if epath and epath.exists():
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
        fpath = RAW / fn if RAW else None
        if fpath and fpath.exists():
            d = json.loads(fpath.read_text(encoding="utf-8"))
            if isinstance(d, list):  # facet_*.json shape
                return {v["value"]: int(v["count"]) for v in d[0]["values"]}
            return d
    return {}


def load_vocab():
    fpath = RAW / "vocab_sources.json" if RAW else None
    if not fpath or not fpath.exists():
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
    fpath = RAW / "bq_previews.json" if RAW else None
    if not fpath or not fpath.exists():
        return {}
    try:
        d = json.loads(fpath.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {_norm(k): v for k, v in d.items() if v}


def load_korrektur():
    if not KORREKTUR:
        return {}
    text = KORREKTUR.read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if text.count(";") > text.count(",") else ","
    out = {}
    for r in csv.DictReader(text.splitlines(), delimiter=sep):
        nid = (r.get("Node-Id") or "").strip()
        if nid:
            out[nid] = {"liste": (r.get("Liste") or "").strip().lower(),
                        "bezugsquelle": (r.get("Bezugsquelle") or "").strip(),
                        "spider": (r.get("Spider") or "").strip()}
    return out


def load_spider_top_publisher():
    """spider -> dominant publisher (the real Bezugsquelle of the crawler content)."""
    p = _find(ROOT / "quellen-analyse/data/replication_publisher_gap.csv")
    out = {}
    if not p:
        return out
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    for r in csv.DictReader(text.splitlines(), delimiter=";"):
        sp = (r.get("spider") or "").strip()
        top = (r.get("topPublisher") or "").strip()
        if sp and top and _norm(top) not in PLACEHOLDER_BQ:
            out[sp] = top
    return out
