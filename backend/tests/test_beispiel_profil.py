"""Ein fremdes Profil (ohne WLO-Felder, ohne Sonderfall-Spider) läuft durch den ganzen Merge."""
import json
from pathlib import Path

import pytest

import repo_profile
import truth

PROFILES = Path(__file__).resolve().parents[2] / "profiles"


def _node(nid, title, pub, lrt="Quelle"):
    return {"ref": {"id": nid}, "title": title, "properties": {
        "cclom:title": [title], "ccm:publisher": [pub],
        "ccm:educationallearningresourcetype_DISPLAYNAME": [lrt],
        "cclom:general_description": ["Text"], "ccm:wf_status": ["published"]}}


@pytest.fixture
def beispiel(monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    nodes = [_node("aaaaaaaa-0000-0000-0000-000000000001", "Museum Digital", "Museum"),
             _node("aaaaaaaa-0000-0000-0000-000000000002", "Archiv Online", "Archiv")]
    (raw / "quellen_nodes.json").write_text(json.dumps(nodes), encoding="utf-8")
    (raw / "cache_facet_bezugsquellen.json").write_text(
        json.dumps({"Museum": 12, "Archiv": 4, "Bibliothek": 30}), encoding="utf-8")
    (raw / "cache_facet_spider.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("QE_PROFILES_DIR", str(PROFILES))
    monkeypatch.setenv("QE_PROFILE", "beispiel")
    repo_profile.reset()
    yield
    repo_profile.reset()


def test_build_with_foreign_profile(beispiel):
    records = truth.build()
    assert {r["kind"] for r in records} == {"manuell", "bezugsquelle"}
    assert all("WLO_MIGRATION" not in r["flags"] for r in records)
    museum = next(r for r in records if r["name"] == "Museum Digital")
    assert museum["public"]["Bezugsquelle"] == "Museum"
    assert museum["contentCount"] == 12
    assert "NICHT_PUBLIZIERT" not in museum["flags"]
    assert any(r["id"] == "bq:bibliothek" for r in records)
