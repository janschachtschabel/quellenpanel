"""views.py — flat export view of the records (CSV/JSON).

The per-source/tier serialization (public/internal separation) lives in serialize.py; this
module only provides the leak-safe flattened row used by the /api/export.{csv,json} endpoints.
"""
import field_policy as fp

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
