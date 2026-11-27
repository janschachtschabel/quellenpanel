"""Etappe 3 / Task 4: signed team session (HMAC, survives restarts) and TRUST_PROXY."""
import pytest
from starlette.requests import Request

import config
import ratelimit
import session


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("QE_SESSION_SECRET", "s1")
    session._revoked.clear()
    yield
    session._revoked.clear()


def test_token_shape():
    exp, nonce, sig = session.issue().split(".")
    assert exp.isdigit() and nonce and sig


def test_token_survives_restart_with_same_secret():
    token = session.issue()
    session._revoked.clear()                  # nothing but the secret is shared with a new process
    assert not hasattr(session, "_tokens")
    assert session.valid(token) is True


def test_other_secret_rejects(monkeypatch):
    token = session.issue()
    monkeypatch.setenv("QE_SESSION_SECRET", "s2")
    assert session.valid(token) is False


def _flip(ch: str) -> str:
    return "A" if ch != "A" else "B"


def test_tampered_and_garbage_rejected():
    token = session.issue()
    exp, nonce, sig = token.split(".")
    assert session.valid(f"{exp}.{nonce}.{sig[:-1]}{_flip(sig[-1])}") is False
    assert session.valid(f"{int(exp) + 3600}.{nonce}.{sig}") is False
    assert session.valid(f"{exp}.{nonce}x.{sig}") is False
    for bad in ("a.b", "", "x" * 5000, None, "1.2.3", "..", "-1.n.s", f"{exp}.{nonce}.{sig}.x", 42):
        assert session.valid(bad) is False, bad


def test_expired_rejected(monkeypatch):
    token = session.issue()
    real = session.time.time()
    monkeypatch.setattr(session.time, "time", lambda: real + session.TTL + 1)
    assert session.valid(token) is False


def test_revoke_blocks_token():
    token = session.issue()
    other = session.issue()
    session.revoke(token)
    assert session.valid(token) is False
    assert session.valid(other) is True
    session.revoke("garbage")                 # never raises
    session.revoke(None)


def test_revoked_list_evicts_expired(monkeypatch):
    session.revoke(session.issue())
    real = session.time.time()
    monkeypatch.setattr(session.time, "time", lambda: real + session.TTL + 1)
    session.revoke(session.issue())
    assert len(session._revoked) == 1


def test_missing_secret_generates_one_per_process(monkeypatch, caplog, tmp_path):
    monkeypatch.delenv("QE_SESSION_SECRET")
    blocker = tmp_path / "keine-mappe"
    blocker.write_text("x")                               # data dir not writable: key stays in memory
    monkeypatch.setenv("QE_DATA_DIR", str(blocker))
    monkeypatch.setattr(config, "_GENERATED_SECRET", None)
    with caplog.at_level("WARNING"):
        a = config.session_secret()
        b = config.session_secret()
    assert a == b and len(a) >= 32
    assert caplog.text.count("Neustart") == 1


def test_team_cookie_roundtrip(client, team_pw):
    r = client.post("/api/auth", headers={"X-Team-Password": team_pw})
    assert r.status_code == 200
    assert client.cookies.get(session.COOKIE)
    try:
        assert client.get("/api/sources?tier=2").json()["tier"] == 2
        assert client.get("/api/auth/status").json()["team"] is True
    finally:
        client.cookies.clear()


def _request(headers: dict, host="10.0.0.5") -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers":
                    [(k.lower().encode(), v.encode()) for k, v in headers.items()],
                    "client": (host, 1234), "query_string": b""})


def test_client_ip_trust_proxy(monkeypatch):
    xff = {"X-Forwarded-For": "203.0.113.9"}
    monkeypatch.delenv("TRUST_PROXY", raising=False)
    assert ratelimit.client_ip(_request(xff)) == "10.0.0.5"
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert config.trust_proxy() is True
    assert ratelimit.client_ip(_request(xff)) == "203.0.113.9"
    assert ratelimit.client_ip(_request({})) == "10.0.0.5"           # no header: socket peer
    assert ratelimit.client_ip(_request({"X-Forwarded-For": " , "})) == "10.0.0.5"
    monkeypatch.setenv("TRUST_PROXY", "nein")
    assert config.trust_proxy() is False


def test_client_ip_trust_proxy_uses_rightmost(monkeypatch):
    # Behind a proxy that APPENDS, the leftmost entries are client-controlled: take the rightmost.
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert ratelimit.client_ip(_request({"X-Forwarded-For": "1.2.3.4, 203.0.113.9"})) == "203.0.113.9"


def test_missing_secret_is_kept_in_the_team_data_dir(monkeypatch, tmp_path):
    # A deploy without QE_SESSION_SECRET keeps team logins across restarts: the key lives in the volume.
    monkeypatch.delenv("QE_SESSION_SECRET")
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(config, "_GENERATED_SECRET", None)
    a = config.session_secret()
    monkeypatch.setattr(config, "_GENERATED_SECRET", None)   # "restart"
    assert config.session_secret() == a and len(a) >= 32
    key = tmp_path / "session.key"
    assert key.is_file() and (key.stat().st_mode & 0o077) == 0


def test_trust_proxy_ignores_forwarded_for_from_a_public_peer(monkeypatch):
    # The app port may also be published directly: a client from the internet (public peer address)
    # must not choose its own rate-limit key via X-Forwarded-For. Only a private peer (the proxy) counts.
    monkeypatch.setenv("TRUST_PROXY", "1")
    forged = {"X-Forwarded-For": "198.51.100.1"}
    assert ratelimit.client_ip(_request(forged, host="93.184.216.34")) == "93.184.216.34"
    assert ratelimit.client_ip(_request(forged, host="172.18.0.1")) == "198.51.100.1"
    assert ratelimit.client_ip(_request(forged, host="127.0.0.1")) == "198.51.100.1"
