"""Stufe 0/1 kommen aus dem Export; das Team veröffentlicht Exporte mit ETag (Etappe 2, Task 4)."""
import shutil

import pytest

import config
import export_query
import export_store
import refresh

TEAM_ROUTES = [("get", "/api/stats/team"), ("get", "/api/protokoll.md"), ("get", "/api/protokoll.json"),
               ("get", "/api/protokoll.csv"), ("post", "/jobs/refresh"), ("post", "/api/admin/reload"),
               ("get", "/internal/exports/stufe0.json")]

BASE = {"q": "", "subject": "", "level": "", "erschliessung": "", "oer": None, "crawler": None,
        "min_count": 1, "flag": None, "show_blacklist": False, "sort": "contentCount", "order": "desc",
        "only_field_profile": False, "has_node": None, "has_bezugsquelle": None, "has_spider": None,
        "lrt": ""}


def test_tier0_list_comes_from_export(client):
    got = client.get("/api/sources?page_size=10").json()
    assert got == export_query.page(export_store.current(0), BASE, 1, 10)
    assert got["items"] and not any("flags" in it or "bind" in it for it in got["items"])


def test_tier1_detail_and_stats_from_export(client):
    doc = export_store.current(1)
    sid = doc["items"][0]["id"]
    assert client.get(f"/api/sources/{sid}?tier=1").json() == doc["items"][0]["detail"]
    assert client.get("/api/stats?tier=1").json() == doc["stats"]
    assert client.get("/api/meta/filters").json() == export_store.current(0)["filters"]


def test_blacklisted_detail_404_below_team(client, team_pw):
    from store import _DATA
    black = next(r["id"] for r in _DATA["records"] if "BLACKLIST" in r["flags"])
    assert client.get(f"/api/sources/{black}").status_code == 404
    assert client.get(f"/api/sources/{black}?tier=2", headers={"X-Team-Password": team_pw}).status_code == 200


def test_team_filters_have_erschliessung(client, team_pw):
    full = client.get("/api/meta/filters?tier=2", headers={"X-Team-Password": team_pw}).json()
    assert full["erschliessung"], "Team behält den Statusfilter"
    assert client.get("/api/meta/filters?tier=2").json()["erschliessung"] == []


def test_internal_export_etag_304(client):
    r = client.get("/internal/exports/stufe0.json")
    assert r.status_code == 200 and r.headers["etag"] == export_store.etag(0)
    assert client.get("/internal/exports/stufe0.json",
                      headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    assert client.get("/internal/exports/stufe2.json").status_code == 404


@pytest.mark.parametrize("role", ["partner", "public"])
def test_team_routes_404_outside_team(client, team_pw, monkeypatch, role):
    monkeypatch.setenv("QE_ROLE", role)
    for method, path in TEAM_ROUTES:
        r = getattr(client, method)(path, headers={"X-Team-Password": team_pw})
        assert r.status_code == 404, (role, path, r.status_code)


def test_tier2_list_unchanged(client, team_pw):
    d = client.get("/api/sources?tier=2&page_size=5", headers={"X-Team-Password": team_pw}).json()
    assert d["tier"] == 2 and "hidden" in d and all("flags" in it for it in d["items"])


def test_refresh_rebuilds_exports(client, tmp_path, monkeypatch):
    shutil.copy(config.truth_path(), tmp_path / "truth.json")
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(refresh.fetcher, "refresh_all", lambda cb: None)
    monkeypatch.setattr(refresh.truth, "main", lambda: {})
    refresh._run_refresh()
    assert refresh.status()["status"] == "done"
    assert (tmp_path / "exports" / "stufe0.json").is_file()
    assert (tmp_path / "exports" / "stufe1.json").is_file()


def test_unwritable_export_dir_keeps_memory_export(monkeypatch, tmp_path, caplog):
    from store import _DATA
    blocker = tmp_path / "exports"
    blocker.write_text("keine Verzeichnis")         # mkdir will fail
    with caplog.at_level("WARNING"):
        export_store.rebuild_from_records(_DATA["records"], _DATA["meta"], blocker)
    assert export_store.current(0) is not None and "Export" in caplog.text
