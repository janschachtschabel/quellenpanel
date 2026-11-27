"""Welcher Code-Stand läuft: /api/capabilities nennt Revision (CI-Build) und Bauzeit des Images."""
import config


def test_capabilities_nennt_revision_und_bauzeit(client, monkeypatch):
    monkeypatch.setattr(config, "REVISION", "29d4d9dcca12")
    monkeypatch.setattr(config, "BUILT", "2026-11-27T15:40:00Z")
    caps = client.get("/api/capabilities").json()
    assert caps["revision"] == "29d4d9dcca12" and caps["built"] == "2026-11-27T15:40:00Z"


def test_revision_ohne_angabe_ist_leer(monkeypatch):
    monkeypatch.delenv("QE_REVISION", raising=False)
    assert config._revision() == ""


def test_bauzeit_aus_datei_im_image(tmp_path):
    f = tmp_path / "BUILD_TIME"
    assert config._built(f) == ""
    f.write_text("2026-11-27T15:40:00Z\n", encoding="utf-8")
    assert config._built(f) == "2026-11-27T15:40:00Z"


def test_dockerfile_schreibt_bauzeit():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "Dockerfile").read_text(encoding="utf-8")
    assert "BUILD_TIME" in text and "ARG QE_REVISION" in text
