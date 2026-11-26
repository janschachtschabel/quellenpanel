"""Live-Abruf und Beispielinhalte: Endpunkte, Kriterien und Properties kommen aus dem Profil."""
import io
import json
import shutil
from pathlib import Path

import pytest

import fetcher
import repo_profile
import wlo_content

PROFILES = Path(__file__).resolve().parents[2] / "profiles"
LRT = "http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/2e678af3-1026-4171-b88e-3b3a915d1673"
NODE = {"ref": {"id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"}, "properties": {
    "ccm:oeh_publisher_combined": ["Alpha"], "ccm:taxonentry_DISPLAYNAME": ["Mathematik"]}}


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@pytest.fixture(autouse=True)
def _reset():
    yield
    repo_profile.reset()


def _foreign_profile(monkeypatch, tmp_path, mds="mds_test"):
    shutil.copytree(PROFILES / "wlo", tmp_path / "test", ignore=shutil.ignore_patterns("daten"))
    toml = tmp_path / "test" / "profil.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace('mds = "mds_oeh"', f'mds = "{mds}"')
                    .replace('publisher = "ccm:oeh_publisher_combined"', 'publisher = "ccm:publisher"'),
                    encoding="utf-8")
    monkeypatch.setenv("QE_PROFILES_DIR", str(tmp_path))
    monkeypatch.setenv("QE_PROFILE", "test")
    repo_profile.reset()


def test_fetch_quellen_uses_profile_criterion(monkeypatch):
    sent = []

    def fake_post(url, json=None, **_kw):
        sent.append({"url": url, "json": json})
        return _Resp({"pagination": {"total": 1}, "nodes": [NODE]})

    monkeypatch.setattr(fetcher.requests, "post", fake_post)
    assert fetcher._fetch_quellen(lambda d, t: None) == [NODE]
    assert sent[0]["url"].startswith(
        "https://redaktion.openeduhub.net/edu-sharing/rest/search/v1/queries/-home-/mds_oeh/ngsearch")
    assert sent[0]["json"]["criteria"] == [{"property": "ccm:oeh_lrt_aggregated", "values": [LRT]}]


def test_other_profile_changes_mds(monkeypatch, tmp_path):
    _foreign_profile(monkeypatch, tmp_path)
    assert "/-home-/mds_test/ngsearch" in fetcher.ngsearch_url()


def test_refresh_writes_into_raw_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))

    def fake_post(url, json=None, **_kw):
        if json and json.get("facets"):
            return _Resp({"facets": [{"values": [{"value": "x_spider", "count": 3}]}], "pagination": {"total": 9}})
        return _Resp({"pagination": {"total": 1}, "nodes": [NODE]})

    monkeypatch.setattr(fetcher.requests, "post", fake_post)
    monkeypatch.setattr(fetcher.requests, "get", lambda *a, **k: _Resp({"hasTopConcept": []}))
    monkeypatch.setattr(fetcher.time, "sleep", lambda s: None)
    fetcher.refresh_all()
    names = {p.name for p in (tmp_path / "raw").iterdir()}
    assert {"cache_facet_bezugsquellen.json", "cache_meta.json", "cache_facet_spider.json",
            "quellen_nodes.json", "extra_nodes.json", "replication_publisher_gap.csv",
            "bq_previews.json", "vocab_sources.json"} <= names


def test_contents_use_profile_mds_and_fields(monkeypatch, tmp_path):
    _foreign_profile(monkeypatch, tmp_path)
    seen = {}

    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url
        return io.BytesIO(json.dumps({"nodes": [NODE], "pagination": {"total": 1}}).encode())

    monkeypatch.setattr(wlo_content.urllib.request, "urlopen", fake_urlopen)
    out = wlo_content.fetch_contents("ccm:publisher", "Alpha")
    assert "/-home-/mds_test/ngsearch" in seen["url"]
    assert out["nodes"][0]["subjects"] == ["Mathematik"]


def test_source_contents_property_from_profile(monkeypatch, tmp_path, client):
    _foreign_profile(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(wlo_content, "fetch_contents", lambda prop, value, n, s: calls.append(prop) or {"total": 0, "nodes": []})
    from store import _DATA
    rid = next(r["id"] for r in _DATA["byId"].values() if r["kind"] == "manuell")
    assert client.get(f"/api/sources/{rid}/contents").status_code == 200
    assert calls == ["ccm:publisher"]
