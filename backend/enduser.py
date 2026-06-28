"""enduser.py — the public, end-user view of a source.

Deliberately slim: ONLY the information an end user cares about (like the old Quellenliste) —
NO data-problem flags, NO internal fields, NO provenance/confidence. The data behind it is the
full Quellensteckbriefe "data truth" join; this module is the gate that keeps problems out.
"""
import json
import logging
import urllib.parse
from pathlib import Path

import config

log = logging.getLogger("quellenliste-x.enduser")
_SUPPLEMENTS_PATH = Path(__file__).parent / "data" / "source_supplements.json"


def _search_url(name: str) -> str:
    """Link to this source's contents in the public WLO search (config.SEARCH_URL), e.g.
    …/search/de/search?filters={"source":["Serlo"]}. Lets users jump from a source to all
    its material in the search, alongside the direct link to the source's own website."""
    if not name:
        return ""
    flt = json.dumps({"source": [name]}, separators=(",", ":"))
    return f"{config.SEARCH_URL}/search/de/search?filters={urllib.parse.quote(flt, safe=':')}"


def _load_supplements() -> dict:
    """Curated source-level description + preview for node-less sources whose own metadata is
    empty (YouTube, Bayerischer Rundfunk, OER Commons and ~30 smaller publishers). Sourced from
    the old Quellenliste — see data/source_supplements.json. Keyed by lowercased source name.
    Fail-soft: a missing or broken file just means those sources fall back to the live
    example-content backfill, so serving never breaks on it."""
    try:
        raw = json.loads(_SUPPLEMENTS_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}  # drop _provenance
    except FileNotFoundError:
        return {}
    except Exception:  # noqa: BLE001 — enhancement only; never 500 a card over a bad data file
        log.exception("source_supplements.json could not be loaded")
        return {}


_SUPPLEMENTS = _load_supplements()


def card(r: dict) -> dict:
    """Compact view for the tile/list (Kachel/Liste)."""
    p = r["public"]
    # Node-less sources (YouTube, BR, OER Commons, smaller publishers) carry no own
    # description/preview. Fill those from the curated supplement so tiles/list/detail show
    # source-fitting text + image instead of a random live content. Only EMPTY fields are
    # filled — sources with their own data keep it.
    sup = _SUPPLEMENTS.get((r.get("name") or "").lower(), {})
    return {
        "id":                 r["id"],
        "name":               r["name"],
        "contentCount":       r.get("contentCount") or 0,
        "url":                p.get("URL", ""),
        "searchUrl":          _search_url(r["name"]),
        # Bezugsquelle (publisher) — public-facing (shown in the Steckbriefe header), surfaced for
        # the detail's Grund-Informationen and the PDF. Empty for node-only sources.
        "bezugsquelle":       (r.get("identity") or {}).get("bezugsquelle", ""),
        "description":        p.get("Beschreibung", "") or sup.get("description", ""),
        "subjects":           p.get("Faecher", []),
        "educationalContext": p.get("Bildungsstufen", []),
        "contentTypes":       p.get("Inhaltstypen", []),
        "license":            p.get("Lizenz", ""),
        "oer":                bool(p.get("OER")),
        "language":           p.get("Sprache", ""),
        "previewUrl":         r.get("previewUrl", "") or sup.get("previewUrl", ""),
        # Editorial cataloguing status — carried for the list-view column (NOT rendered on
        # tiles). The one internal field deliberately surfaced; rest of `internal` stays hidden.
        "erschliessungsstatus": (r.get("internal") or {}).get("Erschliessungsstatus (genau)") or "",
        # Quality characteristics (cost, ads, login, data protection, legal cleanliness, …) —
        # informative for end users (not a data problem); already a clean labelled dict.
        "quality": r.get("quality") or {},
    }


def detail(r: dict) -> dict:
    """Full end-user profile (Steckbrief) — the card plus a few more public fields."""
    p = r["public"]
    d = card(r)
    d.update({
        "keywords":    p.get("Schlagworte", []),
        "author":      p.get("Urheber", ""),
        "targetGroup": p.get("Zielgruppe", []),
        "curriculum":  p.get("Lehrplanbezug", []),
        "ageRange":    p.get("Alter", ""),
    })
    return d  # erschliessungsstatus is already provided by card()
