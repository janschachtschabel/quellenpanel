"""korrektur_import.py — import corrections from CSV, JSON or XLSX (pure functions).

  lesen_datei(bytes, format)  → (columns, rows as {column: text})
  auto_zuordnung(columns)     → {target field: source column | None}
  vorschau(rows, mapping, bestand, modus, wer) → new / changed / unchanged / faulty / dropped + result

Matching key of a correction: (typ, schluessel, aktion); the list actions blacklist / whitelist /
vermerk share the key (typ, schluessel, "liste"), so switching lists shows as a change.
Mode "ergaenzen" keeps existing rows and applies new/changed ones; "ersetzen" makes the import the
whole file (existing rows not in the import are reported as dropped).
"""
from __future__ import annotations

import csv
import io
import json
import zipfile

from korrekturen import Korrektur, _check
from truth_text import _norm

MAX_ZEILEN = 20_000
FORMATE = ("csv", "json", "xlsx")
MODI = ("ergaenzen", "ersetzen")
ZIELFELDER = ("typ", "schluessel", "aktion", "wert", "kommentar")
PFLICHT = ("schluessel", "aktion")
_ALIASSE = {
    "typ": ("typ", "type", "art"),
    "schluessel": ("schlussel", "schluessel", "key", "node-id", "nodeid", "node id", "id", "name"),
    "aktion": ("aktion", "action", "liste", "list"),
    "wert": ("wert", "value"),
    "kommentar": ("kommentar", "comment", "bemerkung", "titel", "title"),
}


class ImportFehler(ValueError):
    """The upload cannot be read or mapped."""


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _check_anzahl(n: int) -> None:
    if n > MAX_ZEILEN:
        raise ImportFehler(f"Zu viele Zeilen ({n}); höchstens {MAX_ZEILEN}.")


def _csv(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252", errors="replace")
    first = text.split("\n", 1)[0]
    if not first.strip():
        raise ImportFehler("Die Datei ist leer.")
    sep = ";" if first.count(";") >= first.count(",") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=sep)
    spalten = [c.strip() for c in next(reader)]
    zeilen = []
    for cells in reader:
        if not any(c.strip() for c in cells):
            continue
        zeilen.append({s: (cells[i].strip() if i < len(cells) else "") for i, s in enumerate(spalten) if s})
        _check_anzahl(len(zeilen))
    return [s for s in spalten if s], zeilen


def _json(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ImportFehler("Kein gültiges JSON.") from e
    if not isinstance(doc, list) or not all(isinstance(o, dict) for o in doc):
        raise ImportFehler("JSON muss eine Liste von Objekten sein.")
    _check_anzahl(len(doc))
    spalten: list[str] = []
    for o in doc:
        for k in o:
            if str(k) not in spalten:
                spalten.append(str(k))
    return spalten, [{str(k): _text(v) for k, v in o.items()} for o in doc]


def _xlsx(data: bytes) -> tuple[list[str], list[dict[str, str]]]:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, OSError, ValueError) as e:
        raise ImportFehler("Keine lesbare XLSX-Datei.") from e
    try:
        ws = wb.worksheets[0]
        rows = ws.iter_rows(values_only=True)
        head = next(rows, None)
        if not head:
            raise ImportFehler("Die Tabelle ist leer.")
        spalten = [_text(c) for c in head]
        zeilen = []
        for r in rows:
            if not any(_text(c) for c in r):
                continue
            zeilen.append({s: _text(r[i]) if i < len(r) else "" for i, s in enumerate(spalten) if s})
            _check_anzahl(len(zeilen))
        return [s for s in spalten if s], zeilen
    finally:
        wb.close()


def lesen_datei(data: bytes, format: str) -> tuple[list[str], list[dict[str, str]]]:
    if format not in FORMATE:
        raise ImportFehler(f"Unbekanntes Format '{format}'; erlaubt: {', '.join(FORMATE)}.")
    if not data:
        raise ImportFehler("Die Datei ist leer.")
    return {"csv": _csv, "json": _json, "xlsx": _xlsx}[format](data)


def auto_zuordnung(spalten: list[str]) -> dict[str, str | None]:
    norm = {_norm(s).replace("ü", "u"): s for s in spalten}
    out: dict[str, str | None] = {}
    for feld in ZIELFELDER:
        out[feld] = next((norm[a] for a in _ALIASSE[feld] if a in norm), None)
    return out


def _schluessel(k: Korrektur) -> tuple[str, str, str]:
    # blacklist and whitelist exclude each other (one list per node); a vermerk stands beside them.
    return (k.typ, k.schluessel, "liste" if k.aktion in ("blacklist", "whitelist") else k.aktion)


def vorschau(zeilen: list[dict[str, str]], zuordnung: dict[str, str | None], bestand: list[Korrektur],
             modus: str, wer: str) -> dict:
    if modus not in MODI:
        raise ImportFehler(f"Unbekannter Modus '{modus}'; erlaubt: {', '.join(MODI)}.")
    fehlend = [f for f in PFLICHT if not zuordnung.get(f)]
    if fehlend:
        raise ImportFehler(f"Spalte nicht zugeordnet: {', '.join(fehlend)}.")
    from datetime import date
    heute = date.today().isoformat()

    def zelle(r, feld):
        spalte = zuordnung.get(feld)
        return (r.get(spalte) or "").strip() if spalte else ""

    vorhanden = {_schluessel(k): k for k in bestand}
    importiert: dict[tuple, Korrektur] = {}
    neu, geaendert, fehlerhaft, unveraendert = [], [], [], 0
    for nr, r in enumerate(zeilen, start=2):
        k = Korrektur((zelle(r, "typ") or "node").lower(), zelle(r, "schluessel"),
                      zelle(r, "aktion").lower(), zelle(r, "wert"), zelle(r, "kommentar"), wer, heute)
        grund = _check(k)
        if grund:
            fehlerhaft.append({"zeile": nr, "text": grund})
            continue
        key = _schluessel(k)
        alt = vorhanden.get(key)
        if alt is not None and (alt.aktion, alt.wert, alt.kommentar) == (k.aktion, k.wert, k.kommentar):
            importiert[key] = alt
            unveraendert += 1
            continue
        if key in importiert:                       # later row in the same file wins
            neu = [x for x in neu if _schluessel(x) != key]
            geaendert = [x for x in geaendert if _schluessel(x["neu"]) != key]
        importiert[key] = k
        if alt is None:
            neu.append(k)
        else:
            geaendert.append({"alt": alt, "neu": k})
    if modus == "ersetzen":
        entfallen = [k for key, k in vorhanden.items() if key not in importiert]
        ergebnis = list(importiert.values())
    else:
        entfallen = []
        ergebnis = [importiert.get(_schluessel(k), k) for k in bestand]
        ergebnis += [k for key, k in importiert.items() if key not in vorhanden]
    return {"neu": neu, "geaendert": geaendert, "unveraendert": unveraendert,
            "fehlerhaft": fehlerhaft, "entfallen": entfallen, "ergebnis": ergebnis}
