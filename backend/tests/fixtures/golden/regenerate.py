"""Erzeugt die Golden-Referenz der Datenwahrheit.

Nur EINMAL vor Etappe 1 ausführen (alter Code-Stand); danach ist die Ausgabe die Referenz,
gegen die tests/test_golden.py jeden Umbau prüft. Aufruf (aus backend/):

    python tests/fixtures/golden/regenerate.py tests/fixtures/golden
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # backend/

import enduser
import truth
import truth_loaders


def build(fix: Path) -> list[dict]:
    root = Path(tempfile.mkdtemp())
    gap = root / "quellen-analyse" / "data"
    gap.mkdir(parents=True)
    shutil.copy(fix / "raw" / "replication_publisher_gap.csv", gap / "replication_publisher_gap.csv")
    truth_loaders.RAW = fix / "raw"
    truth_loaders.DATENCRAWLER = fix / "alt" / "datencrawler.csv"
    truth_loaders.KORREKTUR = fix / "alt" / "quellen_korrektur.csv"
    truth_loaders.ROOT = root
    sup = json.loads((fix / "alt" / "source_supplements.json").read_text(encoding="utf-8"))
    enduser._SUPPLEMENTS = {k: v for k, v in sup.items() if not k.startswith("_")}
    return truth.build()


def dump(o) -> str:
    return json.dumps(o, sort_keys=True, indent=1, ensure_ascii=False)


def main(fix: Path) -> None:
    records = build(fix)
    (fix / "expected_records.json").write_text(dump(records), encoding="utf-8")
    (fix / "expected_cards.json").write_text(dump([enduser.card(r) for r in records]), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())
