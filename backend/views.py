"""views.py — serialization of the records for the API.

Implements the server-side public/internal separation (see field_policy) and
provides the flat export view (CSV/JSON). The ONE place that decides which
fields are allowed to leave a public response.
"""
import json
import logging
from pathlib import Path

import field_policy as fp

log = logging.getLogger("quellenerschliessung.views")
_SUPPLEMENTS_PATH = Path(__file__).parent / "data" / "source_supplements.json"


def _load_supplements() -> dict:
    """Curated source-level description + preview for node-less sources whose own metadata is
    empty (YouTube, Bayerischer Rundfunk, OER Commons and ~30 smaller publishers). Sourced from
    the old Quellenliste — see data/source_supplements.json. Keyed by lowercased source name.
    Fail-soft: a missing or broken file just leaves those sources blank, never crashing
    serialization."""
    try:
        raw = json.loads(_SUPPLEMENTS_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_")}  # drop _provenance
    except FileNotFoundError:
        return {}
    except Exception:  # noqa: BLE001 — enhancement only; never break serialization on a bad file
        log.exception("source_supplements.json could not be loaded")
        return {}


_SUPPLEMENTS = _load_supplements()


def public_view(r: dict) -> dict:
    """Record WITHOUT internal fields (server-side separation)."""
    # Node-less sources carry no own description/preview. Fill those (display only) from the
    # curated supplement so list/detail/PDF show source-fitting text + image. Non-mutating: a
    # copy of `public` is made when filled, so the in-memory record is untouched and the
    # fieldGeneration / confidence signals still reflect the real, un-supplemented data.
    sup = _SUPPLEMENTS.get((r.get("name") or "").lower(), {})
    pub = r["public"]
    if sup and not pub.get("Beschreibung") and sup.get("description"):
        pub = {**pub, "Beschreibung": sup["description"]}
    return {
        "id": r["id"], "name": r["name"], "kind": r["kind"],
        "contentCount": r["contentCount"], "erschliessung": r["erschliessung"],
        "identity": {k: v for k, v in r["identity"].items()},
        "public": pub, "provenance": r["provenance"],
        "fieldGeneration": r.get("fieldGeneration", []),
        "fieldActiveCount": r.get("fieldActiveCount", 0),
        "previewUrl": r.get("previewUrl", "") or sup.get("previewUrl", ""),
        "quality": r.get("quality", {}),
        "flags": [f for f in r.get("flags", []) if f in fp.PUBLIC_FLAGS],
        "confidence": r["confidence"],
        "hasInternal": bool(r.get("internal")),
    }


def full_view(r: dict) -> dict:
    v = public_view(r)
    v["internal"] = r.get("internal", {})
    v["flags"] = r.get("flags", [])   # incl. internal flags
    return v


EXPORT_COLS = ["id", "name", "kind", "bezugsquelle", "nodeId", "spider", "spiderVocabName",
               "contentCount", "erschliessung", "url", "Lizenz", "OER", "Faecher",
               "Bildungsstufen", "Inhaltstypen", "Sprache", "fieldActiveCount", "flags", "confidence"]


def flat(r: dict, team: bool = False) -> dict:
    p = r["public"]; idn = r["identity"]
    # A team export keeps EVERY flag (including the internal data-problem markers the team just
    # filtered by) and the internal confidence; the public (tier-1) export stays limited to the
    # public flag set and omits confidence — leak-safe, consistent with the per-source serializer.
    flags = r.get("flags", []) if team else [f for f in r.get("flags", []) if f in fp.PUBLIC_FLAGS]
    return {
        "id": r["id"], "name": r["name"], "kind": r["kind"],
        "bezugsquelle": idn.get("bezugsquelle", ""), "nodeId": idn.get("nodeId", ""),
        "spider": idn.get("spider", ""), "spiderVocabName": idn.get("spiderVocabName", ""),
        "contentCount": r.get("contentCount") or 0, "erschliessung": r.get("erschliessung", ""),
        "url": p.get("URL", ""), "Lizenz": p.get("Lizenz", ""),
        "OER": "ja" if p.get("OER") else "", "Faecher": " | ".join(p.get("Faecher", [])),
        "Bildungsstufen": " | ".join(p.get("Bildungsstufen", [])),
        "Inhaltstypen": " | ".join(p.get("Inhaltstypen", [])),
        "Sprache": p.get("Sprache", ""), "fieldActiveCount": r.get("fieldActiveCount", 0),
        "flags": " | ".join(flags),
        "confidence": r.get("confidence", "") if team else "",
    }
