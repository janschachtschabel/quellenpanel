"""serialize.py — single serialization entry point, tiered by audience.

One FLAT, layered shape so the Angular frontend renders every tier the same way, just with more
fields higher up (the Steckbriefe nested `public`/`full` views are NOT used here — they carry a
nested `public` dict the tile/list/detail components don't read):

  base       enduser.card (list) / enduser.detail (detail) — end-user fields, flat
  tier >= 1  detail only: the AI-usage / legal `ki` fields + crawler field-generation — "Steckbrief"
  tier >= 2  list: data-problem `flags` + `bind` (source-binding badges);
             detail: + internal fields (flat) + all flags + per-field `provenance` — team

Every result carries `searchUrl` (jump to the source's contents in the WLO search).
The tier passed in must already be resolved (see tiers.effective_tier); this function trusts it.
"""
import json
import urllib.parse

import config
import enduser

# AI-usage / legal public fields surfaced as the tier-1 "KI-Nutzung & Recht" section — the basis of
# the source's AI-usage assessment (mirrors the Quellensteckbriefe KI_KEYS, minus API-Nutzung).
_KI_KEYS = ("robots.txt", "TDM-Hinweis (§44b)", "AGB/Nutzungsbedingungen", "Lizenz-Check")

# Map the flat enduser field names back to their original `public` keys, so tier 2 can attach the
# per-field data source (provenance) to the fields the detail view actually renders.
_PROV_FIELD_MAP = {
    "description": "Beschreibung", "subjects": "Faecher",
    "educationalContext": "Bildungsstufen", "contentTypes": "Inhaltstypen",
    "keywords": "Schlagworte", "author": "Urheber", "targetGroup": "Zielgruppe",
    "curriculum": "Lehrplanbezug", "ageRange": "Alter",
}


def search_url(name: str) -> str:
    """Link to a source's contents in the public WLO search, built from the configurable SEARCH_URL."""
    if not name:
        return ""
    flt = json.dumps({"source": [name]}, separators=(",", ":"))
    return f"{config.SEARCH_URL}/search/de/search?filters={urllib.parse.quote(flt, safe=':')}"


def source(r: dict, tier: int, detail: bool = False,
           related: dict | None = None, family: int = 0) -> dict:
    """Serialize one record at the granted tier. `detail` selects the richer per-source payload.
    The Bezugsquelle family (publisher + its sub-channels, e.g. YouTube) is Audit-tier only (tier 2)
    — `family` is the sibling count for the tile/list badge, `related` the full sibling list for the
    detail view (both from store; display only, no effect on any aggregation)."""
    out = enduser.detail(r) if detail else enduser.card(r)
    out["searchUrl"] = search_url(r.get("name", ""))

    if tier >= 2:
        # Bezugsquelle-family link is Audit-tier only (team): WHICH other source datasets share a
        # Bezugsquelle is data-work context, not end-user information — a count badge on the card,
        # the full sibling list on the detail. Public / lower tiers get neither.
        if detail:
            if related:
                out["related"] = related
        elif family:
            out["familyCount"] = family
        # Team sees the EXACT editorial cataloguing status (internal code, e.g. "9."); tier 0/1 keep
        # the coarse public statement set by enduser.card (leak-safe — see field_policy).
        exact = (r.get("internal") or {}).get("Erschliessungsstatus (genau)")
        if exact:
            out["erschliessungsstatus"] = exact

    # Tier 2 list rows carry the data-problem flags (filter / indicators) plus a source-binding
    # summary, so the team tiles can show Quelldatensatz / Bezugsquelle / Spider badges.
    if tier >= 2 and not detail:
        out["flags"] = list(r.get("flags", []))
        idn = r.get("identity") or {}
        out["bind"] = {
            "node": idn.get("nodeId", ""),
            "bezugsquelle": idn.get("bezugsquelle", ""),
            "spider": idn.get("spider", ""),
        }

    if tier >= 1 and not detail:
        # Steckbrief list rows: the active crawler field count is public and useful for spotting
        # crawlers with rich metadata profiles directly in the tile/list view.
        out["fieldActiveCount"] = r.get("fieldActiveCount", 0)

    if detail and tier >= 1:
        # Steckbrief: the AI-usage / legal fields (robots.txt, TDM §44b, AGB, licence check) and the
        # crawler field-generation provenance (per metadata field: whether/how the crawler fills it).
        pub = r.get("public") or {}
        # Always expose all four KI/legal fields (empty string when the source has none), so the
        # "KI-Nutzung & Recht" section is complete and consistent — a blank field still tells the
        # editor it was checked. The frontend renders empties as "—".
        out["ki"] = {k: pub.get(k, "") for k in _KI_KEYS}
        out["fieldGeneration"] = r.get("fieldGeneration", [])
        out["fieldActiveCount"] = r.get("fieldActiveCount", 0)
        # Source binding (node id + spider) — public Steckbrief identity, surfaced for the detail /
        # PDF "Allgemeine Informationen" already at tier 1 (NOT internal: the node id is a public
        # edu-sharing render link, the spider a public crawler name).
        idn = r.get("identity") or {}
        out["binding"] = {"node": idn.get("nodeId", ""), "spider": idn.get("spider", "")}

    if detail and tier >= 2:
        # Team: internal fields (flat), the full flag set, and the per-field data source for pills —
        # keyed by the flat field names the detail view renders, plus the KI field names.
        out["internal"] = dict(r.get("internal", {}))
        out["flags"] = list(r.get("flags", []))
        prov = r.get("provenance") or {}
        mapped = {flat: prov[orig] for flat, orig in _PROV_FIELD_MAP.items() if prov.get(orig)}
        for k in _KI_KEYS:
            if prov.get(k):
                mapped[k] = prov[k]
        out["provenance"] = mapped

    return out
