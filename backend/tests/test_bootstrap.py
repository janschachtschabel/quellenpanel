"""Etappe 3 / Task 5: no data in the image — first start builds, seed, rebuild status, Vercel gone."""
import io
import shutil
import threading
import time
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
import bootstrap
import config
import export_store
import fetcher
import internal_app
import refresh
import truth

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_TRUTH = Path(__file__).resolve().parents[1] / "data" / "truth.json"


def _wait_job_end(timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if refresh.status()["status"] != "running":
            return
        time.sleep(0.05)
    raise AssertionError("Job endet nicht")


def _wait_bootstrap(timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not bootstrap.loading():
            return
        time.sleep(0.05)
    raise AssertionError("Bootstrap endet nicht")


@pytest.fixture
def empty_data(tmp_path, monkeypatch):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("QE_SEED_URL", raising=False)
    monkeypatch.setattr(truth, "main", lambda: shutil.copy(FIXTURE_TRUTH, tmp_path / "truth.json") and {})
    internal_app._SOURCE.update(ok=True, at=time.monotonic() + 3600, checkedAt="x")  # no network
    refresh._JOB.update(status="idle")
    yield tmp_path
    _wait_bootstrap()
    _wait_job_end()
    refresh._JOB.update(status="idle")
    internal_app._SOURCE.update(ok=None, at=None, checkedAt=None)


def test_first_start_building(empty_data, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: gate.wait(5))
    internal = TestClient(internal_app.app)
    try:
        with TestClient(app_module.app) as c:
            r = c.get("/api/sources")
            assert r.status_code == 503
            assert r.json()["message"] == "Daten werden aufgebaut"
            assert r.json()["retryAfter"] == 60 and r.headers["Retry-After"] == "60"
            assert c.get("/api/health").status_code in (200, 503)
            h = internal.get("/health")
            assert h.status_code == 200 and h.json()["data"]["state"] == "building"
            assert internal.get("/ready").status_code == 503
            _wait_bootstrap()
            assert bootstrap.read_status()["status"] == "running"
            gate.set()
            _wait_job_end()
            assert c.get("/api/sources").status_code == 200
            assert internal.get("/ready").status_code == 200
            assert export_store.current(0) is not None
            assert bootstrap.read_status()["status"] == "done"
    finally:
        gate.set()


def test_first_start_failure_status_readable(empty_data, monkeypatch):
    def boom(cb):
        raise RuntimeError("upstream kaputt")

    monkeypatch.setattr(fetcher, "refresh_all", boom)
    internal = TestClient(internal_app.app)
    with TestClient(app_module.app) as c:
        _wait_bootstrap()
        _wait_job_end()
        h = internal.get("/health").json()
        assert h["rebuild"]["last"]["status"] == "error"
        assert "upstream kaputt" not in str(h)
        assert c.get("/api/sources").status_code == 503
        assert internal.get("/ready").status_code == 503


def test_status_written_on_shutdown_during_rebuild(empty_data, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: gate.wait(5))
    try:
        with TestClient(app_module.app):
            _wait_bootstrap()
            assert refresh.status()["status"] == "running"
        assert bootstrap.read_status()["status"] == "abgebrochen"
    finally:
        gate.set()


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_seed_downloads_missing_only(monkeypatch, tmp_path):
    monkeypatch.setenv("QE_SEED_URL", "https://seed.example/daten/")
    (tmp_path / "korrekturen.csv").write_text("alt", encoding="utf-8")
    seen = []

    def fake(req, timeout=None):
        name = req.full_url.rsplit("/", 1)[1]
        seen.append(req.full_url)
        if name == "truth.json":
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return _Resp(f"neu:{name}".encode())

    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fake)
    assert bootstrap.seed(tmp_path) == ["crawler.csv"]
    assert (tmp_path / "crawler.csv").read_text(encoding="utf-8") == "neu:crawler.csv"
    assert (tmp_path / "korrekturen.csv").read_text(encoding="utf-8") == "alt"
    assert not (tmp_path / "truth.json").exists()
    assert "https://seed.example/daten/crawler.csv" in seen
    assert not any(u.endswith("korrekturen.csv") for u in seen)


def test_seed_without_url_does_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("QE_SEED_URL", raising=False)
    assert bootstrap.seed(tmp_path) == []


def test_seed_failure_is_soft(monkeypatch, tmp_path):
    monkeypatch.setenv("QE_SEED_URL", "https://seed.example")

    def fail(req, timeout=None):
        raise urllib.error.URLError("weg")

    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", fail)
    assert bootstrap.seed(tmp_path) == []
    assert list(tmp_path.iterdir()) == []


def test_seed_then_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("QE_SEED_URL", "https://seed.example")
    payload = FIXTURE_TRUTH.read_bytes()
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(payload if req.full_url.endswith("truth.json") else b"x"))
    assert bootstrap.start_team() == "building"          # seed runs off the event loop
    _wait_bootstrap()
    assert export_store.current(0) is not None


def test_dockerignore_excludes_data():
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for pattern in ("backend/data/truth.json", "backend/data/raw/", "backend/data/exports/", "profiles/*/daten/"):
        assert pattern in lines, pattern
    assert "vercel.json" not in lines and "backend/api/" not in lines


def test_vercel_removed():
    assert not (ROOT / "vercel.json").exists()
    assert not (ROOT / "backend" / "api").exists()
    assert "vercel" not in (ROOT / "README.md").read_text(encoding="utf-8").lower()
    assert config.seed_url() == "" or isinstance(config.seed_url(), str)


# --- Abschlussreview Etappe 3 ----------------------------------------------------------------
def test_slow_seed_does_not_block_startup(empty_data, monkeypatch):
    monkeypatch.setenv("QE_SEED_URL", "https://seed.example")
    gate = threading.Event()
    monkeypatch.setattr(bootstrap, "seed", lambda d: gate.wait(5) and [])
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: None)
    internal = TestClient(internal_app.app)
    t0 = time.monotonic()
    try:
        with TestClient(app_module.app) as c:
            assert time.monotonic() - t0 < 3                   # lifespan did not wait for the seed
            assert c.get("/api/sources").status_code == 503
            assert internal.get("/health").json()["data"]["state"] == "building"
            gate.set()
            _wait_bootstrap()
    finally:
        gate.set()


def test_seed_rejects_html_and_bad_truth(monkeypatch, tmp_path):
    monkeypatch.setenv("QE_SEED_URL", "https://seed.example")
    bodies = {"crawler.csv": b"<!DOCTYPE html><html>login</html>", "korrekturen.csv": b"a,b\n1,2\n",
              "truth.json": b'{"kein": "truth"}'}
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp(bodies[req.full_url.rsplit("/", 1)[1]]))
    assert bootstrap.seed(tmp_path) == ["korrekturen.csv"]
    assert not (tmp_path / "crawler.csv").exists() and not (tmp_path / "truth.json").exists()


def test_broken_local_truth_falls_back_to_building(empty_data, monkeypatch):
    (empty_data / "truth.json").write_text("<html>kaputt", encoding="utf-8")
    gate = threading.Event()
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: gate.wait(5))
    internal = TestClient(internal_app.app)
    try:
        with TestClient(app_module.app) as c:                  # no crash loop
            _wait_bootstrap()
            assert c.get("/api/sources").status_code == 503
            assert internal.get("/health").json()["data"]["state"] == "building"
            assert list(empty_data.glob("truth.json.kaputt-*"))
    finally:
        gate.set()


# --- Abschluss-Audit 1.0.0 -----------------------------------------------------------------------
def test_rebuild_refuses_without_curated_files(tmp_path, monkeypatch, caplog):
    # The image carries no korrekturen.csv / crawler.csv. Without them a build would publish
    # blacklisted sources and drop every correction, silently. It must refuse and say why.
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "korrekturen_csv_path", lambda: None)
    called = []
    monkeypatch.setattr(fetcher, "refresh_all", lambda cb: called.append(1))
    with caplog.at_level("ERROR"):
        r = refresh.start()
    assert r["status"] == "error" and "korrekturen.csv" in r["message"]
    assert called == []
    assert refresh.status()["status"] == "error"
    assert "korrekturen.csv" in caplog.text
    assert (bootstrap.read_status() or {}).get("status") == "error"
    # Files back: the build runs again.
    monkeypatch.setattr(config, "korrekturen_csv_path", lambda: tmp_path / "korrekturen.csv")
    monkeypatch.setattr(config, "crawler_csv_path", lambda: tmp_path / "crawler.csv")
    monkeypatch.setattr(refresh, "_run_refresh", lambda: called.append(2))
    assert refresh.start()["status"] == "started"
