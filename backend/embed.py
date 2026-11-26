"""embed.py — iframe pages for the widgets (/embed/<name>?…).

A tiny HTML page without inline script: it loads the widget script and embed.js (height via
postMessage, only when the parent asks) and renders ONE element. Query parameters become element
attributes — only the allowed names, HTML-escaped, capped at 200 characters.
The page carries a CSP with frame-ancestors from QE_FRAME_ANCESTORS.
"""
from __future__ import annotations

import html

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

import config

WIDGETS = ("quellen-liste", "quellen-top", "quellen-zahl", "quelle", "quellen-statistik",
           "quellen-kacheln", "quellenpanel")
ATTRIBUTE = ("fach", "bildungsstufe", "suche", "max", "sprache", "nur-oer", "variante", "quelle")
MAX_WERT = 200


def seite(name: str, params: dict[str, str]) -> HTMLResponse:
    if name not in WIDGETS:
        raise HTTPException(404, "Not Found")
    attrs = "".join(f' {k}="{html.escape(str(params[k])[:MAX_WERT], quote=True)}"'
                    for k in ATTRIBUTE if k in params)
    tag = f"wlo-{name}"
    body = (
        "<!DOCTYPE html>\n<html lang=\"de\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>Quellenverzeichnis</title>"
        '<link rel="stylesheet" href="/widgets/embed.css">'
        '<script src="/widgets/quellenpanel-widgets.js" defer></script>'
        '<script src="/widgets/embed.js" defer></script>'
        f"</head><body><{tag}{attrs}></{tag}></body></html>\n")
    csp = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src * data:; "
           f"connect-src 'self'; frame-ancestors {config.frame_ancestors()}")
    return HTMLResponse(body, headers={"Content-Security-Policy": csp, "Cache-Control": "no-cache"})
