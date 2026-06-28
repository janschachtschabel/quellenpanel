"""stats.py — public statistics aggregation (pure).

Aggregates the records into the key figures, distributions, origin and
provenance evaluations of the public view. Pure functions over
(records, meta) — no web/IO dependency, so the numbers are individually testable.

  compute_enduser_stats   end-user public figures over the visible set (/api/stats, tier 0)
  compute_stats_full      extended overview — aggregate counts only, no raw internal fields
                          (/api/stats, tier >= 1)
  compute_filter_options  filter vocabulary (/api/filter-options)
  compute_stats           compact variant retained from the shared Quellensteckbriefe engine; unused here.

Shared helpers -> stats_common.py.
"""
from collections import Counter

from stats_common import _BESCHREIBENDE_FELDER, _bracket, _ctype_bucket, _how_bucket


def compute_stats(recs, meta):
    crawler = [r for r in recs if r["kind"] == "crawler"]
    subj = Counter()
    for r in recs:
        for s in r["public"].get("Faecher", []):
            subj[s] += 1
    return {
        "meta": meta,
        "crawlerWithFieldProfile": sum(1 for r in crawler if r.get("fieldGeneration")),
        "oerCount": sum(1 for r in recs if "OER" in r.get("flags", [])),
        "facetsOnly": sum(1 for r in recs if r["kind"] == "bezugsquelle"),
        "topSubjects": [{"value": k, "count": v} for k, v in subj.most_common(15)],
    }


def compute_enduser_stats(recs, meta):
    """Public, end-user statistics over the VISIBLE record set.

    Mirrors the figures of the old Quellenliste statistics view but exposes ONLY clean
    aggregates — totals, content distribution, top sources / subjects / levels, licenses,
    OER share. No flags, confidence, blacklist, provenance or other internal/problem data
    (that is the whole point of the end-user app — see enduser.card). Computed over the
    already-filtered visible records so the numbers match the source list. The total content
    count comes from `meta` (deduplicated, identical to the Quellensteckbriefe app); a naive
    per-source sum would double-count content shared across overlapping sources.
    """
    subj = Counter(); lvl = Counter(); lic = Counter(); lang = Counter()
    with_node = crawler = oer = 0
    for r in recs:
        if (r.get("identity") or {}).get("nodeId"):
            with_node += 1
        if r.get("kind") == "crawler":
            crawler += 1
        p = r["public"]
        if p.get("OER"):
            oer += 1
        for s in p.get("Faecher", []): subj[s] += 1
        for s in p.get("Bildungsstufen", []): lvl[s] += 1
        if p.get("Lizenz"): lic[p["Lizenz"]] += 1
        if p.get("Sprache"): lang[p["Sprache"]] += 1
    total = len(recs)
    top = sorted(recs, key=lambda r: -(r.get("contentCount") or 0))[:15]

    def lst(c, n):
        return [{"value": k, "count": v} for k, v in c.most_common(n)]

    return {
        "total": total,
        "totalContents": meta.get("totalContents", 0),
        "withQuelldatensatz": with_node,
        "crawlerCount": crawler,
        "oer": {"count": oer, "percent": round(100 * oer / max(1, total), 1)},
        "topByContent": [{"value": r["name"], "count": r.get("contentCount") or 0} for r in top],
        "topSubjects": lst(subj, 15),
        "topLevels": lst(lvl, 10),
        "licenseDistribution": lst(lic, 12),
        # Languages of the sources — shown in the base view next to the top-sources chart.
        "topLanguages": lst(lang, 10),
    }


def compute_filter_options(recs):
    subj, lvl, lic, lang, lrt, ersch = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    for r in recs:
        p = r["public"]
        for s in p.get("Faecher", []): subj[s] += 1
        for s in p.get("Bildungsstufen", []): lvl[s] += 1
        for s in p.get("Inhaltstypen", []): lrt[s] += 1
        if p.get("Lizenz"): lic[p["Lizenz"]] += 1
        if p.get("Sprache"): lang[p["Sprache"]] += 1
        status = (r.get("internal") or {}).get("Erschliessungsstatus (genau)")
        if status: ersch[status] += 1
    return {
        "kinds": ["crawler", "manuell", "bezugsquelle"],
        "subjects": [k for k, _ in subj.most_common(60)],
        "levels": [k for k, _ in lvl.most_common(20)],
        "licenses": [k for k, _ in lic.most_common(20)],
        "languages": [k for k, _ in lang.most_common(20)],
        "lrts": [k for k, _ in lrt.most_common(25)],
        # Cataloguing status; leading-digit prefix ("0." … "9.") sorts as editorial progress.
        "erschliessung": sorted(ersch),
    }


def compute_stats_full(recs, meta):
    total = meta["total"]
    BORDER = ["0", "1–4", "5–9", "10–49", "50–99", "100–499", "500–999", "1k–9.9k", "≥10k"]
    bqcb = Counter(); subj = Counter(); lvl = Counter(); lic = Counter()
    lang = Counter(); lrt = Counter(); how = Counter(); flags = Counter()
    ctype = Counter()
    distinct_bq = set(); bq_with_node = set(); schnitt = 0
    node_cb = Counter()
    besch_cnt = Counter(); node_n = 0          # descriptive-field fill over Quelldatensätze
    total_active_fields = crawler_fp = 0
    prev = qual = desc = urlc = oer = 0
    singletons = bq_u5 = quelle_ohne_bq = 0
    for r in recs:
        n = r.get("contentCount") or 0
        fl = r.get("flags", [])
        for f in fl: flags[f] += 1
        if "OER" in fl: oer += 1
        pub = r["public"]; idn = r["identity"]
        for s in pub.get("Faecher", []): subj[s] += 1
        for s in pub.get("Bildungsstufen", []): lvl[s] += 1
        for s in pub.get("Inhaltstypen", []): lrt[s] += 1
        if pub.get("Lizenz"): lic[pub["Lizenz"]] += 1
        if pub.get("Sprache"): lang[pub["Sprache"]] += 1
        if r.get("previewUrl"): prev += 1
        if r.get("quality"): qual += 1
        if pub.get("Beschreibung"): desc += 1
        if pub.get("URL"): urlc += 1
        if r["kind"] == "bezugsquelle":
            bqcb[_bracket(n)] += 1
            if n <= 1: singletons += 1
            if n < 5: bq_u5 += 1
        if idn.get("nodeId") and not idn.get("bezugsquelle"):
            quelle_ohne_bq += 1
        if idn.get("nodeId"):
            node_cb[_bracket(n)] += 1          # content-volume distribution per Quelldatensatz
            node_n += 1
            # Descriptive-metadata fill: which Quelldatensätze actually carry each field.
            for label, _cat, where, key in _BESCHREIBENDE_FELDER:
                val = pub.get(key) if where == "public" else r.get(key)
                if val not in (None, "", [], False, {}):
                    besch_cnt[label] += 1
        # Origin: intersection Quelldatensatz <-> Bezugsquelle (count distinct)
        bqv = (idn.get("bezugsquelle") or "").strip().lower()
        if bqv:
            distinct_bq.add(bqv)
            if idn.get("nodeId"):
                bq_with_node.add(bqv); schnitt += 1
        if r["kind"] == "crawler":
            ct = (r.get("internal") or {}).get("crawlerType", "")
            if ct:
                ctype[_ctype_bucket(ct)] += 1
        if r.get("fieldGeneration"):
            crawler_fp += 1
            total_active_fields += r.get("fieldActiveCount", 0)
            for fg in r["fieldGeneration"]:
                how[_how_bucket(fg.get("how"))] += 1
    top_crawler = sorted([r for r in recs if r["kind"] == "crawler"],
                         key=lambda r: -(r.get("contentCount") or 0))[:20]
    top_content = sorted(recs, key=lambda r: -(r.get("contentCount") or 0))[:20]
    def lst(c, n=15): return [{"value": k, "count": v} for k, v in c.most_common(n)]
    def pct(x): return round(100 * x / max(1, total), 1)

    def besch(cat):
        rows = [{"feld": lbl, "anzahl": besch_cnt.get(lbl, 0),
                 "prozent": round(100 * besch_cnt.get(lbl, 0) / max(1, node_n))}
                for lbl, c, _w, _k in _BESCHREIBENDE_FELDER if c == cat]
        return sorted(rows, key=lambda x: -x["prozent"])
    bq_total = meta["byKind"]["bezugsquelle"]

    # Content coverage by source type (deduplicated per group, groups overlap)
    content_by_bq = {}; crawler_content = 0; quelle_bqs = set()
    for r in recs:
        cc = r.get("contentCount") or 0
        idn = r["identity"]; bq = (idn.get("bezugsquelle") or "").strip().lower()
        if r["kind"] == "crawler":
            crawler_content += cc
        if bq:
            if cc > content_by_bq.get(bq, 0):
                content_by_bq[bq] = cc          # per Bezugsquelle only once (second record=0)
            if idn.get("nodeId"):
                quelle_bqs.add(bq)
    bq_content = sum(content_by_bq.values())
    quelle_content = sum(c for b, c in content_by_bq.items() if b in quelle_bqs)

    # Source management: VISIBLE records as RECORD counts — consistent with the
    # "Art der Quelle" (source-type) filter. The Quelldatensatz dimension counts OBJECTS (secondary
    # datasets / ZWEITDATENSATZ included, like the has_node=True filter); the default
    # and Bezugsquelle dimension count DISTINCT tags (secondary datasets collapsed).
    # Blacklist is always excluded. See field_policy.HIDDEN_BY_DEFAULT / filtering.py.
    qv_gesamt = qv_node = qv_bq = qv_both = 0
    qv_kind = Counter()
    for r in recs:
        fl = r.get("flags", [])
        if "BLACKLIST" in fl:
            continue
        idn = r["identity"]
        hn = bool(idn.get("nodeId")); hb = bool(idn.get("bezugsquelle"))
        if hn: qv_node += 1                      # object view: zweit count
        if hn and hb: qv_both += 1
        if "ZWEITDATENSATZ" not in fl:           # tag view: collapse secondary datasets
            qv_gesamt += 1
            qv_kind[r["kind"]] += 1
            if hb: qv_bq += 1
    return {
        "meta": meta,
        "byKind": meta["byKind"],
        # consistent with the "Art der Quelle" (source-type) filter (visible records, problem
        # records hidden — see field_policy.HIDDEN_BY_DEFAULT)
        "quellenverwaltung": {
            "gesamt": qv_gesamt, "mitQuelldatensatz": qv_node,
            "mitBezugsquelle": qv_bq, "ueberschneidung": qv_both,
        },
        # Kind distribution of the visible (clean, default-view) sources — sums to
        # quellenverwaltung.gesamt; used by the statistics PDF so its summary matches
        # the app (the raw meta["byKind"] above still carries the unfiltered counts).
        "byKindVisible": {k: qv_kind.get(k, 0) for k in ("crawler", "manuell", "bezugsquelle")},
        "contentBracketsNode": [{"value": b, "count": node_cb[b]} for b in BORDER if node_cb.get(b)],
        "bqSizeBrackets": [{"value": b, "count": bqcb[b]} for b in BORDER if bqcb.get(b)],
        "oer": {"count": oer, "percent": pct(oer)},
        # Overview / key figures
        "totals": {
            "quellenGesamt": total,
            "inhalteGesamt": meta.get("totalContents", 0),
            "quelldatensaetze": meta["withNode"],
            "crawler": meta["byKind"]["crawler"],
            "manuell": meta["byKind"]["manuell"],
            "bezugsquellenOhneQuelle": bq_total,
        },
        # Content coverage by source type (content reachable per type)
        "contentCoverage": {
            "bezugsquelle": bq_content,
            "crawler": crawler_content,
            "quelldatensatz": quelle_content,
            "gesamt": meta.get("totalContents", 0),
        },
        # Coverage (share of records with the attribute filled in)
        "coverage": {
            "vorschaubild": {"count": prev, "percent": pct(prev)},
            "qualitaetsmerkmale": {"count": qual, "percent": pct(qual)},
            "beschreibung": {"count": desc, "percent": pct(desc)},
            "url": {"count": urlc, "percent": pct(urlc)},
        },
        "erschliessung": {
            "mitQuelldatensatz": meta["withNode"],
            "nurBezugsquelle": bq_total,
            "crawler": meta["byKind"]["crawler"],
            "manuell": meta["byKind"]["manuell"],
            "zweitDatensatz": flags.get("ZWEITDATENSATZ", 0),
        },
        # Content: actual WLO prod total vs. attributable to a source
        "inhalte": {
            "wloProd": meta.get("wloProdContent"),
            "zuordenbar": meta.get("totalContents", 0),
        },
        # Origin: overlap Quelldatensatz <-> Bezugsquelle (both perspectives). Public, structural
        # counts only — the correction/blacklist/whitelist breakdown and the confidence levels are
        # internal data-quality signals and live ONLY behind the team endpoint (/api/stats/team),
        # never in this tier-1 overview (which is open by default).
        "herkunft": {
            "quelldatensaetzeGesamt": meta["withNode"],
            "quelldatensatzMitBezugsquelle": schnitt,
            "quelldatensatzOhneBezugsquelle": quelle_ohne_bq,
            "bezugsquellenGesamt": len(distinct_bq),
            "bezugsquelleMitQuelldatensatz": len(bq_with_node),
            # distinct-consistent: total - with Quelldatensatz (= pure BQ without node)
            "bezugsquelleOhneQuelldatensatz": len(distinct_bq) - len(bq_with_node),
            "schnittmengeNurEinmalProBezugsquelle": len(bq_with_node),
        },
        # Descriptive-metadata fill over the Quelldatensätze, split into two balanced charts
        # (content & discoverability / classification & quality). Replaces the old crawler
        # field-generation fill chart (which only covered the ~55 crawler profiles).
        "beschreibendeFelder": {
            "basis": node_n,
            "inhalt": besch("inhalt"),
            "einordnung": besch("einordnung"),
        },
        # Crawlers by technical type (normalized)
        "crawlerByType": lst(ctype, 12),
        # Provenance markers (public): how a source is bound/ingested
        "provenienz": {
            "wloMigration": flags.get("WLO_MIGRATION", 0),
            "legacyBindung": flags.get("LEGACY_BINDUNG", 0),
            "misGetaggt": flags.get("TYP_NICHT_QUELLE", 0),
            "zweitDatensatz": flags.get("ZWEITDATENSATZ", 0),
        },
        "fieldGeneration": {
            "crawlerWithProfile": crawler_fp,
            "totalActiveFields": total_active_fields,
            "avgFieldsPerCrawler": round(total_active_fields / max(1, crawler_fp), 1),
            "byMethod": lst(how, 12),
        },
        "licenseDistribution": lst(lic, 15),
        "topSubjects": lst(subj, 25),
        "topLevels": lst(lvl, 15),
        "topLanguages": lst(lang, 10),
        "topLrt": lst(lrt, 15),
        "topCrawler": [{"name": r["name"], "count": r.get("contentCount") or 0,
                        "fields": r.get("fieldActiveCount", 0)} for r in top_crawler],
        "topByContent": [{"name": r["name"], "count": r.get("contentCount") or 0,
                          "kind": r["kind"]} for r in top_content],
    }
