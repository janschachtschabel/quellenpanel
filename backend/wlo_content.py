"""wlo_content.py — live lookup of a source's content items from the public WLO API.

The detail view shows example content of a source, so even node-less crawlers (YouTube,
Bayerischer Rundfunk …) — which carry no own preview/description — surface their real
material. Read-only NGSearch by `ccm:oeh_publisher_combined`; public endpoint, no auth,
urllib only (no extra dependency).
"""
import json
import urllib.request

import config

# Built from the configurable repository base (config.REPO_URL) so the app can run against a
# different edu-sharing repository than production. Preview URLs in the response are already
# absolute (returned by whichever repo answered), so they follow REPO_URL automatically.
_NGSEARCH = (
    config.REPO_URL + "/edu-sharing/rest/search/v1/queries/-home-/mds_oeh/"
    "ngsearch?contentType=FILES&maxItems={n}&skipCount={s}&propertyFilter=-all-"
)
_RENDER = config.REPO_URL + "/edu-sharing/components/render/{id}"


def _first(props: dict, key: str) -> str:
    v = props.get(key)
    if isinstance(v, list):
        return v[0] if v else ""
    return v or ""


def fetch_contents(prop: str, value: str, max_items: int = 12, skip: int = 0) -> dict:
    """Up to `max_items` WLO content items where `prop` == `value`.

    Crawlers are matched by `ccm:replicationsource` (the spider), publisher-based sources by
    `ccm:oeh_publisher_combined`. Shape: {"total": int, "nodes": [{title, previewUrl, url,
    subjects}]}. Raises on a network/API error so the caller can answer 502 and the detail
    degrades gracefully.
    """
    body = json.dumps({
        "criteria": [{"property": prop, "values": [value]}]
    }).encode("utf-8")
    req = urllib.request.Request(
        _NGSEARCH.format(n=max_items, s=skip), data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 — fixed https host
        data = json.load(resp)
    nodes = []
    for n in data.get("nodes", []):
        props = n.get("properties", {}) or {}
        subjects = [v for v in props.get("ccm:taxonentry_DISPLAYNAME", []) if not str(v).startswith("http")]
        desc = _first(props, "cclom:general_description")
        keywords = [k for k in (props.get("cclom:general_keyword") or []) if isinstance(k, str) and k.strip()]
        nodes.append({
            "title": n.get("title") or _first(props, "cclom:title") or n.get("name") or "WLO-Inhalt",
            "previewUrl": (n.get("preview") or {}).get("url", ""),
            "url": _first(props, "ccm:wwwurl") or _RENDER.format(id=n.get("ref", {}).get("id", "")),
            "description": desc[:240] if isinstance(desc, str) else "",
            "subjects": subjects[:3],
            "keywords": keywords[:8],
        })
    return {"total": (data.get("pagination") or {}).get("total", len(nodes)), "nodes": nodes}
