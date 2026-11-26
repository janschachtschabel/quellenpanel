"""Einmalige Migration: alte Korrekturliste + Supplements → korrekturen.csv (Langformat).

    python -m tools.migrate_korrekturen <quellen_korrektur.csv> <source_supplements.json> <ziel.csv> [--bericht <md>]

Das heutige Verhalten bleibt erhalten:
  * Liste blacklist/whitelist → node;<id>;<liste>; leere Liste → node;<id>;vermerk
  * Bezugsquelle/Spider-Spalte → zusätzlich bezugsquelle_setzen / spider_setzen
  * doppelte Node-IDs: wie der alte Loader gilt nur die LETZTE Zeile; frühere stehen im Bericht
  * verrutschte Zeilen (Liste leer, 'blacklist'/'whitelist' in der Spider-Spalte) wirken heute
    nicht → nur 'vermerk' mit Hinweis im Kommentar und im Bericht (Entscheidung beim Team)
  * Supplements: bezugsquelle;<name>;beschreibung|vorschaubild;<wert>
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from korrekturen import Korrektur, write_korrekturen

_LISTEN = ("blacklist", "whitelist")


def _repair(text: str) -> str:
    """Undo double-encoded UTF-8 ('Ã¼' → 'ü') where that round-trips cleanly."""
    try:
        fixed = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return fixed


def migrate(korrektur_csv: Path, supplements_json: Path, heute: str) -> tuple[list[Korrektur], list[str]]:
    bericht: list[str] = []
    text = Path(korrektur_csv).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if text.count(";") > text.count(",") else ","
    last: dict[str, tuple[int, dict]] = {}
    order: list[str] = []
    for zeile, r in enumerate(csv.DictReader(text.splitlines(), delimiter=sep), start=2):
        nid = (r.get("Node-Id") or "").strip()
        if not nid:
            continue
        if nid in last:
            bericht.append(f"- Zeile {last[nid][0]}: Node {nid} doppelt, gilt Zeile {zeile} (wie bisher)")
        else:
            order.append(nid)
        last[nid] = (zeile, r)
    rows: list[Korrektur] = []
    for nid in order:
        zeile, r = last[nid]
        liste = (r.get("Liste") or "").strip().lower()
        bq = (r.get("Bezugsquelle") or "").strip()
        spider = (r.get("Spider") or "").strip()
        titel = _repair((r.get("Titel") or "").strip())
        url = (r.get("Url") or "").strip()
        kommentar = titel + (f" | {url}" if url else "")
        shifted = not liste and spider.lower() in _LISTEN
        if shifted:
            hinweis = f"Verdacht: Spalten verschoben, gemeint wohl {spider.lower()}"
            kommentar = f"{kommentar} – {hinweis}" if kommentar else hinweis
            bericht.append(f"- Zeile {zeile}: Node {nid} ({titel}): {hinweis}")
        meta = dict(kommentar=kommentar, geaendert_von="migration", geaendert_am=heute)
        rows.append(Korrektur("node", nid, liste if liste in _LISTEN else "vermerk", "", **meta))
        if bq:
            rows.append(Korrektur("node", nid, "bezugsquelle_setzen", bq, **meta))
        if spider and not shifted:
            rows.append(Korrektur("node", nid, "spider_setzen", spider, **meta))
    sup = json.loads(Path(supplements_json).read_text(encoding="utf-8"))
    for name, v in sup.items():
        if name.startswith("_"):
            continue
        for key, aktion in (("description", "beschreibung"), ("previewUrl", "vorschaubild")):
            if v.get(key):
                rows.append(Korrektur("bezugsquelle", name, aktion, v[key], "", "migration", heute))
    return rows, bericht


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("korrektur_csv", type=Path)
    ap.add_argument("supplements_json", type=Path)
    ap.add_argument("ziel", type=Path)
    ap.add_argument("--bericht", type=Path)
    a = ap.parse_args(argv)
    rows, bericht = migrate(a.korrektur_csv, a.supplements_json, time.strftime("%Y-%m-%d"))
    a.ziel.parent.mkdir(parents=True, exist_ok=True)
    write_korrekturen(a.ziel, rows)
    if a.bericht:
        a.bericht.write_text("# Migrationsbericht Korrekturen\n\n"
                             f"{len(rows)} Zeilen geschrieben nach `{a.ziel.name}`.\n\n"
                             + ("\n".join(bericht) or "Keine Auffälligkeiten.") + "\n", encoding="utf-8")
    print(f"{len(rows)} Zeilen, {len(bericht)} Hinweise", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
