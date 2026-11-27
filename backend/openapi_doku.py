"""openapi_doku.py — descriptions and examples for /openapi.json (Diensteleitfaden: a readable spec).

The routes keep their signatures short; this module adds, after FastAPI built the spec,
  - a description for every query, path and header parameter (by name; the filters are shared by several routes),
  - a 200 example for the public read endpoints and the one error shape for 4xx/5xx answers.
The examples are shortened real answers (WLO, tier 0); a test checks their keys against live answers.
"""
from __future__ import annotations

PARAMETER = {
    # list, key figure and exports (one filter definition, app._filters)
    "q": "Volltextsuche in Name, Beschreibung und Bezugsquelle, z. B. `physik`.",
    "subject": "Fach, genau ein Wert aus `/api/meta/filters` → `subjects`, z. B. `Mathematik`.",
    "level": "Bildungsstufe, ein Wert aus `levels`, z. B. `Sekundarstufe I`.",
    "lrt": "Inhaltstyp, ein Wert aus `lrts`, z. B. `Video`.",
    "erschliessung": "Erschließungsstatus, ein Wert aus `erschliessung`.",
    "oer": "`true`: nur Quellen mit freier Lizenz (OER); `false`: nur ohne.",
    "crawler": "`true`: nur Quellen mit Crawler; `false`: nur ohne.",
    "min_count": "Mindestzahl an Inhalten im Repository (Standard 1, `0` zeigt auch leere Quellen).",
    "sort": "Sortierung: `contentCount` (Zahl der Inhalte) oder `name`.",
    "order": "Richtung: `desc` (Standard) oder `asc`.",
    "page": "Seite, ab 1.",
    "page_size": "Einträge je Seite, 1 bis 200 (Standard 50).",
    "flag": "Nur Team (Stufe 2): nur Quellen mit diesem Datenproblem, z. B. `DUBLETTE_VERDACHT`.",
    "show_blacklist": "Nur Team (Stufe 2): auch Quellen auf der Blacklist zeigen.",
    "only_field_profile": "Nur Team (Stufe 2): nur Quellen mit Feld-Steckbrief.",
    "has_node": "Nur Team (Stufe 2): mit (`true`) oder ohne (`false`) Quelldatensatz im Repository.",
    "has_bezugsquelle": "Nur Team (Stufe 2): mit oder ohne Bezugsquelle.",
    "has_spider": "Nur Team (Stufe 2): mit oder ohne Crawler-Kennung.",
    # single source and its live contents
    "source_id": "ID aus der Liste, z. B. `crawler:bpb_spider` (Crawler) oder `node:<uuid>`.",
    "max_items": "Zahl der Beispielinhalte, 1 bis 50 (Standard 12).",
    "skip": "Übersprungene Inhalte, zum Blättern (Standard 0).",
    "url": "Vorschaubild-URL auf dem Repository-Host (nur HTTPS, nur dieser Host).",
    # passwords (headers only, never in the URL)
    "x-tier1-password": "Passwort für Stufe 1 auf der Partner-Instanz (`QE_TIER1_PASSWORD`).",
    "x-team-password": "Team-Passwort (`QE_TEAM_PASSWORD`). Anmelden mit `POST /api/auth`, danach gilt die Sitzung.",
    # team area (corrections, imports)
    "id_": "Nummer der Korrektur.",
    "wer": "Kürzel der bearbeitenden Person für den Verlauf, z. B. `JS`.",
    "version": "Stand der Korrekturliste aus der letzten Antwort (optimistische Sperre; 409 bei Abweichung).",
    "limit": "Höchstzahl der Verlaufseinträge, 1 bis 5000 (Standard 200).",
    "format": "Format der hochgeladenen Datei: `csv`, `json` oder `xlsx`.",
    "modus": "`ergaenzen` (Standard) fügt hinzu und ändert; `ersetzen` ersetzt die ganze Liste (mit Sicherung).",
}

_ITEM = {
    "id": "crawler:bpb_spider", "name": "Bundeszentrale für politische Bildung", "contentCount": 62867,
    "url": "https://www.bpb.de/",
    "searchUrl": "https://suche.wirlernenonline.de/search/de/search?filters=…",
    "bezugsquelle": "Bundeszentrale für politische Bildung",
    "description": "Die Webseite der Bundeszentrale für politische Bildung bietet vielseitige Materialien …",
    "subjects": ["Geschichte", "Politik"], "educationalContext": ["Sekundarstufe I", "Sekundarstufe II"],
    "contentTypes": ["Quelle"], "license": "COPYRIGHT_FREE", "oer": True, "language": "Deutsch (Deutschland)",
    "previewUrl": "https://redaktion.openeduhub.net/edu-sharing/preview?nodeId=…",
    "erschliessungsstatus": "im Bestand verfuegbar",
    "quality": {"Login": "ohne Anmeldung", "Kosten": "nein", "DSGVO": "Datensparsam"},
}

BEISPIELE = {
    "/api/sources": {"tier": 0, "total": 3558, "page": 1, "pageSize": 1, "pages": 3558, "items": [_ITEM]},
    "/api/sources/{source_id}": {**_ITEM, "keywords": ["Politik", "Demokratie"], "targetGroup": ["Lehrer/in"],
                                 "ageRange": "10-99", "author": "", "curriculum": []},
    "/api/sources/{source_id}/contents": {"total": 62867, "nodes": [{
        "title": "Was ist Demokratie?", "previewUrl": "https://redaktion.openeduhub.net/edu-sharing/preview?nodeId=…",
        "url": "https://www.bpb.de/…", "description": "Erklärfilm …", "subjects": ["Politik"],
        "keywords": ["Demokratie"]}]},
    "/api/kennzahl": {"quellen": 3558, "inhalte": 311219},
    "/api/meta/filters": {"kinds": ["crawler", "manuell", "bezugsquelle"], "subjects": ["Biologie", "Chemie"],
                          "levels": ["Primarstufe", "Sekundarstufe I"], "lrts": ["Quelle", "Video"], "erschliessung": [],
                          "licenses": ["CC_BY"],
                          "languages": ["Deutsch (Deutschland)"]},
    "/api/stats": {"total": 3721, "totalContents": 304800, "withQuelldatensatz": 824, "crawlerCount": 55,
                   "oer": {"count": 162, "percent": 4.4},
                   "topByContent": [{"value": "Bundeszentrale für politische Bildung", "count": 62867}],
                   "topSubjects": [{"value": "Biologie", "count": 141}],
                   "topLevels": [{"value": "Sekundarstufe II", "count": 594}]},
    "/api/health": {"status": "ok", "records": 3558, "role": "public"},
    "/api/capabilities": {"maxTier": 0, "role": "public", "publicOnly": True, "tier1Gated": False,
                          "teamAvailable": False, "repoUrl": "https://redaktion.openeduhub.net",
                          "branding": {"primary": "#003b7c", "accent": "#e4f700"}},
}

_FEHLER = {
    "400": ("Ungültige Anfrage", "bad_request"),
    "401": ("Anmeldung nötig", "unauthorized"),
    "403": ("Keine Berechtigung für diese Stufe", "forbidden"),
    "404": ("Quelle nicht gefunden", "not_found"),
    "409": ("Die Liste wurde inzwischen geändert", "conflict"),
    "429": ("Zu viele Anfragen. Bitte kurz warten.", "too_many_requests"),
    "502": ("Inhalte des Repositorys derzeit nicht abrufbar", "bad_gateway"),
    "503": ("Daten werden geladen", "service_unavailable"),
}

# Which error answers each documented read can give (besides 422, which FastAPI documents itself).
_FEHLER_JE_PFAD = {
    "/api/sources": ("503",),
    "/api/sources/{source_id}": ("404", "503"),
    "/api/sources/{source_id}/contents": ("404", "429", "502", "503"),
    "/api/kennzahl": ("503",),
    "/api/meta/filters": ("503",),
    "/api/stats": ("503",),
}


def _fehler(code: str) -> dict:
    message, slug = _FEHLER[code]
    retry = " Mit `Retry-After` und `retryAfter`, wenn ein späterer Versuch helfen kann." if code in ("429", "502", "503") else ""
    return {"description": message + "." + retry,
            "content": {"application/json": {"example": {
                "error": slug, "message": message, "status": int(code),
                "trace_id": "463ac35c9f6413ad48485a3953bb6124"}}}}


def ergaenze(spec: dict) -> dict:
    """Fill in parameter descriptions and examples; returns the same (mutated) spec."""
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            for p in op.get("parameters", []):
                if not p.get("description") and p["name"] in PARAMETER:
                    p["description"] = PARAMETER[p["name"]]
            if method != "get":
                continue
            responses = op.setdefault("responses", {})
            if path in BEISPIELE:
                ok = responses.setdefault("200", {"description": "Erfolg"})
                ok.setdefault("content", {}).setdefault("application/json", {})["example"] = BEISPIELE[path]
            for code in _FEHLER_JE_PFAD.get(path, ()):
                responses.setdefault(code, _fehler(code))
    return spec
