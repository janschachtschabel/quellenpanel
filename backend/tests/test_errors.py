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


def test_upstream_4xx_is_not_retryable(client, monkeypatch):
    # A 4xx from the repository will not heal by waiting: 502 without a retry hint.
    def bad(*a, **k):
        raise urllib.error.HTTPError("https://x", 400, "Bad Request", {}, None)

    monkeypatch.setattr(wlo_content, "fetch_contents", bad)
    r = client.get(f"/api/sources/{_crawler_id()}/contents")
    assert r.status_code == 502
    assert "Retry-After" not in r.headers and "retryAfter" not in r.json()


def test_upstream_5xx_is_retryable(client, monkeypatch):
    def down(*a, **k):
        raise urllib.error.HTTPError("https://x", 503, "Unavailable", {}, None)

    monkeypatch.setattr(wlo_content, "fetch_contents", down)
    r = client.get(f"/api/sources/{_crawler_id()}/contents")
    assert r.status_code == 502 and r.headers["Retry-After"] == "30"


def test_own_rate_limit_sends_retry_after(client, monkeypatch):
    import ratelimit
    ratelimit.FETCH_HITS.clear()
    monkeypatch.setattr(ratelimit, "FETCH_MAX", 0)
    try:
        for path in (f"/api/sources/{_crawler_id()}/contents", "/api/thumb?url=https://evil.example/x.jpg"):
            r = client.get(path)
            assert r.status_code == 429, path
            assert int(r.headers["Retry-After"]) > 0 and r.json()["retryAfter"] > 0
    finally:
        ratelimit.FETCH_HITS.clear()


def test_login_throttle_sends_retry_after(client):
    app_module._LOGIN_FAILS.clear()
    try:
        for _ in range(8):
            client.post("/api/auth", headers={"X-Team-Password": "falsch"})
        r = client.post("/api/auth", headers={"X-Team-Password": "falsch"})
        assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    finally:
        app_module._LOGIN_FAILS.clear()


def test_thumb_upstream_errors_follow_error_classes(client, monkeypatch):
    import config
    import thumb

    class R:
        def __init__(self, code, headers=None):
            self.status_code, self.headers = code, headers or {}

        def raise_for_status(self):
            import requests
            if self.status_code >= 400:
                raise requests.HTTPError(response=self)

        def close(self):
            pass

    url = f"/api/thumb?url={config.REPO_URL}/edu-sharing/p.jpg"
    for code, retry in ((404, None), (503, "30"), (429, "90")):
        monkeypatch.setattr(thumb.requests, "get",
                            lambda *a, _c=code, **k: R(_c, {"Retry-After": "90"} if _c == 429 else {}))
        r = client.get(url)
        assert r.status_code == (429 if code == 429 else 502), code
        assert r.headers.get("Retry-After") == retry, code
    monkeypatch.setattr(thumb.requests, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    r = client.get(url)
    assert r.status_code == 502 and r.headers["Retry-After"] == "30"


def test_thumb_cache_budget_from_env(monkeypatch):
    import config
    monkeypatch.delenv("QE_THUMB_CACHE_MB", raising=False)
    assert config.thumb_cache_bytes() == 16 * 1024 * 1024     # fits the small public/partner pods
    monkeypatch.setenv("QE_THUMB_CACHE_MB", "64")
    assert config.thumb_cache_bytes() == 64 * 1024 * 1024
    monkeypatch.setenv("QE_THUMB_CACHE_MB", "0")
    assert config.thumb_cache_bytes() == 0                    # 0 switches the cache off
    monkeypatch.setenv("QE_THUMB_CACHE_MB", "viel")
    assert config.thumb_cache_bytes() == 16 * 1024 * 1024


def test_thumb_respects_cache_budget(client, monkeypatch):
    import config
    import thumb

    class R:
        status_code, headers = 200, {"Content-Type": "image/png"}

        def raise_for_status(self):
            pass

        def iter_content(self, n):
            yield b"x" * 100

        def close(self):
            pass

    monkeypatch.setattr(thumb.requests, "get", lambda *a, **k: R())
    monkeypatch.setenv("QE_THUMB_CACHE_MB", "0")
    thumb._CACHE.clear()
    assert client.get(f"/api/thumb?url={config.REPO_URL}/edu-sharing/q.png").status_code == 200
    assert thumb._CACHE == {}
