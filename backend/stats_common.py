"""stats_common.py — shared helpers/constants of the statistics aggregation.

Pure bucket/normalization helpers and field lists, shared by stats.py (public)
and stats_team.py (team). No IO dependency.
"""


def _bracket(n):
    if n <= 0: return "0"
    if n < 5: return "1–4"
    if n < 10: return "5–9"
    if n < 50: return "10–49"
    if n < 100: return "50–99"
    if n < 500: return "100–499"
    if n < 1000: return "500–999"
    if n < 10000: return "1k–9.9k"
    return "≥10k"


_HOW_BUCKETS = [
    ("hard-coded", "hard-coded"), ("mapping", "via Mapping"), ("url", "aus URL"),
    ("dom", "aus DOM gescraped"), ("lrmi", "via LRMI"), ("rss", "aus RSS"),
    ("api", "aus API"), ("csv", "aus CSV"), ("trafilatura", "Volltext-Extraktion"),
]


def _how_bucket(how):
    h = (how or "").lower()
    for key, label in _HOW_BUCKETS:
        if key in h:
            return label
    return "aus Quelldaten" if h == "" else "sonstige"


def _ctype_bucket(t):
    """Normalize the crawler type (Crawler-Type from datencrawler.csv) into a few classes."""
    h = (t or "").lower()
    if "sitemap" in h:
        return "Webseite (Sitemap)"
    if "rss" in h:
        return "RSS"
    if "api" in h:
        return "API"
    if any(k in h for k in ("csv", "zip", "dump", "import", "sheet")):
        return "Dump/Import"
    if "webseite" in h or "scrap" in h or "website" in h:
        return "Webseite (Scraping)"
    return "Sonstige"


# Descriptive metadata fields for the tier-1 fill-level charts, evaluated over the
# Quelldatensätze (records with a node). Two balanced categories so the view splits into two
# equal-sized charts. (label, category, where, key) — where "public" = key in r["public"],
# "root" = attribute on the record itself (previewUrl/quality).
_BESCHREIBENDE_FELDER = [
    ("Titel", "inhalt", "public", "Titel"),
    ("Beschreibung", "inhalt", "public", "Beschreibung"),
    ("Schlagworte", "inhalt", "public", "Schlagworte"),
    ("Vorschaubild", "inhalt", "root", "previewUrl"),
    ("URL", "inhalt", "public", "URL"),
    ("Fächer", "einordnung", "public", "Faecher"),
    ("Bildungsstufen", "einordnung", "public", "Bildungsstufen"),
    ("Inhaltstypen", "einordnung", "public", "Inhaltstypen"),
    ("Lizenz", "einordnung", "public", "Lizenz"),
    ("Qualitätsmerkmale", "einordnung", "root", "quality"),
]

# Fields for the fill-level evaluation (team): metadata on the Quelldatensatz +
# AI/legal notes from the crawler profile. (label, public key)
_FUELL_META = [
    ("Beschreibung", "Beschreibung"), ("Lizenz", "Lizenz"), ("OER", "OER"),
    ("Fächer", "Faecher"), ("Bildungsstufen", "Bildungsstufen"), ("Inhaltstypen", "Inhaltstypen"),
    ("Sprache", "Sprache"), ("Schlagworte", "Schlagworte"), ("Urheber", "Urheber"),
    ("Zielgruppe", "Zielgruppe"), ("Alter", "Alter"), ("Sprachniveau", "Sprachniveau"),
    ("Lehrplanbezug", "Lehrplanbezug"), ("FSK", "FSK"),
]
_FUELL_KI = [
    ("robots.txt", "robots.txt"), ("TDM-Hinweis (§44b)", "TDM-Hinweis (§44b)"),
    ("AGB/Nutzungsbedingungen", "AGB/Nutzungsbedingungen"), ("Lizenz-Check", "Lizenz-Check"),
    ("API-Nutzungsbedingungen", "API-Nutzungsbedingungen"),
]
