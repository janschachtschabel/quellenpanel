"""Golden-Test: Die Datenwahrheit bleibt beim Profil-Umbau byte-gleich.

Die Referenz (expected_*.json) wurde einmal mit dem Code-Stand VOR Etappe 1 erzeugt
(tests/fixtures/golden/regenerate.py). Bei einem Umbau wird nur build_golden() angepasst,
nie die erwarteten Dateien.
"""
import json
import shutil
from pathlib import Path

import enduser
import truth
import truth_loaders

FIX = Path(__file__).parent / "fixtures" / "golden"


def _canon(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def build_golden(monkeypatch, tmp_path) -> list[dict]:
    gap = tmp_path / "quellen-analyse" / "data"
    gap.mkdir(parents=True)
    shutil.copy(FIX / "raw" / "replication_publisher_gap.csv", gap / "replication_publisher_gap.csv")
    monkeypatch.setattr(truth_loaders, "RAW", FIX / "raw")
    monkeypatch.setattr(truth_loaders, "DATENCRAWLER", FIX / "alt" / "datencrawler.csv")
    monkeypatch.setattr(truth_loaders, "KORREKTUR", FIX / "alt" / "quellen_korrektur.csv")
    monkeypatch.setattr(truth_loaders, "ROOT", tmp_path)
    sup = json.loads((FIX / "alt" / "source_supplements.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(enduser, "_SUPPLEMENTS", {k: v for k, v in sup.items() if not k.startswith("_")})
    return truth.build()


def test_truth_build_matches_golden(monkeypatch, tmp_path):
    records = build_golden(monkeypatch, tmp_path)
    expected = json.loads((FIX / "expected_records.json").read_text(encoding="utf-8"))
    assert _canon(records) == _canon(expected)


def test_cards_match_golden(monkeypatch, tmp_path):
    records = build_golden(monkeypatch, tmp_path)
    expected = json.loads((FIX / "expected_cards.json").read_text(encoding="utf-8"))
    assert _canon([enduser.card(r) for r in records]) == _canon(expected)
