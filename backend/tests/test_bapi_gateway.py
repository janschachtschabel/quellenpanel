"""Betrieb mit und ohne b-api: Der Dienst erkennt an der Anfrage selbst, ob sie über den
Dienste-Proxy der b-api kommt (Delegations-Token in Authorization oder im delegationHeader), und
passt sich an. Über die b-api gibt es keine eigene Anmeldung: kein Team-Bereich, keine Stufe 2,
Team-Pfade nicht in der Spec. Das Token wird nie geprüft, gespeichert oder geloggt."""
import logging


import gateway

BAPI = {"Authorization": "Bearer bdt_dGVzdC10b2tlbi1uaWUtbG9nZ2Vu"}


def _req(headers):
    class R:  # minimal stand-in: only .headers is read
        pass
    r = R()
    r.headers = {k.lower(): v for k, v in headers.items()}
    return r


def test_erkennt_delegations_token():
    assert gateway.via_bapi(_req(BAPI)) is True
    assert gateway.via_bapi(_req({})) is False
    assert gateway.via_bapi(_req({"Authorization": "Bearer abc"})) is False       # kein bdt_-Token
    assert gateway.via_bapi(_req({"Authorization": "Basic YTpi"})) is False


def test_erkennt_eigenen_delegation_header(monkeypatch):
    monkeypatch.setenv("B_API_DELEGATION_HEADER", "X-Bapi-Delegation")
    assert gateway.via_bapi(_req({"X-Bapi-Delegation": "bdt_roh"})) is True
    assert gateway.via_bapi(_req({})) is False


def test_ohne_b_api_bleibt_alles_wie_bisher(client, team_pw):
    caps = client.get("/api/capabilities", headers={"X-Team-Password": team_pw}).json()
    assert caps["maxTier"] == 2 and caps["gateway"] == "direkt"


def test_ueber_b_api_keine_stufe_2_und_kein_team_bereich(client, team_pw):
    h = {**BAPI, "X-Team-Password": team_pw}
    caps = client.get("/api/capabilities", headers=h).json()
    assert caps["gateway"] == "b-api"
    assert caps["maxTier"] == 0 and caps["teamAvailable"] is False
    assert client.get("/api/stats/team", headers=h).status_code == 403
    r = client.get("/api/sources", params={"tier": 2, "page_size": 1}, headers=h)
    assert r.status_code == 200
    assert "internal" not in r.json()["items"][0]


def test_ueber_b_api_stufe_1_mit_freigegebenem_header(client, tier1):
    caps = client.get("/api/capabilities", headers={**BAPI, **tier1}).json()
    assert caps["maxTier"] == 1


def test_ohne_anmeldung_anonym_kein_401(client):
    assert client.get("/api/sources", params={"page_size": 1}, headers=BAPI).status_code == 200


def test_spec_ueber_b_api_ohne_team_pfade(client):
    direkt = client.get("/openapi.json").json()["paths"]
    assert "/api/stats/team" in direkt                    # Team-Instanz direkt: volle Spec
    via = client.get("/openapi.json", headers=BAPI).json()["paths"]
    assert "/api/sources" in via
    assert not any(p.startswith("/api/team") or p in ("/api/stats/team", "/api/auth", "/jobs/refresh")
                   for p in via), sorted(via)


def test_token_erscheint_in_keinem_log(client, caplog):
    with caplog.at_level(logging.DEBUG):
        client.get("/api/sources", params={"page_size": 1}, headers=BAPI)
        client.get("/api/sources/gibt-es-nicht", headers=BAPI)
    assert "bdt_" not in caplog.text


def test_ueber_b_api_kein_team_login(client, team_pw):
    r = client.post("/api/auth", headers={**BAPI, "X-Team-Password": team_pw})
    assert r.status_code == 403
    assert "set-cookie" not in r.headers
