"""bootstrap.py — the team instance's data at start, without data in the image.

  seed(data_dir)     fetches each MISSING crawler.csv / korrekturen.csv / truth.json from QE_SEED_URL
                     (atomic; existing files are never overwritten; a 404 for truth.json is fine)
  start_team()       "ready" when truth.json is (or becomes, via seed) available and loads;
                     otherwise starts the rebuild job in the background and returns "building" —
                     the API answers 503 "Daten werden aufgebaut" until the job has loaded data
  write_status / read_status   $QE_DATA_DIR/status.json: {status, startedAt, finishedAt, error}
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

import config
import export_store
import obs
import store

log = logging.getLogger("quellenpanel.bootstrap")

SEED_FILES = ("crawler.csv", "korrekturen.csv", "truth.json")
_OPTIONAL = {"truth.json"}
_TIMEOUT = 60
_MAX_BYTES = 200 * 1024 * 1024


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def seed(data_dir: Path) -> list[str]:
    """Download the missing seed files; return the names written. Errors are logged, not raised."""
    base = config.seed_url()
    if not base:
        return []
    loaded = []
    for name in SEED_FILES:
        target = Path(data_dir) / name
        if target.exists():
            continue
        url = f"{base.rstrip('/')}/{name}"
        req = urllib.request.Request(url, headers=obs.outgoing_headers())
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — configured URL
                data = resp.read(_MAX_BYTES + 1)
            if len(data) > _MAX_BYTES:
                raise ValueError("zu groß")
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and name in _OPTIONAL:
                continue
            log.warning("Seed %s nicht geladen (HTTP %s)", name, exc.code)
            continue
        except (OSError, ValueError) as exc:
            log.warning("Seed %s nicht geladen (%s)", name, exc)
            continue
        _atomic_write(target, data)
        loaded.append(name)
    if loaded:
        log.info("Seed geladen: %s", ", ".join(loaded))
    return loaded


def load_and_publish() -> None:
    """Load truth.json into memory and rebuild the tier exports (memory + data dir)."""
    store.load()
    export_store.rebuild_from_records(store._DATA["records"], store._DATA["meta"],
                                      config.data_dir() / "exports")


def start_team() -> str:
    import refresh                      # late: refresh imports this module for its status file

    if not config.truth_path().is_file():
        seed(config.data_dir())
    if config.truth_path().is_file():
        load_and_publish()
        return "ready"
    log.warning("Keine truth.json im Datenverzeichnis: Datenaufbau startet, API antwortet bis dahin 503")
    refresh.start()
    return "building"


def _status_path() -> Path:
    return config.data_dir() / "status.json"


def write_status(state: dict) -> None:
    """Persist the rebuild status (fail-soft: a read-only data dir only loses the file)."""
    keep = {k: state.get(k) for k in ("status", "startedAt", "finishedAt", "error")}
    try:
        _atomic_write(_status_path(), json.dumps(keep, ensure_ascii=False).encode("utf-8"))
    except OSError:
        log.warning("status.json nicht schreibbar", exc_info=True)


def read_status() -> dict | None:
    try:
        d = json.loads(_status_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None
