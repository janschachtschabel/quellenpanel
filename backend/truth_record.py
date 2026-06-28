"""truth_record.py — building a canonical source record.

From a node (edu-sharing metadata), a crawler profile (datencrawler.csv) and a
Bezugsquelle, constructs a record with public/internal separation, per-field
provenance and provenance flags. Pure construction (no IO); called by truth.build
once per source.
"""
import field_policy as fp
from truth_text import IGNORE_SPIDERS, _norm, _resolve_rs, spider_vocab_name


def _public_and_provenance(node, prof, bq, content):
    """Public fields + per-field provenance (where the value comes from).
    Node metadata first, crawler profile as supplement/fallback."""
    public, prov = {}, {}

    def setp(k, v, src):
        if v not in (None, "", [], False):
            public[k] = v
            prov[k] = src

    if node:
        setp("Titel", node["title"], "WLO-API")
        setp("URL", node["wwwUrl"], "WLO-API")
        setp("Beschreibung", node["description"], "WLO-API")
        setp("Lizenz", node["license"], "WLO-API")
        setp("OER", node["oer"], "WLO-API")
        setp("Faecher", node["subjects"], "WLO-API")
        setp("Bildungsstufen", node["educationalContext"], "WLO-API")
        setp("Inhaltstypen", node["oehLrt"], "WLO-API")
        setp("Zielgruppe", node.get("targetGroup"), "WLO-API")
        setp("Alter", node.get("ageRange"), "WLO-API")
        setp("Sprache", node["language"], "WLO-API")
        setp("Sprachniveau", node.get("languageLevel"), "WLO-API")
        setp("Zielsprache", node.get("languageTarget"), "WLO-API")
        setp("Lehrplanbezug", node.get("curriculum"), "WLO-API")
        setp("FSK", node.get("fsk"), "WLO-API")
        setp("Schlagworte", node["keywords"], "WLO-API")
        setp("Urheber", node.get("author"), "WLO-API")     # prefer live author
    if prof:
        pp = prof["public"]
        setp("URL", pp.get("url") or public.get("URL", ""), prov.get("URL", "datencrawler.csv"))
        if "Urheber" not in public:                         # CSV only as fallback
            setp("Urheber", pp.get("urheber"), "datencrawler.csv")
        setp("robots.txt", pp.get("robotsTxt"), "datencrawler.csv")
        setp("TDM-Hinweis (§44b)", pp.get("tdmHinweis"), "datencrawler.csv")
        setp("AGB/Nutzungsbedingungen", pp.get("agb"), "datencrawler.csv")
        setp("Lizenz-Check", pp.get("lizenzCheck"), "datencrawler.csv")
        setp("API-Nutzungsbedingungen", pp.get("apiNutzung"), "datencrawler.csv")
    setp("Bezugsquelle", bq, "WLO-API (Facette)")
    setp("Inhaltsanzahl", content, "WLO-API (Facette)")
    return public, prov


def _internal_fields(node, prof, vocab, korr):
    """Internal fields (developer notes, exact status, node ID, correction list)."""
    internal = {}
    if prof:
        for k, v in prof["internal"].items():
            if v:
                internal[k] = v
    if node:
        internal.update({
            "Erschliessungsstatus (genau)": node["editorialStatus"],
            "Workflow-Status": node["wfStatus"],
            "Node-ID": node["nodeId"],
            "replicationsource": _resolve_rs(node["replicationSource"], vocab),
            "general_identifier": node["generalIdentifier"],
            "zuletzt geaendert": node["modified"],
        })
        k = korr.get(node["nodeId"])
        if k:
            internal["Korrekturliste"] = k["liste"] or "—"
    return internal


def _record_flags(node, spider, public, korr):
    """Provenance/quality flags (badges + filters): migration, legacy, mis-tagging …"""
    flags = []
    if node and node["multiType"]:
        flags.append("FEHLTAGGING")
    if node:
        kk = korr.get(node["nodeId"])
        if kk and kk["liste"]:
            flags.append(kk["liste"].upper())
        # Provenance markers (public, as badges):
        if node.get("replicationSource", "") == "wirlernenonline_spider":
            flags.append("WLO_MIGRATION")           # imported via the WLO data migration
        if spider and spider.startswith("http"):
            flags.append("LEGACY_BINDUNG")           # bound via legacy vocab URI (not a technical spider)
        if spider and not any("quelle" in str(x).lower() for x in node.get("oehLrt", [])):
            flags.append("TYP_NICHT_QUELLE")         # real binding, but LRT ≠ Quelle (mis-tagged)
    if not node:
        flags.append("FACETS_ONLY")
    if public.get("OER"):
        flags.append("OER")
    return flags


def make_record(kind, anchor, prof, node, bq, content, vocab, korr, bq_prev=None):
    """Build a canonical source record. anchor = spider name (crawler) or nodeId."""
    bq_prev = bq_prev or {}
    node_title = node["title"] if node and node["title"] else ""
    prof_titel = prof["public"].get("titel") if prof else ""
    if kind == "crawler":
        name = bq or node_title or prof_titel or anchor
    else:  # manual / otherwise: the dataset title is the source name
        name = node_title or bq or prof_titel or anchor
    spider = prof["spider"] if prof else (node["crawlerSpider"] if node else "")
    # Effective binding: if no general_identifier is set but replicationsource
    # is NOT wirlernenonline_spider, then that is the real spider/source binding.
    if not spider and node:
        rs = node.get("replicationSource", "")
        if rs and rs not in IGNORE_SPIDERS:
            spider = rs
    public, prov = _public_and_provenance(node, prof, bq, content)
    internal = _internal_fields(node, prof, vocab, korr)
    flags = _record_flags(node, spider, public, korr)
    vocab_name = spider_vocab_name(spider, vocab) if spider else ""
    return {
        "id": (("crawler:" + spider) if kind == "crawler" and spider else
               ("node:" + node["nodeId"]) if node else ("x:" + str(anchor))),
        "kind": kind,
        "name": name,
        "identity": {
            "bezugsquelle": bq, "nodeId": node["nodeId"] if node else "",
            "spider": spider, "spiderVocabName": vocab_name,
            "url": public.get("URL", ""),
        },
        "contentCount": content,
        "previewUrl": (node["previewUrl"] if node and node.get("previewUrl") else bq_prev.get(_norm(bq), "")),
        "quality": node.get("quality", {}) if node else {},
        "erschliessung": fp.coarse_erschliessung(content, bool(node)),
        "public": public,
        "internal": internal,
        "fieldGeneration": prof["fieldGeneration"] if prof else [],
        "fieldActiveCount": prof["fieldActiveCount"] if prof else 0,
        "provenance": prov,
        "flags": flags,
        "confidence": "high" if (node and (spider or bq)) else ("medium" if node or bq else "low"),
    }
