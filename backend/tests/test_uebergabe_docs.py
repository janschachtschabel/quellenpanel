"""Etappe 7: Übergabe-Doku nach dem Diensteleitfaden (Kapitel 6) ist vollständig und stimmt mit dem Code."""
import re
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parents[2]
UEB = ROOT / "docs/uebergabe"

STECKBRIEF_ZEILEN = ("Kurzbeschreibung", "Funktionen", "b-api", "Ruft selbst die b-api?", "Abhängigkeiten",
                     "Clusterfähigkeit", "Updates und CronJobs", "Ressourcen", "Image-Größe", "Ansprechperson")
MATRIX_SPALTEN = ("Dienst-ID", "braucht Dienste", "Rechte am Schlüssel", "Delegations-Scopes", "LLM-Route",
                  "Repository-Bezug", "nur gemeinsam mit")
PAKET_PUNKTE = ("Repo", "OpenAPI", "Ports", "Header", "Auth", "Prometheus", "Log", "Zustand", "Ressourcen",
                "Daten", "Updates", "Env", "Helm", "Secrets", "Dockerfile", "Compose", "NetworkPolicy",
                "Kosten", "Kompatibilitätsmatrix", "Ansprechperson")


def _text(name: str) -> str:
    return (UEB / name).read_text(encoding="utf-8")


def _zeilen(text: str) -> dict[str, str]:
    """Erste Spalte → Rest einer Markdown-Tabelle (Fettdruck entfernt)."""
    out = {}
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|(.+)\|\s*$", text, re.M):
        out[m.group(1).strip("* ")] = m.group(2)
    return out


def test_steckbrief_beantwortet_jede_zeile_mit_status():
    zeilen = _zeilen(_text("steckbrief.md"))
    for z in STECKBRIEF_ZEILEN:
        assert z in zeilen, z
        zellen = [c.strip() for c in zeilen[z].split("|")]
        assert len(zellen) >= 2 and zellen[0] and zellen[-1], f"{z}: Angabe und Status nötig"


def test_steckbrief_kurzbeschreibung_ist_info_description(client):
    desc = app_module.app.openapi()["info"]["description"]
    assert desc in " ".join(_text("steckbrief.md").split())


def test_ansprechperson_ist_offen_markiert_nicht_erfunden():
    zeile = _zeilen(_text("steckbrief.md"))["Ansprechperson"]
    assert "offen" in zeile.lower()


def _norm(p: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", p.split("?")[0]).rstrip("/")


@pytest.mark.parametrize("datei", ["steckbrief.md", "README.md"])
def test_genannte_api_pfade_gibt_es_in_einer_rolle(client, monkeypatch, datei):
    bekannt = set()
    for rolle in ("team", "partner", "public"):
        monkeypatch.setenv("QE_ROLE", rolle)
        app_module._openapi_cache.clear()
        bekannt |= {_norm(p) for p in app_module.app.openapi()["paths"]}
    app_module._openapi_cache.clear()
    genannt = {_norm(p) for p in re.findall(r"(/(?:api|jobs)/[A-Za-z0-9_./{}-]*[A-Za-z0-9_}])", _text(datei))}
    assert genannt, "keine Pfade gefunden"
    assert sorted(genannt - bekannt) == []


def test_matrix_hat_alle_spalten_und_eine_zeile_quellenpanel():
    text = _text("kompatibilitaet.md")
    kopf = next(line for line in text.splitlines() if line.startswith("| Dienst-ID"))
    assert [c.strip() for c in kopf.strip("|").split("|")] == list(MATRIX_SPALTEN)
    zeile = next(line for line in text.splitlines() if re.match(r"^\|\s*`?quellenpanel`?\s*\|", line))
    assert len([c for c in zeile.strip("|").split("|")]) == len(MATRIX_SPALTEN)


def test_uebergabepaket_deckt_jeden_punkt_ab_und_verweist_auf_vorhandene_dateien():
    text = _text("README.md")
    for p in PAKET_PUNKTE:
        assert p in text, p
    for ziel in re.findall(r"\]\((?!https?:)([^)#]+)", text):
        assert (UEB / ziel).resolve().exists(), ziel


def _env_namen() -> set[str]:
    namen = set()
    for f in (ROOT / "backend").glob("*.py"):
        namen |= set(re.findall(r"(?:environ\.get|getenv|_port)\(\s*\"([A-Z][A-Z0-9_]+)\"", f.read_text(encoding="utf-8")))
    return namen


def test_changelog_und_betrieb_nennen_jede_env_variable():
    namen = _env_namen()
    assert {"QE_ROLE", "TRUST_PROXY", "QE_PORT", "LOG_LEVEL"} <= namen
    for doc in (ROOT / "CHANGELOG.md", ROOT / "docs/betrieb.md"):
        text = doc.read_text(encoding="utf-8")
        assert sorted(n for n in namen if n not in text) == [], doc.name


def test_changelog_hat_release_1_0_0_mit_betriebshinweisen():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    teil = text.split("## [1.0.0]", 1)[1].split("\n## [", 1)[0]
    assert "Hinweise für den Betrieb" in teil
    for stichwort in ("/data", "latest", "QE_ROLE", "9090"):
        assert stichwort in teil, stichwort


def test_info_description_hat_zwei_saetze(client):
    """Leitfaden: Kurzbeschreibung = info.description, in zwei Sätzen."""
    desc = app_module.app.openapi()["info"]["description"]
    assert len(re.findall(r"[.!?](?:\s|$)", desc)) == 2, desc
