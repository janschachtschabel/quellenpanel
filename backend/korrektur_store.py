"""korrektur_store.py — the team-maintained corrections file as state.

The file lives in $QE_DATA_DIR/korrekturen.csv. Until the team saves for the first time, the
profile's starting copy is read (and never written). Every write:
  * checks the caller's `version` (content hash it read) → VersionKonflikt on mismatch,
  * validates the row with the same rules as the loader → UngueltigeKorrektur,
  * writes atomically under a process lock,
  * appends one line to korrekturen-verlauf.csv (Zeitpunkt;Wer;Vorgang;Alt;Neu).
Replacing everything (import "ersetzen") first copies the old file to korrekturen-<ts>.csv.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
import shutil
import threading
from dataclasses import asdict, astuple
from pathlib import Path

import config
from korrekturen import Korrektur, KorrekturSet, _check, decode, load_korrekturen, parse_korrekturen, write_korrekturen

VERLAUF_HEADER = ("Zeitpunkt", "Wer", "Vorgang", "Alt", "Neu")
_FELDER = ("typ", "schluessel", "aktion", "wert", "kommentar")
_LOCK = threading.RLock()


class VersionKonflikt(Exception):
    """The file changed since the caller read it."""


class UngueltigeKorrektur(ValueError):
    """The requested change is invalid (row rules, unknown id, missing initials)."""


def store_path() -> Path:
    return config.data_dir() / "korrekturen.csv"


def verlauf_path() -> Path:
    return config.data_dir() / "korrekturen-verlauf.csv"


def _quelle() -> Path | None:
    return config.korrekturen_csv_path()


def _version(path: Path | None) -> str:
    data = path.read_bytes() if path and path.is_file() else b""
    return hashlib.sha256(data).hexdigest()[:16]


def lock() -> threading.RLock:
    """The process lock every writer of the corrections/crawler files takes."""
    return _LOCK


def _parse(data: bytes) -> KorrekturSet:
    return parse_korrekturen(decode(data)) if data else KorrekturSet()


def lesen() -> dict:
    """Entries and version from ONE read of the file (ids are positions, so they must match)."""
    path = _quelle()
    data = path.read_bytes() if path and path.is_file() else b""
    s = _parse(data)
    return {"version": hashlib.sha256(data).hexdigest()[:16],
            "eintraege": [{"id": i, **asdict(k)} for i, k in enumerate(s.eintraege)],
            "fehler": [{"zeile": m.zeile, "text": m.text} for m in s.fehler],
            "warnungen": [{"zeile": m.zeile, "text": m.text} for m in s.warnungen]}


def bestand() -> list[Korrektur]:
    return load_korrekturen(_quelle()).eintraege


def _roh_ungueltig() -> list[tuple[str, ...]]:
    return load_korrekturen(_quelle()).roh_ungueltig


def _wer(wer: str) -> str:
    wer = (wer or "").strip()
    if not wer or len(wer) > 40:
        raise UngueltigeKorrektur("Kürzel fehlt oder ist länger als 40 Zeichen.")
    return wer


def _heute() -> str:
    return datetime.date.today().isoformat()


def _zeile(k: Korrektur | None) -> str:
    return "" if k is None else "|".join(astuple(k)[:5])


def _korrektur(d: dict, wer: str) -> Korrektur:
    if not isinstance(d, dict):
        raise UngueltigeKorrektur("Korrektur fehlt.")
    v = {f: str(d.get(f) or "").strip() for f in _FELDER}
    k = Korrektur(v["typ"].lower(), v["schluessel"], v["aktion"].lower(), v["wert"], v["kommentar"],
                  wer, _heute())
    grund = _check(k)
    if grund:
        raise UngueltigeKorrektur(grund)
    return k


def verlauf_schreiben(wer: str, vorgang: str, alt: str, neu: str) -> None:
    path = verlauf_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    if not path.is_file():
        w.writerow(VERLAUF_HEADER)
    w.writerow((datetime.datetime.now().isoformat(timespec="seconds"), wer, vorgang, alt, neu))
    data = buf.getvalue().encode("utf-8")
    with open(path, "ab") as f:
        if f.tell() == 0:
            f.write(b"\xef\xbb\xbf")
        f.write(data)


def sichern(path: Path, stamm: str) -> Path | None:
    """Copy `path` to <stamm>-<YYYYmmdd-HHMMSS>.csv in the data dir (dated backup)."""
    if not path or not path.is_file():
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ziel = config.data_dir() / f"{stamm}-{ts}.csv"
    n = 1
    while ziel.exists():
        ziel = config.data_dir() / f"{stamm}-{ts}-{n}.csv"
        n += 1
    shutil.copy2(path, ziel)
    return ziel


def _schreiben(eintraege: list[Korrektur], roh: list[tuple[str, ...]] = ()) -> None:
    ziel = store_path()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    write_korrekturen(ziel, eintraege, roh)


def _aendern_mit(version: str, wer: str, vorgang: str, fn) -> dict:
    wer = _wer(wer)
    with _LOCK:
        if version != _version(_quelle()):
            raise VersionKonflikt("Die Korrekturen wurden inzwischen geändert.")
        eintraege, roh = bestand(), _roh_ungueltig()
        alt, neu = fn(eintraege, wer)
        _schreiben(eintraege, roh)          # invalid rows stay as they were (listed, never dropped)
        verlauf_schreiben(wer, vorgang, _zeile(alt), _zeile(neu))
        return lesen()


def _index(eintraege: list, id_: int) -> int:
    if not isinstance(id_, int) or not 0 <= id_ < len(eintraege):
        raise UngueltigeKorrektur(f"Keine Korrektur mit der Nummer {id_}.")
    return id_


def anlegen(k: dict, wer: str, version: str) -> dict:
    def fn(eintraege, wer):
        neu = _korrektur(k, wer)
        eintraege.append(neu)
        return None, neu
    return _aendern_mit(version, wer, "anlegen", fn)


def aendern(id_: int, k: dict, wer: str, version: str) -> dict:
    def fn(eintraege, wer):
        i = _index(eintraege, id_)
        alt, neu = eintraege[i], _korrektur(k, wer)
        eintraege[i] = neu
        return alt, neu
    return _aendern_mit(version, wer, "aendern", fn)


def loeschen(id_: int, wer: str, version: str) -> dict:
    def fn(eintraege, wer):
        i = _index(eintraege, id_)
        return eintraege.pop(i), None
    return _aendern_mit(version, wer, "loeschen", fn)


def ersetzen_alle(eintraege: list[Korrektur], wer: str, version: str, vorgang: str,
                  sicherung: bool, roh_behalten: bool = False) -> dict:
    """Write the whole list (import). Logs counts, not rows, to the history. `roh_behalten`
    keeps the invalid rows of the current file (import mode "ergaenzen")."""
    wer = _wer(wer)
    with _LOCK:
        if version != _version(_quelle()):
            raise VersionKonflikt("Die Korrekturen wurden inzwischen geändert.")
        vorher = len(bestand())
        if sicherung:
            sichern(_quelle(), "korrekturen")
        _schreiben(list(eintraege), _roh_ungueltig() if roh_behalten else [])
        verlauf_schreiben(wer, vorgang, f"{vorher} Zeilen", f"{len(eintraege)} Zeilen")
        return lesen()


def verlauf(limit: int = 200) -> list[dict]:
    path = verlauf_path()
    if not path.is_file():
        return []
    text = path.read_bytes().decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text, newline=""), delimiter=";"))
    out = [{"zeitpunkt": r.get("Zeitpunkt", ""), "wer": r.get("Wer", ""),
            "vorgang": r.get("Vorgang", ""), "alt": r.get("Alt", ""), "neu": r.get("Neu", "")}
           for r in rows]
    return out[::-1][:max(0, limit)]

