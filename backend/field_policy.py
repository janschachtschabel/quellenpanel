"""
field_policy.py
===============
Central policy: which information is PUBLIC (data providers / data
consumers) and which is INTERNAL (password-protected, for team members only).

Principle (per the assignment):
  - Public: basic + quality info (license, OER, subject, level, URL,
    content count) AND how metadata was produced (per-field provenance of the crawlers).
  - Internal: internal developer notes about crawlers and their *exact*
    operational status.

This file is the ONE place where the separation is maintained.
"""

# --- Crawler base columns from datencrawler.csv ----------------------------
# Publicly usable profile fields (for data providers/data consumers)
CRAWLER_PUBLIC_BASE = {
    "Titel": "titel",
    "Url": "url",
    "Bezugsquelle": "bezugsquelle",
    "Urheber": "urheber",
    # Legal/AI-usage fields of the SOURCE itself (basis for the AI-usage assessment)
    "robots.txt": "robotsTxt",
    "TDM Hinweis ( §44b)": "tdmHinweis",
    "AGB / Nutzungsbedingungen": "agb",
    "Lizenz Check": "lizenzCheck",
    "API Nutzungsbedingungen": "apiNutzung",
}

# Internal fields – ONLY for team members (password)
CRAWLER_INTERNAL_BASE = {
    "Crawler (Spider)": "spider",
    "Prio": "prio",
    "Crawler-Type": "crawlerType",
    "Zustand": "zustand",                  # exact operational status -> internal
    "Spider Bemerkungen": "spiderBemerkungen",
    "Einschätzung KI & Erschließung": "kiEinschaetzung",
    "Bemerkung/Status": "bemerkungStatus",
    "Prod letzter Crawl": "prodLetzterCrawl",
    "Staging letzter Crawl": "stagingLetzterCrawl",
    "Häufigkeit": "haeufigkeit",
    "Anzahl Prod": "anzahlProd",
    "Anzahl Staging": "anzahlStaging",
    "Quelldatensatz (Prod)": "quelldatensatzProd",
    "Hinweis zu Quellendatensatz": "hinweisQuelldatensatz",
    "Export to OER Berlin": "exportOerBerlin",
    "GitHub": "github",
    # Contract/agreement status = WLO-internal business info -> INTERNAL only
    "Vereinb. neu": "Vertrag/Vereinbarung",
    "Vereinb. alt": "Vereinbarung (alt)",
}

# --- Live API fields (Quelldatensatz) --------------------------------------
# Public
NODE_PUBLIC = {
    "title": "Titel",
    "wwwUrl": "URL",
    "description": "Beschreibung",
    "license": "Lizenz",
    "oer": "OER",
    "subjects": "Faecher",
    "educationalContext": "Bildungsstufen",
    "oehLrt": "Inhaltstypen",
    "language": "Sprache",
    "keywords": "Schlagworte",
    "contentCount": "Inhaltsanzahl",
}
# Internal (exact indexing/workflow status, raw provenance)
NODE_INTERNAL = {
    "editorialStatus": "Erschliessungsstatus (genau)",
    "wfStatus": "Workflow-Status",
    "replicationSource": "replicationsource (Knoten-Herkunft)",
    "generalIdentifier": "general_identifier (Crawler-Bindung)",
    "nodeId": "Node-ID",
    "modified": "zuletzt geaendert",
}


def coarse_erschliessung(content_count: int, has_node: bool) -> str:
    """Public, coarse indexing statement (without the internal status code)."""
    if content_count and content_count > 0:
        return "im Bestand verfuegbar"
    if has_node:
        return "Quelle erfasst, (noch) keine Inhalte"
    return "nur als Bezugsquelle bekannt"


# Which flags may be shown publicly?
# Provenance markers (WLO_MIGRATION/LEGACY_BINDUNG/TYP_NICHT_QUELLE) are public,
# so that for every source one can see HOW it is bound/ingested (transparency).
PUBLIC_FLAGS = {"FACETS_ONLY", "OER", "KEINE_URL", "ZWEITDATENSATZ",
                "WLO_MIGRATION", "LEGACY_BINDUNG", "TYP_NICHT_QUELLE"}
INTERNAL_FLAGS = {"FEHLTAGGING", "BLACKLIST", "WHITELIST", "DUBLETTE_VERDACHT",
                  "INHALT_VERDACHT", "PUB_INKONSISTENT",   # reserved (these + KEINE_URL not currently produced)
                  # team data-problem markers (surfaced via the team filter)
                  "METADATEN_DUENN", "BQ_EINZELINHALT", "BINDUNG_UNVOLLSTAENDIG",
                  "QD_OHNE_BEZUGSQUELLE", "OHNE_STATUS", "STATUS_INKONSISTENT",
                  "NICHT_PUBLIZIERT", "SPIDER_UNEINDEUTIG", "BQ_OHNE_QD", "BQ_SUBCHANNEL"}

# Records carrying one of these flags are hidden from the default/end-user list
# AND from the public "Quellenverwaltung" counts, so the customer sees clean data:
#   BLACKLIST      sorted-out non-sources (single materials / duplicates)
#   ZWEITDATENSATZ secondary dataset of an already-listed Bezugsquelle (its content
#                  is already counted on the primary record -> it would double-count)
# The team filter reveals each category on demand via flag=<NAME>. Defined here once;
# filtering.py and stats.py both consume it so the list totals and the stats stay in sync.
HIDDEN_BY_DEFAULT = ("BLACKLIST", "ZWEITDATENSATZ")
