"""Nach einer Änderung: Merge neu rechnen (mit Roh-Caches) oder nur Supplements/Exporte."""
import shutil
from pathlib import Path

import pytest

import anwenden
import enduser
import export_store
import korrektur_store as ks
import repo_profile
import store
from korrekturen import Korrektur, write_korrekturen

FIX = Path(__file__).parent / "fixtures" / "golden"


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    repo_profile.reset()
    saved = dict(store._DATA)
    yield tmp_path
    store._DATA.update(saved)
    repo_profile.reset()
    monkeypatch.undo()
    enduser.reload_supplements()
    if store._DATA.get("records"):
        export_store.rebuild_from_records(store._DATA["records"], store._DATA["meta"], None)


def test_without_raw_caches_only_supplements_and_exports(daten):
    shutil.copy(Path(__file__).resolve().parents[1] / "data" / "truth.json", daten / "truth.json")
    store.load()
    write_korrekturen(daten / "korrekturen.csv",
                      [Korrektur("bezugsquelle", "Testquelle", "beschreibung", "frisch")])
    res = anwenden.nach_aenderung()
    assert res == {"neuBerechnet": False, "wirktBeimNaechstenAufbau": True}
    assert enduser._supplements()["testquelle"]["description"] == "frisch"
    assert not (daten / "truth.json.tmp").exists()


def test_with_raw_caches_rebuilds_truth_and_memory(daten):
    shutil.copytree(FIX / "raw", daten / "raw")
    shutil.copy(FIX / "neu" / "crawler.csv", daten / "crawler.csv")
    shutil.copy(FIX / "neu" / "korrekturen.csv", daten / "korrekturen.csv")
    anwenden.nach_aenderung()
    rec = next(r for r in store._DATA["records"] if r["identity"].get("nodeId")
               and "BLACKLIST" not in r["flags"] and "WHITELIST" not in r["flags"])
    nid = rec["identity"]["nodeId"]
    ks.anlegen({"typ": "node", "schluessel": nid, "aktion": "blacklist"}, "JS", ks.lesen()["version"])
    res = anwenden.nach_aenderung()
    assert res == {"neuBerechnet": True, "wirktBeimNaechstenAufbau": False}
    neu = next(r for r in store._DATA["records"] if r["identity"].get("nodeId") == nid)
    assert "BLACKLIST" in neu["flags"]
    assert (daten / "exports" / "stufe0.json").is_file()
    assert all(r["id"] != rec["id"] for r in export_store.current(0)["items"])


def test_refresh_rebuild_holds_the_correction_lock(monkeypatch):
    """Review-Befund: Rebuild und Anwenden laufen nie gleichzeitig (gemeinsame Sperre)."""
    import refresh
    import fetcher
    import truth
    held = []
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: None)

    def fake_main():
        held.append(ks.lock()._is_owned())
        raise RuntimeError("stop")
    monkeypatch.setattr(truth, "main", fake_main)
    monkeypatch.setattr(refresh.bootstrap, "write_status", lambda job: None)
    refresh._run_refresh()
    refresh._JOB.update(status="idle")
    assert held == [True]
