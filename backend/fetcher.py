"""
fetcher.py — live fetch from the edu-sharing repository for the refresh job.

Pulls the current live/facet data and writes it into the caches (config.raw_dir()) from
which truth.py builds the data truth:
  cache_facet_bezugsquellen.json   Bezugsquelle -> content count (facet)
  cache_facet_spider.json          Spider -> content count (facet)
  quellen_nodes.json               all source datasets (profile: repository.quelle_*)
  extra_nodes.json                 search-invisible source datasets (node API)
  vocab_sources.json               sources vocabulary (profile: repository.vocab_sources_url)
  replication_publisher_gap.csv    dominant publisher per Spider
  bq_previews.json, cache_meta.json

Endpoints and property names come from the repository profile. The curated inputs
(crawler.csv, korrekturen.csv) are NOT touched – they are maintained by the team.
"""
from __future__ import annotations
import csv
import json
import re
import time
import unicodedata

import requests

import config
import repo_profile


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", t)


def ensure_dirs() -> None:
    config.raw_dir().mkdir(parents=True, exist_ok=True)


def ngsearch_url() -> str:
    """NGSearch endpoint of the configured repository and metadata set (profile: repository.mds)."""
    return f"{config.REPO_URL}/edu-sharing/rest/search/v1/queries/-home-/{repo_profile.get().mds}/ngsearch"


def node_metadata_url(node_id: str) -> str:
    return f"{config.REPO_URL}/edu-sharing/rest/node/v1/nodes/-home-/{node_id}/metadata?propertyFilter=-all-"


H = {"Content-Type": "application/json", "Accept": "application/json"}
TIMEOUT = 90


def _facet(prop: str) -> tuple[dict, int]:
    """Facet map {value: count} AND the total count of all content
    (pagination.total of the ngsearchword=* query = total WLO prod inventory)."""
    body = {"criteria": [{"property": "ngsearchword", "values": ["*"]}],
            "facetLimit": 100_000, "facetMinCount": 1, "facets": [{"property": prop}]}
    r = requests.post(f"{ngsearch_url()}?contentType=ALL&maxItems=1&skipCount=0", json=body, headers=H, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    groups = d.get("facets", [])
    vals = groups[0].get("values", []) if groups else []
    total = int(d.get("pagination", {}).get("total") or 0)
    return {v["value"]: int(v.get("count") or 0) for v in vals}, total


def _fetch_quellen(progress) -> list:
    out, skip, total = [], 0, None
    while True:
        params = (f"contentType=ALL&maxItems=500&skipCount={skip}"
                  f"&propertyFilter=-all-&sortProperties=sys%3Anode-uuid&sortAscending=true")
        prof = repo_profile.get()
        body = {"criteria": [{"property": prof.quelle_property, "values": list(prof.quelle_werte)}]}
        r = requests.post(f"{ngsearch_url()}?{params}", json=body, headers=H, timeout=TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if total is None:
            total = d.get("pagination", {}).get("total", 0)
        nodes = d.get("nodes", [])
        if not nodes:
            break
        out.extend(nodes)
        skip += len(nodes)
        progress(skip, total)
        if skip >= (total or 0):
            break
        time.sleep(0.05)
    return out


def _node_uuid(n) -> str:
    ref = n.get("ref") or {}
    if ref.get("id"):
        return ref["id"]
    nu = (n.get("properties") or {}).get("sys:node-uuid")
    return (nu[0] if isinstance(nu, list) and nu else nu) or ""


def _csv_quelldatensatz_ids() -> list:
    """Node IDs from the CSV column 'Quelldatensatz (Prod)' (via the truth profiles,
    which already provide the column cleanly as internal.quelldatensatzProd)."""
    try:
        import truth
        profs = truth.load_crawler_profiles()
    except Exception:
        return []
    uuid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
    ids = []
    for prof in profs.values():
        m = uuid.search((prof.get("internal") or {}).get("quelldatensatzProd", "") or "")
        if m:
            ids.append(m.group(0))
    return list(dict.fromkeys(ids))


def _fetch_extra_nodes(existing_ids: set, progress) -> list:
    """Load search-INvisible source datasets via the node API (e.g. bpb): the node
    ID comes from the CSV. Returns node objects in the same format as quellen_nodes.json."""
    ids = [i for i in _csv_quelldatensatz_ids() if i not in existing_ids]
    out = []
    for k, nid in enumerate(ids, 1):
        try:
            r = requests.get(node_metadata_url(nid), headers=H, timeout=TIMEOUT)
            if r.status_code == 200:
                n = r.json().get("node")
                if n:
                    out.append(n)
        except Exception:
            pass
        if k % 5 == 0 or k == len(ids):
            progress(k, len(ids))
        time.sleep(0.03)
    return out


def _spider_top_publisher(spiders: dict, progress) -> None:
    items = list(spiders.keys())
    f = repo_profile.get().felder
    rows = []
    for i, sp in enumerate(items, 1):
        try:
            body = {"criteria": [{"property": f["replication_source"], "values": [sp]}],
                    "facetLimit": 100_000, "facetMinCount": 1,
                    "facets": [{"property": f["publisher"]}]}
            r = requests.post(f"{ngsearch_url()}?contentType=ALL&maxItems=1&skipCount=0", json=body, headers=H, timeout=TIMEOUT)
            if r.status_code == 200:
                groups = r.json().get("facets", [])
                vals = sorted(groups[0].get("values", []) if groups else [],
                              key=lambda v: -int(v.get("count") or 0))
                rows.append({"spider": sp, "topPublisher": vals[0]["value"] if vals else ""})
        except Exception:
            pass
        if i % 10 == 0:
            progress(i, len(items))
        time.sleep(0.03)
    with open(config.raw_dir() / "replication_publisher_gap.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["spider", "topPublisher"], delimiter=";")
        w.writeheader(); w.writerows(rows)


def _vocab() -> None:
    d = requests.get(repo_profile.get().vocab_sources_url, timeout=TIMEOUT).json()
    (config.raw_dir() / "vocab_sources.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def enrich_bq_previews(bq_facet: dict, quelle_publishers: set, progress,
                       min_count: int = 5, max_new: int = 400) -> int:
    """Fetches 1 example item per facets-only Bezugsquelle for a preview image.
    Cached incrementally in <raw>/bq_previews.json (only missing ones are fetched)."""
    fp = config.raw_dir() / "bq_previews.json"
    publisher = repo_profile.get().felder["publisher"]
    cache = {}
    if fp.exists():
        try:
            cache = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    cand = [(k, c) for k, c in bq_facet.items()
            if c >= min_count and _norm(k) not in quelle_publishers and k not in cache]
    cand.sort(key=lambda x: -x[1])
    cand = cand[:max_new]
    done = 0
    for i, (bq, _c) in enumerate(cand, 1):
        try:
            body = {"criteria": [{"property": publisher, "values": [bq]}]}
            r = requests.post(f"{ngsearch_url()}?contentType=FILES&maxItems=1&skipCount=0&propertyFilter=-all-",
                              json=body, headers=H, timeout=TIMEOUT)
            if r.status_code == 200:
                nodes = r.json().get("nodes", [])
                pv = ((nodes[0].get("preview") or {}).get("url") if nodes else "") or ""
                if pv:
                    cache[bq] = pv
                    done += 1
        except Exception:
            pass
        if i % 25 == 0:
            progress(i, len(cand))
        time.sleep(0.03)
    fp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return done


def refresh_all(progress=lambda p, m: None) -> None:
    """Full live refresh. progress(percent:int, message:str)."""
    ensure_dirs()
    raw = config.raw_dir()
    f = repo_profile.get().felder
    progress(4, "Bezugsquellen-Facette abrufen …")
    bq, prod_total = _facet(f["publisher"])
    (raw / "cache_facet_bezugsquellen.json").write_text(json.dumps(bq, ensure_ascii=False), encoding="utf-8")
    # record the real WLO prod total + data timestamp
    (raw / "cache_meta.json").write_text(json.dumps(
        {"wloProdContentTotal": prod_total, "fetchedAt": time.strftime("%Y-%m-%d %H:%M")},
        ensure_ascii=False), encoding="utf-8")

    progress(12, "Spider-Facette abrufen …")
    sp, _sp_total = _facet(f["replication_source"])
    (raw / "cache_facet_spider.json").write_text(json.dumps(sp, ensure_ascii=False), encoding="utf-8")

    progress(14, "Quelldatensätze abrufen …")
    nodes = _fetch_quellen(lambda done, total: progress(14 + int(28 * done / max(1, total)),
                                                        f"Quelldatensätze {done}/{total}"))
    (raw / "quellen_nodes.json").write_text(json.dumps(nodes, ensure_ascii=False), encoding="utf-8")

    progress(44, "Versteckte Quelldatensätze (Node-API) …")
    existing = {_node_uuid(n) for n in nodes}
    extra = _fetch_extra_nodes(existing, lambda i, n: progress(44 + int(6 * i / max(1, n)),
                                                              f"Versteckte Nodes {i}/{n}"))
    (raw / "extra_nodes.json").write_text(json.dumps(extra, ensure_ascii=False), encoding="utf-8")

    progress(52, "Dominanten Publisher je Spider ermitteln …")
    _spider_top_publisher(sp, lambda i, n: progress(52 + int(14 * i / max(1, n)), f"Spider {i}/{n}"))

    progress(66, "Vorschaubilder für Bezugsquellen …")
    qpubs = set()
    for n in nodes:
        p = n.get("properties", {}).get(f["publisher"])
        pv = (p[0] if isinstance(p, list) and p else p) if p else ""
        if pv:
            qpubs.add(_norm(pv))
    enrich_bq_previews(bq, qpubs, lambda i, n: progress(66 + int(24 * i / max(1, n)),
                                                        f"Vorschaubilder {i}/{n}"))

    progress(92, "Vokabular aktualisieren …")
    try:
        _vocab()
    except Exception:
        pass  # vocabulary is non-critical / rarely changed
    progress(95, "Live-Abruf abgeschlossen.")
