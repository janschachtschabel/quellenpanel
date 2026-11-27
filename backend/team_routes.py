"""team_routes.py — the team's correction and crawler-table management (/api/team/…).

Only on the team instance (404 elsewhere), only with team login (403). Writes additionally:
  * require an Origin that is this host or a trusted QE_ALLOWED_ORIGINS entry (or none, as sent by
    non-browser clients) — CSRF guard for the cookie session,
  * are refused with 409 while a data rebuild runs or when `version` is stale.
Uploads arrive as the raw request body (application/octet-stream), up to 5 MB.
"""
from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool

import anwenden
import config
import crawler_upload
import korrektur_import
import korrektur_store
import refresh
import tiers

MAX_UPLOAD_BYTES = 5_000_000
_LISTE_MAX = 200


def require_team_role() -> None:
    """Team-only routes do not exist on partner/public instances (404, not 403)."""
    if config.role() != "team":
        raise HTTPException(404, "Not Found")


def _team(team: bool = Depends(tiers.is_team)) -> None:
    if not team:
        raise HTTPException(403, "Team-Login erforderlich.")


def herkunft_pruefen(request: Request) -> None:
    """Team writes only from the own site or an allowed origin (the cookie may be SameSite=None)."""
    origin = request.headers.get("origin")
    if origin and origin not in config.ALLOWED_ORIGINS \
            and urlparse(origin).netloc != request.headers.get("host", ""):
        raise HTTPException(403, "Fremde Herkunft (Origin) nicht erlaubt.")


def _schreiben_erlaubt(request: Request) -> None:
    herkunft_pruefen(request)
    if refresh.status().get("status") == "running":
        raise HTTPException(409, "Die Daten werden gerade aktualisiert. Bitte danach erneut versuchen.")


router = APIRouter(prefix="/api/team", dependencies=[Depends(require_team_role), Depends(_team)])
_WRITE = [Depends(_schreiben_erlaubt)]
SCHREIBEN = _WRITE                     # also for the team POSTs outside /api/team (app.py)


def _fehler(fn, *args):
    try:
        return fn(*args)
    except korrektur_store.VersionKonflikt as e:
        raise HTTPException(409, str(e)) from e
    except (korrektur_store.UngueltigeKorrektur, korrektur_import.ImportFehler,
            crawler_upload.UploadFehler) as e:
        raise HTTPException(422, str(e)) from e


def _mit_anwenden(stand: dict) -> dict:
    return {**stand, "anwenden": anwenden.sicher()}


async def _body(request: Request) -> bytes:
    data = await request.body()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Datei zu groß (höchstens 5 MB).")
    return data


def _zuordnung(request: Request, spalten: list[str]) -> dict:
    raw = request.headers.get("x-zuordnung")
    auto = korrektur_import.auto_zuordnung(spalten)
    if not raw:
        return auto
    try:
        manuell = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(422, "X-Zuordnung ist kein gültiges JSON.") from e
    if not isinstance(manuell, dict):
        raise HTTPException(422, "X-Zuordnung muss ein Objekt sein.")
    out = {}
    for feld in korrektur_import.ZIELFELDER:
        v = manuell.get(feld, auto.get(feld))
        out[feld] = v if v in spalten else None
    return out


def _vorschau(data: bytes, format: str, modus: str, request: Request, wer: str) -> tuple[dict, dict, list]:
    spalten, zeilen = korrektur_import.lesen_datei(data, format)
    zuordnung = _zuordnung(request, spalten)
    v = korrektur_import.vorschau(zeilen, zuordnung, korrektur_store.bestand(), modus, wer)
    return {"spalten": spalten, "zuordnung": zuordnung}, v, zeilen


def _k(k) -> dict:
    return {"typ": k.typ, "schluessel": k.schluessel, "aktion": k.aktion, "wert": k.wert,
            "kommentar": k.kommentar}


@router.get("/korrekturen")
def korrekturen_lesen():
    return korrektur_store.lesen()


@router.post("/korrekturen", dependencies=_WRITE)
def korrektur_anlegen(korrektur: dict = Body(...), wer: str = Body(...), version: str = Body(...)):
    return _mit_anwenden(_fehler(korrektur_store.anlegen, korrektur, wer, version))


@router.put("/korrekturen/{id_}", dependencies=_WRITE)
def korrektur_aendern(id_: int, korrektur: dict = Body(...), wer: str = Body(...),
                      version: str = Body(...)):
    return _mit_anwenden(_fehler(korrektur_store.aendern, id_, korrektur, wer, version))


@router.delete("/korrekturen/{id_}", dependencies=_WRITE)
def korrektur_loeschen(id_: int, wer: str = Query(...), version: str = Query(...)):
    return _mit_anwenden(_fehler(korrektur_store.loeschen, id_, wer, version))


@router.get("/korrekturen.csv")
def korrekturen_csv():
    path = config.korrekturen_csv_path()
    data = path.read_bytes() if path else b""
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="korrekturen.csv"'})


@router.get("/korrekturen/verlauf")
def korrekturen_verlauf(limit: int = Query(200, ge=1, le=5000)):
    return korrektur_store.verlauf(limit)


@router.post("/korrekturen/import/vorschau", dependencies=_WRITE)
async def import_vorschau(request: Request, format: str = Query(...), modus: str = Query("ergaenzen")):
    data = await _body(request)
    kopf, v, _ = await run_in_threadpool(_fehler, _vorschau, data, format, modus, request, "")
    return {**kopf,
            "anzahl": {"neu": len(v["neu"]), "geaendert": len(v["geaendert"]),
                       "unveraendert": v["unveraendert"], "fehlerhaft": len(v["fehlerhaft"]),
                       "entfallen": len(v["entfallen"]), "ergebnis": len(v["ergebnis"])},
            "vorschau": {"neu": [_k(k) for k in v["neu"][:_LISTE_MAX]],
                         "geaendert": [{"alt": _k(g["alt"]), "neu": _k(g["neu"])}
                                       for g in v["geaendert"][:_LISTE_MAX]],
                         "fehlerhaft": v["fehlerhaft"][:_LISTE_MAX],
                         "entfallen": [_k(k) for k in v["entfallen"][:_LISTE_MAX]]}}


@router.post("/korrekturen/import", dependencies=_WRITE)
async def import_uebernehmen(request: Request, format: str = Query(...), modus: str = Query("ergaenzen"),
                             wer: str = Query(...), version: str = Query(...)):
    data = await _body(request)

    def run():
        _, v, _ = _vorschau(data, format, modus, request, korrektur_store._wer(wer))
        stand = korrektur_store.ersetzen_alle(v["ergebnis"], wer, version, f"import_{modus}",
                                              sicherung=modus == "ersetzen",
                                              roh_behalten=modus == "ergaenzen")
        return _mit_anwenden(stand)
    return await run_in_threadpool(_fehler, run)


@router.post("/crawler/vorschau", dependencies=_WRITE)
async def crawler_vorschau(request: Request):
    data = await _body(request)
    return await run_in_threadpool(_fehler, crawler_upload.pruefen, data)


@router.post("/crawler", dependencies=_WRITE)
async def crawler_ersetzen(request: Request, wer: str = Query(...)):
    data = await _body(request)
    return await run_in_threadpool(_fehler, crawler_upload.ersetzen, data, wer)
