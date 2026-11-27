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


def test_empty_migration_quelle_matches_nothing(beispiel):
    # Review-Befund: migration_quelle = "" galt für jeden Datensatz ohne replicationsource.
    import filtering
    import stats_team
    records = truth.build()
    hits = filtering.filter_records(records, None, None, None, None, None, 0, None, False,
                                    wlo_migration=True)
    assert hits == []
    stats = stats_team.compute_stats_team(records, {"withNode": 2})
    assert stats["spider"]["ausWloAltmigration_replicationsource"] == 0


def test_neues_repository_startet_mit_leeren_startdaten(beispiel, tmp_path):
    """Anleitung „Anderes Repository anbinden“: Kopfzeilen genügen als Startdaten für den Server."""
    import refresh
    (tmp_path / "crawler.csv").write_text("Titel;Url;Crawler (Spider);Quelldatensatz (Prod)\n", encoding="utf-8-sig")
    (tmp_path / "korrekturen.csv").write_text(
        "Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am\n", encoding="utf-8-sig")
    assert refresh.fehlende_startdaten() == []
    records = truth.build()
    assert any(r["name"] == "Museum Digital" for r in records)
