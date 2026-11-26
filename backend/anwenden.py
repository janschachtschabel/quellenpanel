"""anwenden.py — make a saved correction / crawler-table change effective, without a live fetch.

With the raw API caches on the volume ($QE_DATA_DIR/raw/quellen_nodes.json) the merge is recomputed
(truth.main → truth.json), loaded into memory and the tier exports are rewritten (seconds).
Without them (e.g. the team instance was seeded with truth.json only) the node corrections take
effect at the next data build; source supplements (descriptions, preview images) apply right away.
"""
from __future__ import annotations

import logging

import config
import enduser
import export_store
import korrektur_store
import store
import truth

_LOG = logging.getLogger("anwenden")


def _hat_rohdaten() -> bool:
    return (config.raw_dir() / "quellen_nodes.json").is_file()


def nach_aenderung() -> dict:
    with korrektur_store.lock():
        neu = _hat_rohdaten()
        if neu:
            truth.main()
            store.load()
        enduser.reload_supplements()
        if store._DATA.get("records"):
            export_store.rebuild_from_records(store._DATA["records"], store._DATA["meta"],
                                              config.data_dir() / "exports")
        _LOG.info("korrektur angewendet", extra={"neu_berechnet": neu})
        return {"neuBerechnet": neu, "wirktBeimNaechstenAufbau": not neu}


def sicher() -> dict:
    """nach_aenderung() for callers whose change is already saved: a failing recompute is logged
    and reported as "effective at the next data build", never as a failed save."""
    try:
        return nach_aenderung()
    except Exception:  # noqa: BLE001
        _LOG.exception("anwenden nach Änderung fehlgeschlagen")
        return {"neuBerechnet": False, "wirktBeimNaechstenAufbau": True, "fehler": True}
