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
