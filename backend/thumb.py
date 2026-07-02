"""thumb.py — preview-image proxy for the client-side PDF export.

jsPDF.addImage cannot draw a cross-origin repository thumbnail (canvas CORS taint), so the SPA
fetches it through this same-origin proxy instead. Only the configured repository host is allowed
(repo-neutral; NOT an open proxy), raster images only, size-capped, and per-client rate limited.
Mounted as its own router so app.py stays the tier/data web layer, not an image proxy too.
"""
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query, Request, Response

import config
import ratelimit

router = APIRouter()

_CACHE: dict[str, tuple[bytes, str]] = {}
_CACHE_BYTES = 0                       # running total of cached image bytes
_CACHE_MAX_BYTES = 128 * 1024 * 1024   # total cache budget (thousands of real previews; bounds memory)
_REPO_HOST = (urlparse(config.REPO_URL).hostname or "").lower()
_MAX_BYTES = 5 * 1024 * 1024           # hard cap per preview image (5 MB)


@router.get("/api/thumb")
def thumb(request: Request, url: str = Query(..., description="Preview URL on the configured repository host")):
    if not ratelimit.fetch_rate_ok(request):
        raise HTTPException(429, "Zu viele Anfragen. Bitte kurz warten.")
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    # HTTPS only, and only the EXACT configured repository host (or a sub-domain of it) — repo-neutral,
    # never an open proxy. Matching the exact host (not the registrable domain) means a deployment
    # against a multi-label TLD (e.g. example.co.uk) cannot accidentally widen the allow-list.
    if parts.scheme != "https" or not (host == _REPO_HOST or host.endswith("." + _REPO_HOST)):
        raise HTTPException(400, "Host nicht erlaubt.")
    cached = _CACHE.get(url)
    if cached is None:
        rr = None
        try:
            # Do NOT follow redirects: the host allow-list above only validated the INITIAL url, so a
            # 3xx from the allowed host (open redirect / user-controlled render link) could otherwise
            # bounce the server-side fetch to an internal address (SSRF). Any redirect is refused.
            rr = requests.get(url, timeout=8, stream=True, allow_redirects=False)
            if 300 <= rr.status_code < 400:
                raise HTTPException(502, "Vorschau nicht abrufbar.")
            rr.raise_for_status()
            ct = rr.headers.get("Content-Type", "image/jpeg")
            # Raster images only — reject SVG (can embed script) and any non-image payload.
            if not ct.startswith("image/") or "svg" in ct.lower():
                raise HTTPException(415, "Kein Bild.")
            # Reject oversized images: trust the declared length when present, and enforce the cap
            # while streaming so a lying/absent Content-Length cannot bust the memory budget.
            declared = rr.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > _MAX_BYTES:
                raise HTTPException(413, "Vorschau zu groß.")
            buf = bytearray()
            for chunk in rr.iter_content(8192):
                buf.extend(chunk)
                if len(buf) > _MAX_BYTES:
                    raise HTTPException(413, "Vorschau zu groß.")
            content = bytes(buf)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "Vorschau nicht abrufbar.") from None
        finally:
            if rr is not None:
                rr.close()
        cached = (content, ct)
        global _CACHE_BYTES
        if _CACHE_BYTES + len(content) <= _CACHE_MAX_BYTES:
            _CACHE[url] = cached
            _CACHE_BYTES += len(content)
    content, ct = cached
    return Response(content=content, media_type=ct,
                    headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})
