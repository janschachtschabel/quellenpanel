"""korrekturen.py — curated corrections in ONE long-format, semicolon-separated CSV.

One row per correction:  Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am

  Typ     node | spider | bezugsquelle
  Aktion  blacklist | whitelist | vermerk          (node: correction-list membership)
          bezugsquelle_setzen | spider_setzen      (node: override, carried as data)
          beschreibung | vorschaubild              (bezugsquelle: serve-time supplement)

Excel-friendly: written as UTF-8 with BOM, ';' and CRLF; read tolerantly (BOM optional,
',' detected, trailing empty columns ignored). Invalid rows are skipped and reported with
their 1-based line number (header = line 1), so a bad edit never breaks serving.
"""
from __future__ import annotations

import csv
import io
import os
from collections.abc import Iterable
from dataclasses import astuple, dataclass, field
from pathlib import Path

from truth_text import _UUID_RE, _norm

HEADER = ("Typ", "Schlüssel", "Aktion", "Wert", "Kommentar", "Geändert von", "Geändert am")
TYPEN = ("node", "spider", "bezugsquelle")
AKTIONEN = ("blacklist", "whitelist", "vermerk", "bezugsquelle_setzen", "spider_setzen",
            "beschreibung", "vorschaubild")
_LISTEN = ("blacklist", "whitelist", "vermerk")
_SUPPLEMENT_KEYS = {"beschreibung": "description", "vorschaubild": "previewUrl"}


@dataclass(frozen=True)
class Korrektur:
    typ: str
    schluessel: str
    aktion: str
    wert: str = ""
    kommentar: str = ""
    geaendert_von: str = ""
    geaendert_am: str = ""


@dataclass(frozen=True)
class Meldung:
    zeile: int
    text: str


@dataclass
class KorrekturSet:
    eintraege: list[Korrektur] = field(default_factory=list)
    fehler: list[Meldung] = field(default_factory=list)
    warnungen: list[Meldung] = field(default_factory=list)

    def als_node_dict(self) -> dict[str, dict[str, str]]:
        """Shape of the former correction-list loader: {nodeId: {liste, bezugsquelle, spider}}."""
        out: dict[str, dict[str, str]] = {}
        for k in self.eintraege:
            if k.typ != "node":
                continue
            entry = out.setdefault(k.schluessel, {"liste": "", "bezugsquelle": "", "spider": ""})
            if k.aktion in ("blacklist", "whitelist"):
                entry["liste"] = k.aktion
            elif k.aktion == "bezugsquelle_setzen":
                entry["bezugsquelle"] = k.wert
            elif k.aktion == "spider_setzen":
                entry["spider"] = k.wert
        return out

    def melden(self, log, max_n: int = 10) -> None:
        """Log row errors and warnings (count + the first few), so bad edits are visible."""
        for art, items, level in (("Fehler", self.fehler, log.warning),
                                  ("Warnungen", self.warnungen, log.info)):
            if items:
                level("korrekturen.csv: %d %s", len(items), art)
                for m in items[:max_n]:
                    level("  Zeile %d: %s", m.zeile, m.text)

    def supplements(self) -> dict[str, dict[str, str]]:
        """{lowercased source name: {description, previewUrl}} — only fields that are set."""
        out: dict[str, dict[str, str]] = {}
        for k in self.eintraege:
            if k.typ == "bezugsquelle" and k.aktion in _SUPPLEMENT_KEYS and k.wert:
                out.setdefault(k.schluessel.lower(), {})[_SUPPLEMENT_KEYS[k.aktion]] = k.wert
        return out


def _check(k: Korrektur) -> str:
    """Empty string if the row is valid, else the reason."""
    if k.typ not in TYPEN:
        return f"unbekannter Typ '{k.typ}'"
    if k.aktion not in AKTIONEN:
        return f"unbekannte Aktion '{k.aktion}'"
    if not k.schluessel:
        return "Schlüssel fehlt"
    if k.typ == "node" and not _UUID_RE.fullmatch(k.schluessel):
        return f"keine gültige Node-ID: '{k.schluessel}'"
    if k.aktion in _SUPPLEMENT_KEYS and k.typ != "bezugsquelle":
        return f"Aktion '{k.aktion}' nur für Typ bezugsquelle"
    if k.aktion in _LISTEN + ("bezugsquelle_setzen", "spider_setzen") and k.typ != "node":
        return f"Aktion '{k.aktion}' nur für Typ node"
    return ""


_PFLICHT = ("Typ", "Schlüssel", "Aktion")


def _read_text(path: Path) -> str:
    """UTF-8 (BOM optional); falls back to cp1252 for Excel's plain 'CSV (Trennzeichen-getrennt)'."""
    raw = Path(path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def load_korrekturen(path: Path | None) -> KorrekturSet:
    result = KorrekturSet()
    if path is None or not Path(path).is_file():
        return result
    text = _read_text(path)
    first = text.split("\n", 1)[0]
    if not first.strip():
        return result
    sep = ";" if first.count(";") >= first.count(",") else ","
    # Parse the whole text (not splitlines()), so quoted values may span lines (descriptions
    # with paragraphs); reader.line_num gives the physical line for messages.
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=sep)
    head = [_norm(c) for c in next(reader)]
    pos = {name: head.index(_norm(name)) if _norm(name) in head else None for name in HEADER}
    missing = [name for name in _PFLICHT if pos[name] is None]
    if missing:
        result.fehler.append(Meldung(1, f"Kopfzeile unvollständig: {', '.join(missing)} fehlt"))
        return result
    last_list: dict[str, tuple[str, int]] = {}
    start = reader.line_num
    for cells in reader:
        zeile, start = start + 1, reader.line_num
        if not any(c.strip() for c in cells):
            continue

        def cell(name: str, cells=cells) -> str:
            i = pos[name]
            return cells[i].strip() if i is not None and i < len(cells) else ""

        k = Korrektur(cell("Typ").lower(), cell("Schlüssel"), cell("Aktion").lower(), cell("Wert"),
                      cell("Kommentar"), cell("Geändert von"), cell("Geändert am"))
        reason = _check(k)
        if reason:
            result.fehler.append(Meldung(zeile, reason))
            continue
        if k.typ == "node" and k.aktion in ("blacklist", "whitelist"):
            prev = last_list.get(k.schluessel)
            if prev and prev[0] != k.aktion:
                result.warnungen.append(Meldung(
                    zeile, f"{k.schluessel}: '{k.aktion}' überschreibt '{prev[0]}' aus Zeile {prev[1]}"))
            last_list[k.schluessel] = (k.aktion, zeile)
        result.eintraege.append(k)
    return result


def write_korrekturen(path: Path, eintraege: Iterable[Korrektur]) -> None:
    """Atomic write (temp file + os.replace): UTF-8 with BOM, ';', CRLF."""
    path = Path(path)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(HEADER)
    for k in eintraege:
        w.writerow(astuple(k))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))
    os.replace(tmp, path)
