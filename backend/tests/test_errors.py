"""Etappe 3 / Task 2: one error JSON shape with trace_id, Retry-After, OpenAPI per role."""
import urllib.error

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app as app_module
import wlo_content


def test_404_json_has_trace_id(client):
    r = client.get("/api/sources/gibts:nicht")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"
    assert body["status"] == 404
    assert body["message"]
    assert body["trace_id"] == r.headers["X-B3-TraceId"]


def test_422_without_input_echo(client):
    r = client.get("/api/sources?page=0")
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_error"
    assert body["details"][0]["loc"]
    assert all(set(d) == {"loc", "msg"} for d in body["details"])
    assert body["trace_id"] == r.headers["X-B3-TraceId"]


def test_413_uses_error_shape(client):
    r = client.post("/api/sources/batch", content=b"x", headers={"Content-Length": "2000000"})
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


def test_500_hides_exception_text():
    def boom():
        raise RuntimeError("geheim-intern")

    app_module.app.router.routes.insert(0, APIRoute("/api/__test_boom500", boom))
    try:
        with TestClient(app_module.app, raise_server_exceptions=False) as c:
            r = c.get("/api/__test_boom500")
        assert r.status_code == 500
        body = r.json()
        assert body == {"error": "internal_error", "message": "Interner Fehler", "status": 500,
                        "trace_id": r.headers["X-B3-TraceId"]}
        assert "geheim-intern" not in r.text
    finally:
        app_module.app.router.routes[:] = [x for x in app_module.app.router.routes
                                           if getattr(x, "path", "") != "/api/__test_boom500"]


def _crawler_id():
    from store import _DATA
    return next(r["id"] for r in _DATA["records"]
                if r.get("kind") == "crawler" and (r.get("identity") or {}).get("spider"))


def test_upstream_failure_has_retry_after(client, monkeypatch):
    def fail(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(wlo_content, "fetch_contents", fail)
    r = client.get(f"/api/sources/{_crawler_id()}/contents")
    assert r.status_code == 502
    assert r.headers["Retry-After"] == "30"
    assert r.json()["retryAfter"] == 30
    assert r.json()["error"] == "bad_gateway"


def test_upstream_429_passes_retry_after(client, monkeypatch):
    def limited(*a, **k):
        raise urllib.error.HTTPError("https://x", 429, "Too Many", {"Retry-After": "120"}, None)

    monkeypatch.setattr(wlo_content, "fetch_contents", limited)
    r = client.get(f"/api/sources/{_crawler_id()}/contents")
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "120"
    assert r.json()["retryAfter"] == 120


@pytest.mark.parametrize("bad", ["Wed, 21 Oct 2015 07:28:00 GMT", "-5", "99999999"])
def test_upstream_429_ignores_odd_retry_after(client, monkeypatch, bad):
    def limited(*a, **k):
        raise urllib.error.HTTPError("https://x", 429, "Too Many", {"Retry-After": bad}, None)

    monkeypatch.setattr(wlo_content, "fetch_contents", limited)
    r = client.get(f"/api/sources/{_crawler_id()}/contents")
    assert r.status_code == 429
    assert r.json()["retryAfter"] == 30


def test_openapi_per_role(client, monkeypatch):
    paths = app_module.app.openapi()["paths"]
    assert "/api/stats/team" in paths
    assert not any(p.startswith("/internal") for p in paths)
    info = app_module.app.openapi()["info"]
    assert info["title"] == "Quellenpanel" and info["version"] == "1.0.0" and "Stufe" in info["description"]
    monkeypatch.setenv("QE_ROLE", "public")
    paths = app_module.app.openapi()["paths"]
    for team_only in ("/api/stats/team", "/api/protokoll.md", "/api/protokoll.json", "/api/protokoll.csv",
                      "/jobs/refresh", "/api/admin/reload", "/api/auth"):
        assert team_only not in paths, team_only
    assert "/api/sources" in paths
    assert not any(p.startswith("/internal") for p in paths)
