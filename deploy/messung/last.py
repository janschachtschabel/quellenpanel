#!/usr/bin/env python3
"""Lastskript für die Ressourcenmessung (nur Standardbibliothek).

Ruft die lesenden Endpunkte einer Instanz nebenläufig ab und gibt je Endpunkt Anzahl, P50 und P90
der Antwortzeit aus. Der Live-Abruf /api/sources/{id}/contents fehlt absichtlich: Er fragt das
Repository an und ist pro Client gedrosselt, er misst also nicht diesen Dienst.

    python deploy/messung/last.py http://127.0.0.1:8080 --clients 20 --sekunden 60
    python deploy/messung/last.py http://127.0.0.1:8082 --team-pw "$QE_TEAM_PASSWORD"   # Stufe 2

Abbruch mit Exit-Code 2, wenn die Vorprüfung nicht für jeden Endpunkt 200 liefert (z. B. 503, weil
die Instanz noch keine Daten hat: dann misst man nur Fehlerseiten). Exit-Code 1, wenn unter Last
eine Antwort nicht 200 war.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


def endpunkte(basis: str, erste_id: str | None, team: bool = False) -> list[str]:
    pfade = [
        "/api/capabilities",
        "/api/meta/filters",
        "/api/sources?page=1&page_size=24",
        "/api/sources?page=2&page_size=24&q=mathe",
        "/api/stats",
        "/api/kennzahl",
    ]
    if team:
        pfade += ["/api/stats/team", "/api/export.json"]
    if erste_id:
        pfade.append("/api/sources/" + urllib.parse.quote(erste_id, safe=""))
    if team:                                 # Stufe 2 anfordern (gewährt nur mit gültiger Sitzung)
        pfade = [p + ("&" if "?" in p else "?") + "tier=2" for p in pfade]
    return [basis + p for p in pfade]


_KOPF: dict[str, str] = {}


def anmelden(basis: str, passwort: str) -> bool:
    """Team-Login (Stufe 2): merkt sich das Sitzungs-Cookie für alle weiteren Abrufe."""
    req = urllib.request.Request(basis + "/api/auth", method="POST", data=b"",
                                 headers={"x-team-password": passwort})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            cookie = r.headers.get("set-cookie", "").split(";", 1)[0]
    except OSError:
        return False
    if cookie:
        _KOPF["cookie"] = cookie
    return bool(cookie)


def abrufen(url: str, timeout: float = 30) -> tuple[int, float, bytes]:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_KOPF), timeout=timeout) as r:
            body = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        body, code = b"", e.code
    except OSError:
        body, code = b"", 0
    return code, time.perf_counter() - start, body


def quantil(werte: list[float], q: float) -> float:
    if len(werte) < 2:
        return werte[0] if werte else 0.0
    return statistics.quantiles(werte, n=100, method="inclusive")[int(q * 100) - 1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("basis")
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--sekunden", type=float, default=60)
    ap.add_argument("--team-pw", help="vorher als Team anmelden (Stufe 2, nur Team-Instanz)")
    ap.add_argument("--json", help="Ergebnis zusätzlich als JSON in diese Datei")
    a = ap.parse_args(argv)
    basis = a.basis.rstrip("/")
    _KOPF.clear()
    if a.team_pw and not anmelden(basis, a.team_pw):
        print("Team-Login fehlgeschlagen. Abbruch.", file=sys.stderr)
        return 2

    code, _, body = abrufen(basis + "/api/sources?page=1&page_size=1")
    if code != 200:
        print(f"Vorprüfung: /api/sources antwortet {code}, nicht 200. Abbruch.", file=sys.stderr)
        return 2
    items = json.loads(body).get("items") or []
    urls = endpunkte(basis, items[0]["id"] if items else None, team=bool(a.team_pw))
    for u in urls:
        code, _, _ = abrufen(u)
        if code != 200:
            print(f"Vorprüfung: {u} antwortet {code}, nicht 200. Abbruch.", file=sys.stderr)
            return 2

    zeiten: dict[str, list[float]] = {u: [] for u in urls}
    fehler: dict[str, int] = {u: 0 for u in urls}
    sperre = threading.Lock()
    ende = time.monotonic() + a.sekunden

    def arbeiter(n: int) -> None:
        i = n
        while time.monotonic() < ende:
            u = urls[i % len(urls)]
            i += 1
            code, dauer, _ = abrufen(u)
            with sperre:
                if code == 200:
                    zeiten[u].append(dauer)
                else:
                    fehler[u] += 1

    threads = [threading.Thread(target=arbeiter, args=(n,)) for n in range(a.clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ergebnis = []
    print(f"{'Endpunkt':60} {'n':>6} {'P50 ms':>8} {'P90 ms':>8} {'Fehler':>6}")
    for u in urls:
        z = zeiten[u]
        zeile = {"pfad": u[len(basis):], "n": len(z), "p50_ms": round(quantil(z, .5) * 1000),
                 "p90_ms": round(quantil(z, .9) * 1000), "fehler": fehler[u]}
        ergebnis.append(zeile)
        print(f"{zeile['pfad'][:60]:60} {zeile['n']:>6} {zeile['p50_ms']:>8} {zeile['p90_ms']:>8} {zeile['fehler']:>6}")
    gesamt = sum(len(z) for z in zeiten.values())
    print(f"Durchsatz: {gesamt / a.sekunden:.1f} Anfragen/s bei {a.clients} Clients")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"clients": a.clients, "sekunden": a.sekunden, "endpunkte": ergebnis}, fh, indent=2)
    return 1 if any(fehler.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
