"""truth.py — single-source-of-truth engine (merge step).

Merges ALL known information sources into a canonical source view
("one data truth") with per-field provenance and public/internal separation.
Inputs are read by truth_loaders, helpers come from truth_text; this module
now contains only the join/record-building logic and the build entry point.

Inputs (see truth_loaders for details):
  * Live API caches (quellen_nodes.json, facets, vocab_sources.json)
  * Curated (datencrawler.csv, quellen_korrektur.csv)

Output:
  data/truth.json                   canonical records (public + internal separated)

Join keys (precedence):
  1. Spider name  (general_identifier / replicationsource <-> Crawler(Spider) <-> Vocab)
  2. publisher_combined (Bezugsquelle)
  3. nodeId / correction list
"""
from __future__ import annotations
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import field_policy as fp
from truth_loaders import (
    DATENCRAWLER,
    KORREKTUR,
    RAW,
    load_bq_previews,
    load_crawler_profiles,
    load_facet,
    load_korrektur,
    load_nodes,
    load_spider_top_publisher,
    load_vocab,
)
from truth_record import make_record
from truth_text import (
    PLACEHOLDER_BQ,
    _is_junk_bq,
    _node_id_from_url,
    _norm,
    _represents,
)

HERE = Path(__file__).parent
DATA = HERE / "data"; DATA.mkdir(exist_ok=True)


def _pick_bq_reps(nodes, bq_norm, profiles, used_nodes, used_bq):
    """For each (still unassigned, non-placeholder) Bezugsquelle, the FIRST node
    whose title represents the Bezugsquelle (= a real source dataset). Prevents
    an individual item that happens to be iterated first from representing the
    whole Bezugsquelle. Returns {norm_bezugsquelle: nodeId}."""
    reps = {}
    for n in nodes:
        if n["nodeId"] in used_nodes:
            continue
        if n["crawlerSpider"] and n["crawlerSpider"] in profiles:
            continue
        pub = n["publisher"]
        if not (pub and _norm(pub) in bq_norm):
            continue
        bq = bq_norm[_norm(pub)]
        nb = _norm(bq)
        if nb in used_bq or nb in PLACEHOLDER_BQ or nb in reps:
            continue
        if _represents(n["title"], bq):
            reps[nb] = n["nodeId"]
    return reps


# Workflow states in which a source dataset is published/visible in WLO search.
_PUBLISHED_WF = ("150_PUBLISH_IN_SEARCH", "155_ELEMENT_UNLOCK_BUFFET")

# Separators that introduce a sub-channel / sub-portal ("YouTube - Lehrerschmidt").
_SUBCHANNEL_SEPS = (" - ", " – ", " — ", " | ")


def _subchannel_parent(bq: str, bq_names: set) -> str:
    """If `bq` looks like a sub-channel of an existing parent Bezugsquelle, return the parent
    name ('YouTube - Mathematrick' -> 'YouTube'); else ''. The prefix before the separator must
    itself be a known, distinct Bezugsquelle — so a legitimate hyphenated full name whose prefix
    is NOT a separate Bezugsquelle is not flagged. Detection only, no merge (idea ported from the
    Quellenliste's BQ-canonicalisation, but non-destructive)."""
    low = bq.strip().lower()
    for sep in _SUBCHANNEL_SEPS:
        if sep in bq:
            prefix = bq.split(sep)[0].strip()
            if len(prefix) >= 3 and prefix.lower() != low and prefix.lower() in bq_names:
                return prefix
    return ""


def _mark_data_problems(records):
    """Add team-only data-problem flags (surfaced via the team filter): thin metadata,
    a Bezugsquelle with ~no content, an incomplete crawler binding, a source dataset
    without a Bezugsquelle, duplicate suspicion (shared URL or normalized title), missing or
    inconsistent editorial status, unpublished-in-search, ambiguous spider binding, and a
    publisher Bezugsquelle that carries content but has no source dataset."""
    # Pre-pass: URL/title frequencies so the duplicate-suspicion flag can see the whole set.
    url_c = Counter(); title_c = Counter()
    for r in records:
        u = (r["identity"].get("url") or r["public"].get("URL") or "").strip()
        if u:
            url_c[u] += 1
        t = (r["name"] or "").strip().lower()
        if t:
            title_c[t] += 1
    # Pre-pass: all Bezugsquelle names (lowercased) so the sub-channel check can see the whole set.
    bq_names = {(r["identity"].get("bezugsquelle") or "").strip().lower()
                for r in records if (r["identity"].get("bezugsquelle") or "").strip()}
    for r in records:
        fl = r["flags"]; pub = r["public"]; idn = r["identity"]
        # source dataset missing core descriptive fields (Beschreibung/Faecher/Bildungsstufen)
        if idn.get("nodeId") and not (pub.get("Beschreibung") and pub.get("Faecher")
                                      and pub.get("Bildungsstufen")):
            fl.append("METADATEN_DUENN")
        # Bezugsquelle that exists only as a facet entry with a single content item
        # (long-tail publisher string, mostly not a real curated source)
        if r["kind"] == "bezugsquelle" and (r.get("contentCount") or 0) <= 1:
            fl.append("BQ_EINZELINHALT")
        # crawler binding without a source dataset (search-invisible)
        if r["kind"] == "crawler" and not idn.get("nodeId"):
            fl.append("BINDUNG_UNVOLLSTAENDIG")
        # source dataset (has node) without a Bezugsquelle tag (incomplete linkage)
        if idn.get("nodeId") and not idn.get("bezugsquelle"):
            fl.append("QD_OHNE_BEZUGSQUELLE")
        # duplicate suspicion: shares its URL or its normalized title with another record
        u = (idn.get("url") or pub.get("URL") or "").strip()
        t = (r["name"] or "").strip().lower()
        if (u and url_c[u] > 1) or (t and title_c[t] > 1):
            fl.append("DUBLETTE_VERDACHT")
        # editorial status / search visibility / binding ambiguity (all node-level)
        inT = r.get("internal") or {}
        st = (inT.get("Erschliessungsstatus (genau)") or "").strip()
        if idn.get("nodeId"):
            if not st:
                fl.append("OHNE_STATUS")                       # no editorial status set
            elif st[:1].isdigit() and int(st[0]) < 9 and (
                    pub.get("Beschreibung") and pub.get("Faecher") and pub.get("Bildungsstufen")):
                fl.append("STATUS_INKONSISTENT")               # fully filled, but status leading digit < 9
            if (inT.get("Workflow-Status") or "").strip() not in _PUBLISHED_WF:
                fl.append("NICHT_PUBLIZIERT")                  # source dataset not published in search
        gi = (inT.get("general_identifier") or "").strip()
        rs = (inT.get("replicationsource") or "").strip()
        if gi and rs and gi != rs:
            fl.append("SPIDER_UNEINDEUTIG")                    # general_identifier and replicationsource disagree
        # publisher Bezugsquelle (no source dataset node) that still carries real content
        if r["kind"] == "bezugsquelle" and not idn.get("nodeId") and (r.get("contentCount") or 0) > 1:
            fl.append("BQ_OHNE_QD")
        # Bezugsquelle looks like a sub-channel of an existing parent (e.g. a YouTube channel)
        if idn.get("bezugsquelle") and _subchannel_parent(idn["bezugsquelle"], bq_names):
            fl.append("BQ_SUBCHANNEL")


# ---------------------------------------------------------------------------
# Merge the single source of truth
# ---------------------------------------------------------------------------
def build(rename_unrepresented=True):
    # rename_unrepresented (variant A, default): if a Bezugsquelle has no
    # source dataset of its own, the representing individual item is listed
    # under the Bezugsquelle name. False (variant B) = only the primary
    # preference (i), no renaming.
    profiles = load_crawler_profiles()
    nodes = load_nodes()
    bq_facet = load_facet("bezugsquellen")
    sp_facet = load_facet("spider")
    vocab = load_vocab()
    korr = load_korrektur()
    spider_top_pub = load_spider_top_publisher()
    bq_prev = load_bq_previews()

    bq_norm = {_norm(k): k for k in bq_facet}

    # Indexes
    nodes_by_spider = defaultdict(list)
    nodes_by_id = {}
    for n in nodes:
        nodes_by_id[n["nodeId"]] = n
        if n["crawlerSpider"]:
            nodes_by_spider[n["crawlerSpider"]].append(n)

    used_nodes = set()
    used_bq = set()
    records = []

    def pick_node(cands):
        if not cands:
            return None
        return sorted(cands, key=lambda n: (n["nodeId"] in used_nodes,  # unused first
                                            -len(n["description"]), -len(n["subjects"])))[0]

    # --- A) Crawler records (Spider as anchor) -----------------------------
    for spider, prof in profiles.items():
        node = pick_node(nodes_by_spider.get(spider, []))
        if node is None:
            # search-invisible source dataset: use the node ID from the CSV link
            nid = _node_id_from_url(prof.get("internal", {}).get("quelldatensatzProd", ""))
            if nid and nid in nodes_by_id and nid not in used_nodes:
                node = nodes_by_id[nid]
        bq_from_csv = prof["public"].get("bezugsquelle", "")
        if _is_junk_bq(bq_from_csv):
            bq_from_csv = ""
        top_pub = spider_top_pub.get(spider, "")
        bq = ""
        # Precedence: dominant publisher of the crawler content (the real data truth)
        if top_pub and _norm(top_pub) in bq_norm:
            bq = bq_norm[_norm(top_pub)]
        elif bq_from_csv and _norm(bq_from_csv) in bq_norm and _norm(bq_from_csv) not in PLACEHOLDER_BQ:
            bq = bq_norm[_norm(bq_from_csv)]
        elif node and node["publisher"] and _norm(node["publisher"]) in bq_norm \
                and _norm(node["publisher"]) not in PLACEHOLDER_BQ:
            bq = bq_norm[_norm(node["publisher"])]
        elif top_pub:
            bq = top_pub
        elif bq_from_csv and _norm(bq_from_csv) not in PLACEHOLDER_BQ:
            bq = bq_from_csv
        # A crawler's content is its Spider facet (replicationsource count) — use it even
        # when 0 (a dead crawler genuinely has 0). `or` would wrongly fall back to the
        # Bezugsquelle total; the bq fallback only applies when there is no Spider at all.
        content = sp_facet.get(spider, 0) if spider else (bq_facet.get(bq, 0) if bq else 0)
        if node:
            used_nodes.add(node["nodeId"])
        if bq:
            used_bq.add(_norm(bq))
        records.append(make_record("crawler", spider, prof, node, bq, content, vocab, korr, bq_prev))

    # --- B) Source-dataset records (without crawler profile) ---------------
    # Primary selection per Bezugsquelle: prefer the node whose title represents
    # the Bezugsquelle (a real source dataset). Otherwise an individual item
    # represents the Bezugsquelle and is listed under its name.
    bq_rep = _pick_bq_reps(nodes, bq_norm, profiles, used_nodes, used_bq)
    for n in nodes:
        if n["nodeId"] in used_nodes:
            continue
        # additional node of an already-represented crawler -> consolidate
        if n["crawlerSpider"] and n["crawlerSpider"] in profiles:
            used_nodes.add(n["nodeId"])
            continue
        used_nodes.add(n["nodeId"])
        sp = n["crawlerSpider"]
        has_spider = bool(sp)
        bq = ""
        secondary = False
        repless = False
        if n["publisher"] and _norm(n["publisher"]) in bq_norm:
            bq = bq_norm[_norm(n["publisher"])]
            nb = _norm(bq)
            if nb in used_bq:
                # Bezugsquelle already booked on a primary record -> secondary dataset.
                secondary = True
            elif nb in bq_rep and bq_rep[nb] != n["nodeId"]:
                # A real source dataset represents the Bezugsquelle -> yield to it.
                secondary = True
            else:
                used_bq.add(nb)
                # No node represents the Bezugsquelle: this individual item represents
                # it -> list under the Bezugsquelle name instead of the item title (variant A).
                repless = rename_unrepresented and nb not in bq_rep and nb not in PLACEHOLDER_BQ
        content = 0 if secondary else (bq_facet.get(bq, 0) if bq else 0)
        prof = profiles.get(sp) if has_spider else None
        kind = "crawler" if has_spider else "manuell"
        rec = make_record(kind, sp if has_spider else n["nodeId"], prof, n, bq, content, vocab, korr, bq_prev)
        if secondary:
            rec["flags"].append("ZWEITDATENSATZ")
            rec["erschliessung"] = f"Zweit-Datensatz (Inhalte unter Bezugsquelle '{bq}')"
            rec["confidence"] = "medium"
        elif repless and kind == "manuell":
            rec["name"] = bq
            rec["public"]["Titel"] = bq
            rec["provenance"]["Titel"] = "Bezugsquelle (kein eigener Quell-Datensatz)"
        records.append(rec)

    # --- C) Bezugsquelle-only (facet without source dataset) ---------------
    seen_bq_ids: dict[str, int] = {}
    for bq, cnt in bq_facet.items():
        if _is_junk_bq(bq) or _norm(bq) in used_bq:
            continue
        # Unique id even when two facet variants normalise to the same key
        # ("Klicksafe"/"klicksafe") — keep BOTH records, never let one shadow the other in byId.
        bid = "bq:" + _norm(bq)
        seen_bq_ids[bid] = seen_bq_ids.get(bid, 0) + 1
        if seen_bq_ids[bid] > 1:
            bid += f"#{seen_bq_ids[bid]}"
        records.append({
            "id": bid, "kind": "bezugsquelle", "name": bq,
            "identity": {"bezugsquelle": bq, "nodeId": "", "spider": "", "spiderVocabName": "", "url": ""},
            "contentCount": cnt,
            "previewUrl": bq_prev.get(_norm(bq), ""),
            "erschliessung": fp.coarse_erschliessung(cnt, False),
            "public": {"Bezugsquelle": bq, "Inhaltsanzahl": cnt},
            "internal": {},
            "fieldGeneration": [],
            "provenance": {"Bezugsquelle": "WLO-API (Facette)", "Inhaltsanzahl": "WLO-API (Facette)"},
            "flags": ["FACETS_ONLY"],
            "confidence": "low",
        })

    _mark_data_problems(records)
    return records


def main():
    # Variant A (default) vs. B: the (ii) renaming can be disabled via QE_RENAME_UNREP_BQ=0.
    rename = os.environ.get("QE_RENAME_UNREP_BQ", "1").strip() != "0"
    records = build(rename_unrepresented=rename)
    # sort by content count
    records.sort(key=lambda r: -(r.get("contentCount") or 0))
    cmeta = {}
    if RAW and (RAW / "cache_meta.json").exists():
        try:
            cmeta = json.loads((RAW / "cache_meta.json").read_text(encoding="utf-8"))
        except Exception:
            cmeta = {}
    meta = {
        "total": len(records),
        "byKind": {k: sum(1 for r in records if r["kind"] == k) for k in ("crawler", "manuell", "bezugsquelle")},
        "withFieldProfile": sum(1 for r in records if r.get("fieldGeneration")),
        "withNode": sum(1 for r in records if r["identity"]["nodeId"]),
        # content assigned to a source (crawler/source dataset/manual)
        "totalContents": sum(r.get("contentCount") or 0 for r in records if r["kind"] != "bezugsquelle"),
        # real WLO prod total of ALL content (facet pagination.total, via fetcher)
        "wloProdContent": cmeta.get("wloProdContentTotal"),
        # data timestamp = time of the live fetch (fetcher), not of the truth build
        "generatedAt": cmeta.get("fetchedAt") or time.strftime("%Y-%m-%d %H:%M"),
    }
    # Atomic write (temp file + os.replace): a crash mid-write can't corrupt truth.json,
    # and store.load() never reads a half-written file.
    out = DATA / "truth.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"meta": meta, "records": records}, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out)
    print(json.dumps(meta, ensure_ascii=False, indent=2), file=sys.stderr)
    print(f"Inputs: nodes={'ok' if RAW else 'FEHLT'} crawler={DATENCRAWLER and DATENCRAWLER.name} "
          f"korrektur={KORREKTUR and KORREKTUR.name}", file=sys.stderr)
    return meta


if __name__ == "__main__":
    main()
