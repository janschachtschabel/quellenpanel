"""Datenwahrheit bei fehlenden kuratierten Dateien (Crawler-Tabelle, Korrekturen)."""
import shutil
from pathlib import Path

import repo_profile
import truth

FIX = Path(__file__).parent / "fixtures" / "golden"
PROFILES = Path(__file__).resolve().parents[2] / "profiles"


def test_build_without_crawler_and_korrekturen(monkeypatch, tmp_path):
    shutil.copytree(FIX / "raw", tmp_path / "data" / "raw")
    (tmp_path / "profiles" / "wlo").mkdir(parents=True)          # profile WITHOUT daten/
    shutil.copy(PROFILES / "wlo" / "profil.toml", tmp_path / "profiles" / "wlo" / "profil.toml")
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("QE_PROFILES_DIR", str(tmp_path / "profiles"))
    repo_profile.reset()
    try:
        records = truth.build()
    finally:
        repo_profile.reset()
    assert records
    assert not any(r["kind"] == "crawler" and r["fieldGeneration"] for r in records)
    assert not any({"BLACKLIST", "WHITELIST"} & set(r["flags"]) for r in records)
