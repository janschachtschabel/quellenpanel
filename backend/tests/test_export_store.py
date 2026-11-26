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


# --- Task 5: Partner/Öffentlich laden nur ihren Export -------------------------------------
import io  # noqa: E402
import json  # noqa: E402
import urllib.error  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402
import exports  # noqa: E402
import store  # noqa: E402


@pytest.fixture
def export_files(client, tmp_path, monkeypatch):
    """stufe0/1.json from the team instance, a private /tmp dir, and a clean store afterwards."""
    src = tmp_path / "src"
    for t in (0, 1):
        exports.write_doc(export_store.current(t), src / f"stufe{t}.json")
    monkeypatch.setattr(export_store, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setenv("QE_EXPORT_SOURCE", str(src / "stufe{tier}.json"))
    monkeypatch.setenv("QE_EXPORT_POLL_MINUTES", "0")
    yield src
    export_store.reset()


def test_load_from_file_source(export_files):
    export_store.reset()
    assert export_store.load_remote(0) is True
    assert export_store.current(0)["tier"] == 0


def test_broken_source_keeps_last_good(export_files, caplog):
    export_store.reset()
    assert export_store.load_remote(0)
    good = export_store.current(0)
    f = export_files / "stufe0.json"
    with caplog.at_level("WARNING"):
        f.write_text('{"schema": 1, "tier": 0, "items": [', encoding="utf-8")
        assert export_store.load_remote(0) is False
        f.write_bytes((export_files / "stufe1.json").read_bytes())     # tier 1 doc in stufe0.json
        assert export_store.load_remote(0) is False
    assert export_store.current(0) is good
    assert "Export" in caplog.text


def test_http_source_etag_304(export_files, monkeypatch):
    export_store.reset()
    assert export_store.load_remote(0)
    good, tag = export_store.current(0), export_store.etag(0)
    monkeypatch.setenv("QE_EXPORT_SOURCE", "http://team.intern/internal/exports/stufe{tier}.json")
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["url"], seen["inm"] = req.full_url, req.get_header("If-none-match")
        raise urllib.error.HTTPError(req.full_url, 304, "Not Modified", {}, io.BytesIO(b""))

    monkeypatch.setattr(export_store.urllib.request, "urlopen", fake_urlopen)
    assert export_store.load_remote(0) is True
    assert seen == {"url": "http://team.intern/internal/exports/stufe0.json", "inm": tag}
    assert export_store.current(0) is good


def test_http_source_200(export_files, monkeypatch):
    export_store.reset()
    body = (export_files / "stufe1.json").read_bytes()
    monkeypatch.setenv("QE_EXPORT_SOURCE", "https://team.intern/x/stufe{tier}.json")

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(export_store.urllib.request, "urlopen", lambda req, timeout=None: Resp(body))
    assert export_store.load_remote(1) is True
    assert export_store.current(1)["tier"] == 1


def test_tmp_copy_used_on_start(export_files):
    export_store.reset()
    assert export_store.load_remote(0)
    assert (export_store.TMP_DIR / "quellenpanel-stufe0.json").is_file()
    export_store.reset()
    assert export_store.load_tmp(0) is True and export_store.current(0)["tier"] == 0


def test_public_app_serves_only_export(export_files, monkeypatch, team_pw):
    monkeypatch.setenv("QE_ROLE", "public")
    with TestClient(app_module.app) as c:
        h = c.get("/api/health")
        assert h.status_code == 200 and h.json()["role"] == "public"
        assert c.get("/api/sources?tier=2", headers={"X-Team-Password": team_pw}).json()["tier"] == 0
        assert store._DATA["records"] == []
        assert export_store.current(1) is None          # public holds tier 0 only
        for method, path in TEAM_ROUTES:
            assert getattr(c, method)(path, headers={"X-Team-Password": team_pw}).status_code == 404


def test_partner_app_has_tier1_with_password(export_files, monkeypatch):
    monkeypatch.setenv("QE_ROLE", "partner")
    monkeypatch.setattr(config, "TIER1_PW", "p")
    with TestClient(app_module.app) as c:
        assert c.get("/api/sources?tier=1").json()["tier"] == 0
        assert c.get("/api/sources?tier=1", headers={"X-Tier1-Password": "p"}).json()["tier"] == 1
        sid = export_store.current(1)["items"][0]["id"]
        assert "ki" in c.get(f"/api/sources/{sid}?tier=1", headers={"X-Tier1-Password": "p"}).json()


def test_public_health_503_without_export(export_files, monkeypatch):
    monkeypatch.setenv("QE_ROLE", "public")
    monkeypatch.setenv("QE_EXPORT_SOURCE", str(export_files / "fehlt-stufe{tier}.json"))
    with TestClient(app_module.app) as c:
        r = c.get("/api/health")
        assert r.status_code == 503 and r.json()["status"] == "starting"
        assert c.get("/api/sources").status_code == 503


def test_partner_without_source_builds_from_truth(export_files, monkeypatch, caplog):
    monkeypatch.delenv("QE_EXPORT_SOURCE")
    monkeypatch.setenv("QE_ROLE", "partner")
    with caplog.at_level("WARNING"), TestClient(app_module.app) as c:
        assert c.get("/api/health").status_code == 200
        assert export_store.current(1) is not None
        assert store._DATA["records"] == []
    assert "QE_EXPORT_SOURCE" in caplog.text


def test_export_source_doc_is_valid_json(export_files):
    assert json.loads((export_files / "stufe0.json").read_text(encoding="utf-8"))["tier"] == 0
