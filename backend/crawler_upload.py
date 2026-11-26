"""crawler_upload.py — the data team replaces the crawler table ($QE_DATA_DIR/crawler.csv).

pruefen(bytes)       required columns (from the profile) + effect against the current table:
                     spiders new / dropped / changed / unchanged
ersetzen(bytes, wer) re-checks, backs up the old table (crawler-<ts>.csv), writes atomically,
                     logs to the corrections history and makes it effective (anwenden).
"""
from __future__ import annotations

import csv
import io
import os

import anwenden
import config
import korrektur_store
import repo_profile
from truth_text import _norm


class UploadFehler(ValueError):
    """The uploaded crawler table cannot be used."""


def _text(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _lesen(text: str) -> tuple[list[str], list[list[str]]]:
    first = text.split("\n", 1)[0]
    if not first.strip():
        raise UploadFehler("Die Datei ist leer.")
    sep = ";" if first.count(";") >= first.count(",") else ","
    rows = [r for r in csv.reader(io.StringIO(text, newline=""), delimiter=sep)]
    return [c.strip() for c in rows[0]], [r for r in rows[1:] if any(c.strip() for c in r)]


def _nach_spider(spalten: list[str], rows: list[list[str]]) -> dict[str, tuple]:
    prof = repo_profile.get()
    norm = [_norm(c) for c in spalten]
    i = norm.index(_norm(prof.crawler_spider_spalte))
    out: dict[str, tuple] = {}
    for r in rows:
        sp = r[i].strip() if i < len(r) else ""
        if sp and sp.lower() not in ("nein", "-", "none"):
            out[sp] = tuple(c.strip() for c in r)
    return out


def _aktuell() -> dict[str, tuple]:
    path = config.crawler_csv_path()
    if not path:
        return {}
    try:
        spalten, rows = _lesen(_text(path.read_bytes()))
        return _nach_spider(spalten, rows)
    except (UploadFehler, ValueError):
        return {}


def pruefen(data: bytes) -> dict:
    if not data:
        raise UploadFehler("Die Datei ist leer.")
    spalten, rows = _lesen(_text(data))
    prof = repo_profile.get()
    norm = {_norm(c) for c in spalten}
    pflicht = (prof.crawler_spider_spalte, prof.crawler_quelldatensatz_spalte)
    fehlend = [p for p in pflicht if _norm(p) not in norm]
    res = {"ok": not fehlend, "zeilen": len(rows), "spalten": spalten, "fehlendePflicht": fehlend,
           "spider": {"neu": [], "entfallen": [], "geaendert": [], "gleich": 0}}
    if fehlend:
        return res
    neu, alt = _nach_spider(spalten, rows), _aktuell()
    res["spider"] = {"neu": sorted(set(neu) - set(alt)), "entfallen": sorted(set(alt) - set(neu)),
                     "geaendert": sorted(s for s in set(neu) & set(alt) if neu[s] != alt[s]),
                     "gleich": sum(1 for s in set(neu) & set(alt) if neu[s] == alt[s])}
    return res


def ersetzen(data: bytes, wer: str) -> dict:
    wer = korrektur_store._wer(wer)
    res = pruefen(data)
    if not res["ok"]:
        raise UploadFehler("Pflichtspalte fehlt: " + ", ".join(res["fehlendePflicht"]))
    with korrektur_store.lock():
        alt = config.crawler_csv_path()
        vorher = 0
        if alt:
            vorher = len(_lesen(_text(alt.read_bytes()))[1])
            korrektur_store.sichern(alt, "crawler")
        ziel = config.data_dir() / "crawler.csv"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tmp = ziel.with_suffix(".csv.tmp")
        # Always stored as UTF-8 with BOM: Excel's "CSV (Trennzeichen-getrennt)" is cp1252 and the
        # merge reads UTF-8, so umlaut columns (Häufigkeit …) would otherwise get lost.
        tmp.write_bytes(b"\xef\xbb\xbf" + _text(data).encode("utf-8"))
        os.replace(tmp, ziel)
        korrektur_store.verlauf_schreiben(wer, "crawler_ersetzen", f"{vorher} Zeilen",
                                          f"{res['zeilen']} Zeilen")
    res["anwenden"] = anwenden.sicher()
    return res
