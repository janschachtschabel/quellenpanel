"""Team-Routen für Korrekturen und Crawler-Tabelle (Etappe 4)."""
import json

import pytest

import refresh

NODE = "27c77a87-8250-4a26-9d95-3b24cd162539"
OCTET = {"Content-Type": "application/octet-stream"}


@pytest.fixture
def team(client, team_pw, tmp_path, monkeypatch):
    assert client.post("/api/auth", headers={"X-Team-Password": team_pw}).status_code == 200
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    yield client
    monkeypatch.undo()
    import enduser
    enduser.reload_supplements()


def _version(c):
    return c.get("/api/team/korrekturen").json()["version"]


@pytest.mark.parametrize("role", ["partner", "public"])
def test_routes_do_not_exist_outside_team(client, monkeypatch, role):
    monkeypatch.setenv("QE_ROLE", role)
    assert client.get("/api/team/korrekturen").status_code == 404
    assert client.post("/api/team/crawler/vorschau", content=b"x", headers=OCTET).status_code == 404


def test_login_required(client):
    assert client.get("/api/team/korrekturen").status_code == 403
    assert client.get("/api/team/korrekturen.csv").status_code == 403


def test_crud_roundtrip(team):
    stand = team.get("/api/team/korrekturen").json()
    n = len(stand["eintraege"])
    r = team.post("/api/team/korrekturen", json={
        "korrektur": {"typ": "node", "schluessel": NODE, "aktion": "whitelist"}, "wer": "JS",
        "version": stand["version"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["eintraege"]) == n + 1 and body["anwenden"]["wirktBeimNaechstenAufbau"] is True
    i = body["eintraege"][-1]["id"]
    r = team.put(f"/api/team/korrekturen/{i}", json={
        "korrektur": {"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "wer": "JS",
        "version": body["version"]})
    assert r.status_code == 200 and r.json()["eintraege"][i]["aktion"] == "blacklist"
    r = team.delete(f"/api/team/korrekturen/{i}", params={"wer": "JS", "version": r.json()["version"]})
    assert r.status_code == 200 and len(r.json()["eintraege"]) == n
    vorgaenge = [e["vorgang"] for e in team.get("/api/team/korrekturen/verlauf").json()]
    assert vorgaenge[:3] == ["loeschen", "aendern", "anlegen"]


def test_invalid_row_is_422(team):
    r = team.post("/api/team/korrekturen", json={
        "korrektur": {"typ": "node", "schluessel": "x", "aktion": "blacklist"}, "wer": "JS",
        "version": _version(team)})
    assert r.status_code == 422 and "Node-ID" in r.json()["message"]


def test_wrong_version_is_409(team):
    r = team.post("/api/team/korrekturen", json={
        "korrektur": {"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "wer": "JS",
        "version": "0" * 16})
    assert r.status_code == 409


def test_running_rebuild_is_409(team, monkeypatch):
    monkeypatch.setitem(refresh._JOB, "status", "running")
    r = team.post("/api/team/korrekturen", json={
        "korrektur": {"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "wer": "JS",
        "version": _version(team)})
    assert r.status_code == 409


def test_foreign_origin_is_403_same_origin_ok(team):
    body = {"korrektur": {"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "wer": "JS"}
    r = team.post("/api/team/korrekturen", json={**body, "version": _version(team)},
                  headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    r = team.post("/api/team/korrekturen", json={**body, "version": _version(team)},
                  headers={"Origin": "http://testserver"})
    assert r.status_code == 200


def test_csv_download(team):
    r = team.get("/api/team/korrekturen.csv")
    assert r.status_code == 200
    assert r.content.startswith(b"\xef\xbb\xbfTyp;Schl")
    assert "attachment" in r.headers["content-disposition"]


def test_import_preview_and_apply(team):
    data = ("Typ;Schlüssel;Aktion\nnode;%s;whitelist\nnode;kaputt;blacklist\n" % NODE).encode()
    r = team.post("/api/team/korrekturen/import/vorschau", params={"format": "csv", "modus": "ergaenzen"},
                  content=data, headers=OCTET)
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["zuordnung"]["schluessel"] == "Schlüssel"
    assert v["anzahl"]["fehlerhaft"] == 1 and v["vorschau"]["fehlerhaft"][0]["zeile"] == 3
    assert v["anzahl"]["neu"] + v["anzahl"]["geaendert"] == 1
    assert "ergebnis" not in v["vorschau"]
    r = team.post("/api/team/korrekturen/import",
                  params={"format": "csv", "modus": "ergaenzen", "wer": "JS", "version": _version(team)},
                  content=data, headers=OCTET)
    assert r.status_code == 200, r.text
    assert any(e["schluessel"] == NODE and e["aktion"] == "whitelist" for e in r.json()["eintraege"])


def test_import_manual_mapping_header(team):
    data = ("A;B\n%s;blacklist\n" % NODE).encode()
    r = team.post("/api/team/korrekturen/import/vorschau", params={"format": "csv", "modus": "ersetzen"},
                  content=data, headers={**OCTET, "X-Zuordnung": json.dumps({"schluessel": "A", "aktion": "B"})})
    assert r.status_code == 200, r.text
    assert r.json()["anzahl"]["entfallen"] > 0


def test_import_unreadable_is_422(team):
    r = team.post("/api/team/korrekturen/import/vorschau", params={"format": "json", "modus": "ergaenzen"},
                  content=b"{kaputt", headers=OCTET)
    assert r.status_code == 422


def test_crawler_preview_missing_column(team):
    r = team.post("/api/team/crawler/vorschau", content=b"Titel;Spider\nA;x\n", headers=OCTET)
    assert r.status_code == 200 and r.json()["ok"] is False


def test_upload_limits(team):
    big = b"Titel;Crawler (Spider);Quelldatensatz (Prod)\n" + b"A;s;\n" * 400_000       # ~2 MB
    assert team.post("/api/team/crawler/vorschau", content=big, headers=OCTET).status_code == 200
    huge = b"x" * 6_000_000
    assert team.post("/api/team/crawler/vorschau", content=huge, headers=OCTET).status_code == 413


def test_public_openapi_has_no_team_paths(client, monkeypatch):
    import app as app_module
    monkeypatch.setenv("QE_ROLE", "public")
    app_module._openapi_cache.clear()
    paths = client.get("/openapi.json").json()["paths"]
    app_module._openapi_cache.clear()
    assert not [p for p in paths if p.startswith("/api/team/")]


def test_team_routes_work_while_data_builds(team, monkeypatch):
    """Erststart ohne Daten: Das Team kann trotzdem Korrekturen und die Crawler-Tabelle pflegen."""
    import app as app_module
    monkeypatch.setitem(app_module._DATA, "records", [])
    assert team.get("/api/sources").status_code == 503
    assert team.get("/api/team/korrekturen").status_code == 200
