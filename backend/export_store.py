"""export_store.py — the current export document per public tier, held in memory.

Team instance: rebuilt from the merged records after every load / reload / refresh and written to
$QE_DATA_DIR/exports/ for the partner/public instances. Partner/public instances only ever hold
these documents (see load_remote / load_tmp, added for them).
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import exports

log = logging.getLogger("quellenpanel.export")

_LOCK = threading.Lock()
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


def reset() -> None:
    """Forget all exports (tests)."""
    with _LOCK:
        for t in exports.TIERS:
            _DOCS[t] = None
            _TAGS[t] = None
