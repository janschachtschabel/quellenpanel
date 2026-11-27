"""Golden-Test: Die Datenwahrheit bleibt beim Profil-Umbau byte-gleich.

Die Referenz (expected_*.json) wurde einmal mit dem Code-Stand VOR Etappe 1 erzeugt
(tests/fixtures/golden/regenerate.py). Bei einem Umbau wird nur build_golden() angepasst,
nie die erwarteten Dateien.
"""
import json
import shutil
from pathlib import Path

import pytest

import enduser
import repo_profile
import truth

FIX = Path(__file__).parent / "fixtures" / "golden"


def _canon(x) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def use_data_dir(monkeypatch, data_dir: Path, profile: str = "wlo") -> None:
    """Point the app at a data directory (raw/ + crawler.csv + korrekturen.csv) and a profile."""
    monkeypatch.setenv("QE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("QE_PROFILE", profile)
    repo_profile.reset()
    monkeypatch.setattr(enduser, "_SUPPLEMENTS", None)   # re-read lazily from the new data dir
    enduser.reload_supplements()


@pytest.fixture(autouse=True)
def _reset_profile():
    yield
    repo_profile.reset()
    enduser.reload_supplements()


def build_golden(monkeypatch, tmp_path) -> list[dict]:
    shutil.copytree(FIX / "raw", tmp_path / "raw")
    shutil.copy(FIX / "neu" / "crawler.csv", tmp_path / "crawler.csv")
    shutil.copy(FIX / "neu" / "korrekturen.csv", tmp_path / "korrekturen.csv")
    use_data_dir(monkeypatch, tmp_path)
    return truth.build()


def test_truth_build_matches_golden(monkeypatch, tmp_path):
    records = build_golden(monkeypatch, tmp_path)
    expected = json.loads((FIX / "expected_records.json").read_text(encoding="utf-8"))
    assert _canon(records) == _canon(expected)


def test_cards_match_golden(monkeypatch, tmp_path):
    records = build_golden(monkeypatch, tmp_path)
    expected = json.loads((FIX / "expected_cards.json").read_text(encoding="utf-8"))
    assert _canon([enduser.card(r) for r in records]) == _canon(expected)
