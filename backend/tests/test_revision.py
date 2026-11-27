"""Welcher Code-Stand läuft: /api/capabilities nennt die Revision aus dem Image (QE_REVISION)."""
import config


def test_capabilities_nennt_revision(client, monkeypatch):
    monkeypatch.setattr(config, "REVISION", "29d4d9dcca12")
    assert client.get("/api/capabilities").json()["revision"] == "29d4d9dcca12"


def test_revision_ohne_angabe_ist_leer(monkeypatch):
    monkeypatch.delenv("QE_REVISION", raising=False)
    assert config._revision() == ""
