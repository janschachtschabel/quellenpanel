"""README in zwei Sprachen (Jan, 27.11.2026): Installation, Nutzung, Zugangsstufen und Schutz,
Bearbeitungsbereich, Datenabruf über die API — beide Fassungen gleich gegliedert und korrekt."""
import re
from pathlib import Path

import pytest

import app as app_module

ROOT = Path(__file__).resolve().parents[2]
DE, EN = ROOT / "README.md", ROOT / "README.en.md"
ABSCHNITTE = {
    DE: ("Installation", "Nutzung", "Zugangsstufen", "Bearbeitungsbereich", "Daten über die API", "Einbetten"),
    EN: ("Installation", "Usage", "Access tiers", "Editing area", "Data via the API", "Embedding"),
}


def _h2(p: Path) -> list[str]:
    return re.findall(r"^## (.+)$", p.read_text(encoding="utf-8"), re.M)


def test_beide_fassungen_gibt_es_und_sie_verweisen_aufeinander():
    assert "README.en.md" in DE.read_text(encoding="utf-8")
    assert "README.md" in EN.read_text(encoding="utf-8")


def test_beide_fassungen_gleich_gegliedert():
    assert len(_h2(DE)) == len(_h2(EN)) >= 8


@pytest.mark.parametrize("datei", [DE, EN])
def test_pflichtabschnitte(datei):
    kopf = " | ".join(_h2(datei))
    for a in ABSCHNITTE[datei]:
        assert a in kopf, a


@pytest.mark.parametrize("datei", [DE, EN])
def test_schutz_und_bearbeitung_erklaert(datei):
    t = datei.read_text(encoding="utf-8")
    for s in ("QE_TEAM_PASSWORD", "QE_TIER1_PASSWORD", "QE_SESSION_SECRET", "VPN/SSO", "networkPolicy.enabled",
              "x-tier1-password", "Korrekturen", "kopf=\"aus\""):
        assert s in t, s


def _norm(p: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", p.split("?")[0]).rstrip("/")


@pytest.mark.parametrize("datei", [DE, EN])
def test_genannte_pfade_gibt_es(client, monkeypatch, datei):
    bekannt = set()
    for rolle in ("team", "partner", "public"):
        monkeypatch.setenv("QE_ROLE", rolle)
        app_module._openapi_cache.clear()
        bekannt |= {_norm(p) for p in app_module.app.openapi()["paths"]}
    app_module._openapi_cache.clear()
    muster = [re.compile("^" + re.sub(r"\\{\\}", "[^/]+", re.escape(b)) + "$") for b in bekannt]
    genannt = {_norm(p) for p in re.findall(r"(/(?:api|jobs)/[A-Za-z0-9_./{}:%-]*[A-Za-z0-9_}])", datei.read_text(encoding="utf-8"))}
    assert genannt and sorted(g for g in genannt if not any(m.match(g) for m in muster)) == []


@pytest.mark.parametrize("datei", [DE, EN])
def test_genannte_filterparameter_gibt_es(datei):
    """Jeder im Abschnitt zur API genannte Query-Parameter `name=` existiert in /api/sources."""
    import inspect
    erlaubt = set(inspect.signature(app_module._filters).parameters) | {"page", "page_size", "tier", "max_items", "skip"}
    t = datei.read_text(encoding="utf-8")
    genannt = set(re.findall(r"[?&]([a-z_]+)=", t))
    assert genannt and sorted(genannt - erlaubt - {"kopf", "fuss", "filter", "rahmen", "ansicht", "hintergrund",
                                                    "farbe", "fach", "max"}) == []
