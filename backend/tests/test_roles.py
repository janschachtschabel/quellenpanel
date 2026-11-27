"""Rollen team/partner/public: die Stufen-Obergrenze kommt aus der Rolle (Etappe 2)."""
import types

import pytest

import config
import session
import tiers


def _req(cookie=None):
    return types.SimpleNamespace(cookies=({session.COOKIE: cookie} if cookie else {}), headers={},
                                 client=types.SimpleNamespace(host="127.0.0.9"))


@pytest.fixture(autouse=True)
def _clean_role(monkeypatch):
    monkeypatch.delenv("QE_ROLE", raising=False)
    monkeypatch.delenv("QE_PUBLIC_ONLY", raising=False)


def test_role_default_is_team():
    assert config.role() == "team"


def test_public_only_alias(monkeypatch):
    monkeypatch.setenv("QE_PUBLIC_ONLY", "1")
    assert config.role() == "public"
    assert tiers.max_tier(_req(), None, "test-team-pw", None) == 0


def test_invalid_role_raises(monkeypatch):
    monkeypatch.setenv("QE_ROLE", "admin")
    with pytest.raises(ValueError, match="admin"):
        config.role()


def test_partner_caps_at_1_and_ignores_team(monkeypatch):
    monkeypatch.setenv("QE_ROLE", "partner")
    monkeypatch.setattr(config, "TIER1_PW", "p")
    assert tiers.max_tier(_req(), None, "test-team-pw", None) == 0
    assert tiers.max_tier(_req(), None, None, "p") == 1


def test_partner_without_tier1_pw_is_closed(monkeypatch):
    monkeypatch.setenv("QE_ROLE", "partner")
    monkeypatch.setattr(config, "TIER1_PW", "")
    assert tiers.max_tier(_req(), None, None, None) == 0


@pytest.mark.parametrize("role", ["partner", "public"])
def test_is_team_false_outside_team_role(monkeypatch, role):
    monkeypatch.setenv("QE_ROLE", role)
    assert tiers.is_team(_req(), "test-team-pw") is False


def test_team_role_keeps_team_and_closed_tier1():
    assert tiers.max_tier(_req(), None, "test-team-pw", None) == 2
    assert tiers.max_tier(_req(), None, None, None) == 0      # tier 1 needs its password


def test_capabilities_reports_role(client):
    caps = client.get("/api/capabilities").json()
    assert caps["role"] == "team"
    assert caps["teamAvailable"] is True and caps["tier1Gated"] is True   # one port: tier 1 gated too


def test_capabilities_partner(client, monkeypatch):
    monkeypatch.setenv("QE_ROLE", "partner")
    caps = client.get("/api/capabilities").json()
    assert caps["role"] == "partner" and caps["tier1Gated"] is True
    assert caps["teamAvailable"] is False and caps["publicOnly"] is False


@pytest.mark.parametrize("role", ["team", "partner"])
def test_public_only_conflicting_role_raises(monkeypatch, role):
    # Zwischenreview: QE_PUBLIC_ONLY=1 neben QE_ROLE=team/partner darf nicht still öffnen.
    monkeypatch.setenv("QE_PUBLIC_ONLY", "1")
    monkeypatch.setenv("QE_ROLE", role)
    with pytest.raises(ValueError, match="QE_PUBLIC_ONLY"):
        config.role()


def test_public_only_with_public_role_ok(monkeypatch):
    monkeypatch.setenv("QE_PUBLIC_ONLY", "1")
    monkeypatch.setenv("QE_ROLE", "public")
    assert config.role() == "public"


def test_partner_ignores_team_cookie(monkeypatch):
    monkeypatch.setenv("QE_ROLE", "partner")
    monkeypatch.setattr(config, "TIER1_PW", "p")
    token = session.issue()
    assert tiers.max_tier(_req(token), None, None, None) == 0


def test_partner_without_pw_warns_on_start(monkeypatch, caplog):
    from fastapi.testclient import TestClient

    import app as app_module
    monkeypatch.setenv("QE_ROLE", "partner")
    monkeypatch.setattr(config, "TIER1_PW", "")
    with caplog.at_level("WARNING"), TestClient(app_module.app):
        pass
    assert "QE_TIER1_PASSWORD" in caplog.text


@pytest.mark.parametrize("role", ["partner", "public"])
def test_auth_route_404_outside_team(client, monkeypatch, role):
    monkeypatch.setenv("QE_ROLE", role)
    assert client.post("/api/auth", headers={"X-Team-Password": "test-team-pw"}).status_code == 404
