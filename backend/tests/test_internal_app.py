"""Etappe 3 / Task 3: internal port 9090 — health, ready, metrics, internal exports."""
import pytest
from fastapi.testclient import TestClient

import app as app_module
import export_store
import exports
import internal_app
import obs
import refresh


@pytest.fixture
def internal():
    internal_app._SOURCE.update(ok=None, at=None, checkedAt=None)   # fresh source-check cache
    return TestClient(internal_app.app)


def test_health_ready_team(client, internal, monkeypatch):
    monkeypatch.setattr(internal_app, "_check_source", lambda: True)
    h = internal.get("/health")
    assert h.status_code == 200
    body = h.json()
    assert body["status"] == "ok" and body["role"] == "team" and body["version"]
    assert body["data"]["state"] == "ready"
    assert body["data"]["ageSeconds"] >= 0
    assert "status" in body["rebuild"]
    r = internal.get("/ready")
    assert r.status_code == 200 and r.json()["source"]["ok"] is True


@pytest.fixture
def export_files(client, tmp_path, monkeypatch):
    src = tmp_path / "src"
    for t in (0, 1):
        exports.write_doc(export_store.current(t), src / f"stufe{t}.json")
    monkeypatch.setattr(export_store, "TMP_DIR", tmp_path / "tmp")
    monkeypatch.setenv("QE_EXPORT_SOURCE", str(src / "stufe{tier}.json"))
    monkeypatch.setenv("QE_EXPORT_POLL_MINUTES", "0")
    yield src
    export_store.reset()


def test_ready_503_public_without_export(export_files, monkeypatch, internal):
    monkeypatch.setenv("QE_ROLE", "public")
    monkeypatch.setenv("QE_EXPORT_SOURCE", str(export_files / "fehlt-stufe{tier}.json"))
    monkeypatch.setattr(internal_app, "_check_source", lambda: False)
    with TestClient(app_module.app):
        r = internal.get("/ready")
        assert r.status_code == 503
        assert r.json()["source"]["ok"] is False
        h = internal.get("/health")
        assert h.status_code == 200 and h.json()["data"]["state"] == "missing"


def test_ready_public_with_export(export_files, monkeypatch, internal):
    monkeypatch.setenv("QE_ROLE", "public")
    monkeypatch.setattr(internal_app, "_check_source", lambda: False)   # informational only
    with TestClient(app_module.app):
        assert internal.get("/ready").status_code == 200


def test_ready_source_check_cached(client, internal, monkeypatch):
    calls = []
    clock = {"t": 1000.0}
    monkeypatch.setattr(internal_app, "_check_source", lambda: calls.append(1) or True)
    monkeypatch.setattr(internal_app.time, "monotonic", lambda: clock["t"])
    internal_app._SOURCE.update(ok=None, at=None, checkedAt=None)
    internal.get("/ready")
    clock["t"] += 10
    internal.get("/ready")
    assert len(calls) == 1
    clock["t"] += 31
    internal.get("/ready")
    assert len(calls) == 2


def test_metrics_exposed(client, internal):
    client.get("/api/sources")
    text = internal.get("/metrics").text
    assert 'http_requests_total{' in text
    assert 'route="/api/sources"' in text
    assert "http_request_duration_seconds_bucket" in text
    assert "quellenpanel_data_age_seconds" in text
    assert "quellenpanel_export_fetch_total" in text or "quellenpanel_rebuild_total" in text


def test_port_separation(client, internal):
    for path in ("/internal/exports/stufe0.json", "/metrics", "/ready"):
        assert client.get(path).status_code == 404, path
    assert internal.get("/api/sources").status_code == 404
    r = internal.get("/internal/exports/stufe0.json")
    assert r.status_code == 200 and r.headers["etag"] == export_store.etag(0)
    assert internal.get("/internal/exports/stufe0.json",
                        headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    assert internal.get("/internal/exports/stufe2.json").status_code == 404


def test_internal_exports_404_outside_team(client, internal, monkeypatch):
    monkeypatch.setenv("QE_ROLE", "public")
    assert internal.get("/internal/exports/stufe0.json").status_code == 404


def _counter(name, **labels):
    v = obs.REGISTRY.get_sample_value(name, labels)
    return v or 0.0


def test_rebuild_metrics(client, monkeypatch):
    import enduser
    import fetcher
    import store
    import truth

    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: None)
    monkeypatch.setattr(truth, "main", lambda: {})
    monkeypatch.setattr(store, "load", lambda: None)
    monkeypatch.setattr(enduser, "reload_supplements", lambda: None)
    monkeypatch.setattr(export_store, "rebuild_from_records", lambda *a, **k: None)
    ok0 = _counter("quellenpanel_rebuild_total", result="success")
    refresh._run_refresh()
    assert _counter("quellenpanel_rebuild_total", result="success") == ok0 + 1
    assert _counter("quellenpanel_rebuild_last_success_timestamp_seconds") > 0

    def boom(cb):
        raise RuntimeError("x")

    monkeypatch.setattr(fetcher, "refresh_all", boom)
    err0 = _counter("quellenpanel_rebuild_total", result="error")
    refresh._run_refresh()
    assert _counter("quellenpanel_rebuild_total", result="error") == err0 + 1


def test_export_fetch_metrics(export_files):
    ok0 = _counter("quellenpanel_export_fetch_total", tier="0", result="ok")
    export_store.reset()
    assert export_store.load_remote(0)
    assert _counter("quellenpanel_export_fetch_total", tier="0", result="ok") == ok0 + 1


def test_serve_builds_two_servers(monkeypatch):
    import serve

    monkeypatch.delenv("QE_PORT", raising=False)
    monkeypatch.delenv("QE_INTERNAL_PORT", raising=False)
    public, private = serve.build_servers()
    assert (public.port, private.port) == (8080, 9090)
    assert public.access_log is False and private.access_log is False
    assert public.lifespan == "on" and private.lifespan == "off"
    assert public.proxy_headers is False and private.server_header is False
