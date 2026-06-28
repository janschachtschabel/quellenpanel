"""stats_team.py — internal team statistics (/api/stats/team).

Data problems, origin (Quelldatensatz↔Bezugsquelle), spider reconciliation and
field fill levels. Pure function over (records, meta) — no web/IO
dependency; intended for the team only (server-side password-protected).
"""
from collections import Counter

from stats_common import _FUELL_KI

# Flags shown in the problem charts → for each, collect a few example sources (drill-down). Mirrors
# the team filter vocabulary (data-problem-filters.ts) plus the two provenance markers.
_EXAMPLE_FLAGS = frozenset({
    "FEHLTAGGING", "ZWEITDATENSATZ", "BQ_EINZELINHALT", "DUBLETTE_VERDACHT", "METADATEN_DUENN",
    "BLACKLIST", "QD_OHNE_BEZUGSQUELLE", "BINDUNG_UNVOLLSTAENDIG", "TYP_NICHT_QUELLE",
    "BQ_OHNE_QD", "OHNE_STATUS", "STATUS_INKONSISTENT", "NICHT_PUBLIZIERT",
    "SPIDER_UNEINDEUTIG", "BQ_SUBCHANNEL", "WLO_MIGRATION", "LEGACY_BINDUNG",
})

# Actual data DEFECTS (for the "problems per source" distribution) — the example flags minus the
# two pure provenance markers (migration / legacy binding are origin info, not defects).
_DEFECT_FLAGS = _EXAMPLE_FLAGS - {"WLO_MIGRATION", "LEGACY_BINDUNG"}


def _defect_bucket(n):
    return "0" if n == 0 else "1" if n == 1 else "2" if n == 2 else "3+"


def compute_stats_team(recs, meta):
    """Negative/data-problem statistics + origin + spider reconciliation. Team only."""
    flags = Counter()
    conf = Counter()
    nur_quelle = schnitt = nur_bq = 0
    schnitt_sauber = schnitt_zweit = schnitt_black = 0
    gi = wlo_migr = both_fields = 0
    sb_gi = sb_rs = sb_both = sb_bothdiff = 0
    sb_onlyrs_wlo = sb_onlyrs_spider = sb_onlyrs_named = 0
    bq_u5 = 0
    url_c = Counter(); title_c = Counter()
    prob_ex = {}                    # flag -> [(contentCount, name)] for example drill-down
    prob_per_src = Counter()        # defect-count bucket -> number of sources (distribution)
    ki_cnt = Counter(); ki_base = 0
    for r in recs:
        conf[r.get("confidence", "?")] += 1
        fls = r.get("flags", [])
        for f in fls:
            flags[f] += 1
            if f in _EXAMPLE_FLAGS:
                prob_ex.setdefault(f, []).append((r.get("contentCount") or 0, r["name"]))
        prob_per_src[_defect_bucket(sum(1 for f in fls if f in _DEFECT_FLAGS))] += 1
        idn = r["identity"]; has_node = bool(idn.get("nodeId")); has_bq = bool(idn.get("bezugsquelle"))
        if r["kind"] == "bezugsquelle":
            nur_bq += 1
            if (r.get("contentCount") or 0) < 5: bq_u5 += 1
        elif has_node and has_bq:
            schnitt += 1
            if "BLACKLIST" in fls:
                schnitt_black += 1          # possible duplicate (correction list)
            elif "ZWEITDATENSATZ" in fls:
                schnitt_zweit += 1          # additional record of the same Bezugsquelle
            else:
                schnitt_sauber += 1         # clean first assignment (≈ old value)
        elif has_node and not has_bq:
            nur_quelle += 1
        intr = r.get("internal", {})
        g = str(intr.get("general_identifier", "")); rs = str(intr.get("replicationsource", ""))
        if g and "spider" in g.lower(): gi += 1
        if rs == "wirlernenonline_spider": wlo_migr += 1
        if g and rs: both_fields += 1
        # Spider binding broken down (general_identifier vs. replicationsource)
        g2 = g.strip(); rs2 = rs.strip()
        if g2: sb_gi += 1
        if rs2: sb_rs += 1
        if g2 and rs2:
            sb_both += 1
            if g2 != rs2: sb_bothdiff += 1
        elif rs2:                                       # ONLY replicationsource (no gi)
            if rs2 == "wirlernenonline_spider": sb_onlyrs_wlo += 1
            elif rs2.endswith("_spider"): sb_onlyrs_spider += 1   # real spider, only via rs!
            else: sb_onlyrs_named += 1                  # legacy vocab name (real source)
        u = idn.get("url") or r["public"].get("URL", "")
        if u: url_c[u] += 1
        nm = (r["name"] or "").strip().lower()
        if nm: title_c[nm] += 1
        # Fill level: AI/legal notes per crawler profile (metadata fill moved to the tier-1 view).
        pub = r["public"]
        if r.get("fieldGeneration"):
            ki_base += 1
            for label, key in _FUELL_KI:
                if pub.get(key) not in (None, "", [], False):
                    ki_cnt[label] += 1

    def dup(c):
        groups = {k: v for k, v in c.items() if v > 1}
        return {"gruppen": len(groups), "ueberzaehlig": sum(v - 1 for v in groups.values()),
                "beispiele": [{"wert": k, "anzahl": v} for k, v in sorted(groups.items(), key=lambda x: -x[1])[:8]]}

    feld_ki = [{"feld": l, "anzahl": ki_cnt.get(l, 0),
                "prozent": round(100 * ki_cnt.get(l, 0) / max(1, ki_base))} for l, _ in _FUELL_KI]
    # Example sources per problem flag (top 5 by content) → drill-down cards in the team view.
    problem_beispiele = {
        f: [{"name": nm, "inhalte": cc} for cc, nm in sorted(ex, key=lambda x: -x[0])[:5]]
        for f, ex in prob_ex.items()
    }

    return {
        "generatedAt": meta.get("generatedAt"),
        # Assignment confidence (team only): high/medium/low depending on linkage state
        "confidence": dict(conf),
        # Origin of the sources (intersection Quelldatensatz ↔ Bezugsquelle)
        "herkunft": {
            "quelldatensaetzeGesamt": meta["withNode"],
            "nurQuelldatensatz_ohneBezugsquelle": nur_quelle,
            "schnittmenge_QuelldatensatzUndBezugsquelle": schnitt,
            "nurBezugsquelle_ohneQuelldatensatz": nur_bq,
            # Breakdown of the intersection (explains 1,165 vs. old value ~660–700)
            "schnittmenge_sauber": schnitt_sauber,
            "schnittmenge_zweitDatensatz": schnitt_zweit,
            "schnittmenge_blacklist": schnitt_black,
        },
        # Spider reconciliation: general_identifier (on the Quelldatensatz) vs. migration
        "spider": {
            "mitCrawlerBindung_generalIdentifier": gi,
            "ausWloAltmigration_replicationsource": wlo_migr,
            "beideFelderGesetzt": both_fields,
        },
        # Spider binding complete: general_identifier ↔ replicationsource
        "spiderBindung": {
            "mitGeneralIdentifier": sb_gi,
            "mitReplicationsource": sb_rs,
            "beide": sb_both,
            "beideUnterschiedlich": sb_bothdiff,
            "nurGeneralIdentifier": sb_gi - sb_both,
            "nurReplicationsource": sb_rs - sb_both,
            "nurRs_wloMigration": sb_onlyrs_wlo,        # pure WLO migration (no real crawler)
            "nurRs_echterSpider": sb_onlyrs_spider,     # real spider ONLY via replicationsource
            "nurRs_legacyName": sb_onlyrs_named,        # legacy vocab source (real)
            # real crawler/source binding = general_identifier OR replicationsource != WLO
            "echteBindungGesamt": sb_gi + sb_onlyrs_spider + sb_onlyrs_named,
        },
        # Data problems — aligned 1:1 with the team filter (each key = one flag=<NAME>
        # option), so the chart and the filter always show the same set by construction.
        "probleme": {
            "mischTypen_fehltagging": flags.get("FEHLTAGGING", 0),
            "zweitDatensaetze": flags.get("ZWEITDATENSATZ", 0),
            "bezugsquelleEinzelinhalt": flags.get("BQ_EINZELINHALT", 0),
            "dublettenVerdacht": flags.get("DUBLETTE_VERDACHT", 0),
            "metadatenDuenn": flags.get("METADATEN_DUENN", 0),
            "blacklist": flags.get("BLACKLIST", 0),
            "quelldatensatzOhneBezugsquelle": flags.get("QD_OHNE_BEZUGSQUELLE", 0),
            "bindungUnvollstaendig": flags.get("BINDUNG_UNVOLLSTAENDIG", 0),
            "typNichtQuelle": flags.get("TYP_NICHT_QUELLE", 0),
            "bezugsquelleOhneQuelldatensatz": flags.get("BQ_OHNE_QD", 0),
            "ohneStatus": flags.get("OHNE_STATUS", 0),
            "statusInkonsistent": flags.get("STATUS_INKONSISTENT", 0),
            "nichtPubliziert": flags.get("NICHT_PUBLIZIERT", 0),
            "spiderUneindeutig": flags.get("SPIDER_UNEINDEUTIG", 0),
            "bqSubchannel": flags.get("BQ_SUBCHANNEL", 0),
            # Provenance markers (origin/binding group) — counts so the group chart is complete.
            "wloMigration": flags.get("WLO_MIGRATION", 0),
            "legacyBindung": flags.get("LEGACY_BINDUNG", 0),
            # extra context + detail for the dedicated duplicate cards (not in the bar list)
            "bezugsquellenUnter5Inhalte": bq_u5,
            "doppelteUrl": dup(url_c),
            "doppelteTitel": dup(title_c),
        },
        # Fill level (team): how complete are the AI/legal-note fields? (Descriptive-metadata
        # fill now lives in the tier-1 overview, over the Quelldatensätze.)
        "feldFuellstand": {
            "kiBasis": ki_base, "ki": feld_ki,
        },
        # Example sources per data-problem flag (keyed by flag) — drill-down detail.
        "problemBeispiele": problem_beispiele,
        # Distribution: how many sources carry 0 / 1 / 2 / 3+ data defects at once (overview that
        # does NOT duplicate the per-problem group charts — shows problem concentration instead).
        "problemeProQuelle": [{"value": b, "count": prob_per_src[b]}
                              for b in ("0", "1", "2", "3+") if prob_per_src.get(b)],
    }
