"""Review-Befund: Neu laden/Aktualisieren muss auch die Bezugsquellen-Ergänzungen aus
korrekturen.csv neu lesen, nicht nur die Node-Korrekturen."""
import shutil

import config
import enduser
import refresh
from korrekturen import Korrektur, write_korrekturen


def _data_dir_with_supplement(tmp_path, monkeypatch, text):
    shutil.copy(config.truth_path(), tmp_path / "truth.json")
    write_korrekturen(tmp_path / "korrekturen.csv",
                      [Korrektur("bezugsquelle", "Testquelle", "beschreibung", text)])
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))


def test_admin_reload_rereads_supplements(client, team_pw, tmp_path, monkeypatch):
    enduser._supplements()                                   # cache filled from the old file
    _data_dir_with_supplement(tmp_path, monkeypatch, "neu")
    r = client.post("/api/admin/reload", headers={"X-Team-Password": team_pw})
    assert r.status_code == 200
    assert enduser._supplements()["testquelle"]["description"] == "neu"
    monkeypatch.undo()
    enduser.reload_supplements()


def test_refresh_rereads_supplements(tmp_path, monkeypatch):
    enduser._supplements()
    _data_dir_with_supplement(tmp_path, monkeypatch, "frisch")
    monkeypatch.setattr(refresh.fetcher, "refresh_all", lambda cb: None)
    monkeypatch.setattr(refresh.truth, "main", lambda: {})
    refresh._run_refresh()
    assert refresh.status()["status"] == "done"
    assert enduser._supplements()["testquelle"]["description"] == "frisch"
    monkeypatch.undo()
    enduser.reload_supplements()
