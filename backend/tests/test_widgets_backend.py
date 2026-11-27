"""Etappe 5: Kennzahl-API und iframe-Seiten der Widgets."""
import pytest


def test_kennzahl_all_and_by_subject(client):
    alle = client.get("/api/kennzahl").json()
    assert alle["quellen"] == client.get("/api/sources").json()["total"]
    assert alle["inhalte"] > 0
    fach = client.get("/api/sources", params={"page_size": 1}).json()["items"][0]["subjects"][0]
    teil = client.get("/api/kennzahl", params={"subject": fach}).json()
    assert 0 < teil["quellen"] <= alle["quellen"] and teil["inhalte"] <= alle["inhalte"]
    oer = client.get("/api/kennzahl", params={"oer": True}).json()
    assert oer["quellen"] == client.get("/api/sources", params={"oer": True}).json()["total"]


def test_kennzahl_ignores_team_session(client, team_pw):
    """Immer Stufe 0, auch mit Team-Login (öffentliche Zahl)."""
    anon = client.get("/api/kennzahl").json()
    assert client.get("/api/kennzahl", headers={"X-Team-Password": team_pw}, params={"tier": 2}).json() == anon


def test_embed_page_escapes_and_filters_attributes(client):
    r = client.get("/embed/quellen-liste", params={"fach": '"><script>alert(1)</script>', "variante": "schlicht",
                                                   "onload": "x", "max": "5"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "<script>alert" not in html and "&lt;script&gt;" in html
    assert 'variante="schlicht"' in html and 'max="5"' in html and "onload" not in html
    assert "<wlo-quellen-liste" in html
    assert '<script src="/widgets/quellenpanel-widgets.js" defer></script>' in html
    assert "<script>" not in html                                   # no inline script


def test_embed_unknown_widget_404(client):
    assert client.get("/embed/gibtsnicht").status_code == 404


def test_embed_value_length_capped(client):
    html = client.get("/embed/quellen-top", params={"fach": "x" * 500}).text
    assert 'fach="' + "x" * 200 + '"' in html and "x" * 201 not in html


@pytest.mark.parametrize("role,env,expected", [
    ("public", None, "frame-ancestors *"),
    ("team", None, "frame-ancestors 'self'"),
    ("public", "https://a.example https://b.example", "frame-ancestors https://a.example https://b.example"),
])
def test_embed_csp(client, monkeypatch, role, env, expected):
    monkeypatch.setenv("QE_ROLE", role)
    if env:
        monkeypatch.setenv("QE_FRAME_ANCESTORS", env)
    else:
        monkeypatch.delenv("QE_FRAME_ANCESTORS", raising=False)
    csp = client.get("/embed/quellen-zahl").headers["content-security-policy"]
    assert expected in csp and "script-src 'self'" in csp


def test_embed_reicht_einbettungsoptionen_durch(client):
    """Schlanke Einbettung im iframe: kopf/fuss/filter/rahmen/ansicht/hintergrund/farbe erreichen das Element."""
    r = client.get("/embed/quellen-kacheln", params={
        "kopf": "aus", "fuss": "aus", "filter": "aus", "rahmen": "aus", "ansicht": "liste",
        "hintergrund": "#ffffff", "farbe": "#1a73e8"})
    assert r.status_code == 200
    for k, v in (("kopf", "aus"), ("fuss", "aus"), ("filter", "aus"), ("rahmen", "aus"), ("ansicht", "liste"),
                 ("hintergrund", "#ffffff"), ("farbe", "#1a73e8")):
        assert f'{k}="{v}"' in r.text, k


def test_widgets_doku_nennt_jedes_attribut_mit_wirkungsbereich():
    """Jan: Optionen und Einblendungsparameter gut dokumentieren. Jedes Attribut, das Elemente, App
    oder iframe-Seite verstehen, steht in der Übersichtstabelle von docs/widgets.md."""
    import re
    from pathlib import Path

    import embed
    root = Path(__file__).resolve().parents[2]
    app_ts = (root / "frontend/src/app/app.component.ts").read_text(encoding="utf-8")
    el_ts = (root / "frontend/src/widgets/elements.ts").read_text(encoding="utf-8")
    namen = set(embed.ATTRIBUTE) | set(re.findall(r"@Input\('([a-z-]+)'\)", app_ts))
    namen |= set(re.findall(r"'([a-z-]+)'", el_ts.split("observedAttributes", 1)[1].split("]", 1)[0]))
    doku = (root / "docs/widgets.md").read_text(encoding="utf-8")
    teil = doku.split("### Alle Optionen auf einen Blick", 1)[1].split("\n### ", 1)[0]
    zeilen = {m.group(1) for m in re.finditer(r"^\| `([a-z-]+)`", teil, re.M)}
    assert sorted(namen - zeilen) == []
