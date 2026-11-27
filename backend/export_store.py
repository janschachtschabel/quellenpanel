"""export_store.py — the current export document per public tier, held in memory.

Team instance: rebuilt from the merged records after every load / reload / refresh and written to
$QE_DATA_DIR/exports/ for the partner/public instances. Partner/public instances only ever hold
these documents: load_tmp() restores the last copy from /tmp for a fast restart, load_remote()
fetches QE_EXPORT_SOURCE (URL with ETag, or a file path), start_polling() refreshes it. On any
error the last valid document stays.
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import config
import export_query
import exports
import obs

log = logging.getLogger("quellenpanel.export")

TMP_DIR = Path(tempfile.gettempdir())
_TIMEOUT = 20
RETRY_SECONDS = 15        # while a tier export is still missing (e.g. the team starts later)
_LOCK = threading.Lock()
_POLLING = False
_DOCS: dict[int, dict | None] = {0: None, 1: None}
_TAGS: dict[int, str | None] = {0: None, 1: None}


def current(tier: int) -> dict | None:
    return _DOCS.get(tier)


def etag(tier: int) -> str | None:
    return _TAGS.get(tier)


def set_doc(tier: int, doc: dict) -> None:
    """Validate and swap in a new export (readers see either the old or the new document)."""
    exports.validate(doc, tier)
    tag = exports.etag(doc)
    export_query.index(doc)       # build the id index BEFORE publishing: readers never mutate a doc
    with _LOCK:
        _DOCS[tier] = doc
        _TAGS[tier] = tag


def rebuild_from_records(records: list[dict], meta: dict, out_dir: Path | None) -> None:
    """Team: build both exports into memory; write them to out_dir when given (fail-soft)."""
    docs = {tier: exports.build_export(records, meta, tier) for tier in exports.TIERS}
    for tier, doc in docs.items():
        set_doc(tier, doc)
    if out_dir is None:
        return
    try:
        for tier, doc in docs.items():
            exports.write_doc(doc, Path(out_dir) / f"stufe{tier}.json")
    except OSError:
        log.warning("Export konnte nicht nach %s geschrieben werden; Speicher-Export gilt weiter",
                    out_dir, exc_info=True)


def _tmp_path(tier: int) -> Path:
    return Path(TMP_DIR) / f"quellenpanel-stufe{tier}.json"


def _fetch(src: str, tier: int) -> bytes | None:
    """Raw bytes of the source; None when an HTTP source answers 304 Not Modified."""
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"Accept": "application/json", **obs.outgoing_headers()})
        tag = etag(tier)
        if tag and current(tier) is not None:
            req.add_header("If-None-Match", tag)
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — configured URL
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return None
            raise
    return Path(src).read_bytes()


def export_url(template: str, tier: int) -> str:
    """QE_EXPORT_SOURCE with `{tier}` filled in; other braces (e.g. in a query) stay as they are."""
    return template.replace("{tier}", str(tier))


def load_remote(tier: int) -> bool:
    """Fetch, validate and swap in the tier export from QE_EXPORT_SOURCE. False on any error."""
    template = config.export_source()
    if not template:
        return False
    src = export_url(template, tier)
    try:
        raw = _fetch(src, tier)
        if raw is None:                       # 304: what we hold is current
            obs.EXPORT_FETCH.labels(str(tier), "not_modified").inc()
            return True
        doc = json.loads(raw)
        set_doc(tier, doc)
    except Exception as exc:  # noqa: BLE001 — keep serving the last valid export
        obs.EXPORT_FETCH.labels(str(tier), "error").inc()
        log.warning("Export Stufe %d von %s nicht übernommen (%s); letzter Stand bleibt", tier, src, exc)
        return False
    obs.EXPORT_FETCH.labels(str(tier), "ok").inc()
    try:
        exports.write_doc(doc, _tmp_path(tier))
    except OSError:
        log.warning("Export-Kopie nach %s nicht möglich", _tmp_path(tier), exc_info=True)
    return True


def load_tmp(tier: int) -> bool:
    """Restore the /tmp copy written by an earlier load (fast restart within the same pod)."""
    p = _tmp_path(tier)
    if not p.is_file():
        return False
    try:
        set_doc(tier, json.loads(p.read_bytes()))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Export-Kopie %s unbrauchbar (%s)", p, exc)
        return False


def start_polling(tiers: tuple[int, ...], minutes: int) -> None:
    """Re-fetch the exports every `minutes` in a daemon thread (0 = off)."""
    global _POLLING
    if minutes <= 0 or _POLLING:
        return
    _POLLING = True
    threading.Thread(target=_poll_loop, args=(tiers, minutes), name="export-poll", daemon=True).start()


def next_delay(tiers: tuple[int, ...], minutes: int) -> int:
    """Seconds to the next fetch: the poll interval once every tier is held, else a short retry."""
    if all(current(t) is not None for t in tiers):
        return minutes * 60
    return min(RETRY_SECONDS, minutes * 60)


def _poll_loop(tiers: tuple[int, ...], minutes: int) -> None:
    """Never dies on an error: a failed round is logged and retried at the next interval."""
    while True:
        time.sleep(next_delay(tiers, minutes))
        for t in tiers:
            try:
                load_remote(t)
            except Exception:  # noqa: BLE001
                log.exception("Export-Abruf Stufe %d fehlgeschlagen", t)


def reset() -> None:
    """Forget all exports (tests)."""
    with _LOCK:
        for t in exports.TIERS:
            _DOCS[t] = None
            _TAGS[t] = None
