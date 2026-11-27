"""wlo_content.py — live lookup of a source's content items from the public repository API.

The detail view shows example content of a source, so even node-less crawlers (YouTube,
Bayerischer Rundfunk …) — which carry no own preview/description — surface their real
material. Read-only NGSearch by the publisher or spider property (profile); public endpoint, no auth,
urllib only (no extra dependency).
"""
import json
import urllib.request

import config
import obs
import repo_profile

# Built from the configurable repository base (config.REPO_URL) and the profile's metadata set,
# so the app can run against any edu-sharing repository. Preview URLs in the response are
# already absolute (returned by whichever repo answered), so they follow REPO_URL automatically.
def _ngsearch(n: int, s: int) -> str:
    return (f"{config.REPO_URL}/edu-sharing/rest/search/v1/queries/-home-/{repo_profile.get().mds}/"
            f"ngsearch?contentType=FILES&maxItems={n}&skipCount={s}&propertyFilter=-all-")


def _render(node_id: str) -> str:
    return f"{config.REPO_URL}/edu-sharing/components/render/{node_id}"


def _first(props: dict, key: str) -> str:
    v = props.get(key)
    if isinstance(v, list):
        return v[0] if v else ""
    return v or ""


def fetch_contents(prop: str, value: str, max_items: int = 12, skip: int = 0) -> dict:
    """Up to `max_items` WLO content items where `prop` == `value`.

    Crawlers are matched by the replication-source property (the spider), publisher-based
    sources by the publisher property (both named in the profile). Shape: {"total": int, "nodes": [{title, previewUrl, url,
    subjects}]}. Raises on a network/API error so the caller can answer 502 and the detail
    degrades gracefully.
    """
    body = json.dumps({
        "criteria": [{"property": prop, "values": [value]}]
    }).encode("utf-8")
    req = urllib.request.Request(
        _ngsearch(max_items, skip), data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 **obs.outgoing_headers()},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 — fixed https host
            data = json.load(resp)
    except Exception:
        obs.UPSTREAM.labels("repository", "error").inc()
        raise
    obs.UPSTREAM.labels("repository", "ok").inc()
    f = repo_profile.get().felder
    nodes = []
    for n in data.get("nodes", []):
        props = n.get("properties", {}) or {}
        subjects = [v for v in props.get(f["subjects_entry"], []) if not str(v).startswith("http")]
        desc = _first(props, f["description"])
        keywords = [k for k in (props.get(f["keywords"]) or []) if isinstance(k, str) and k.strip()]
        nodes.append({
            "title": n.get("title") or _first(props, f["title"]) or n.get("name") or "WLO-Inhalt",
            "previewUrl": (n.get("preview") or {}).get("url", ""),
            "url": _first(props, f["www_url"]) or _render(n.get("ref", {}).get("id", "")),
            "description": desc[:240] if isinstance(desc, str) else "",
            "subjects": subjects[:3],
            "keywords": keywords[:8],
        })
    return {"total": (data.get("pagination") or {}).get("total", len(nodes)), "nodes": nodes}
