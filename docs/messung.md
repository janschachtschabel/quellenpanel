# Ressourcenmessung

Stand 27.11.2026, Version 1.0.0 (Image aus dem `Dockerfile` des Repos, Compose aus
`deploy/docker-compose.yml` mit drei Rollen, Datenbestand 3 558 Quellen). Gemessen mit
`docker stats` (Abtastung etwa alle 2 s) auf einem Rechner mit 4 Kernen. Die Last erzeugt
`deploy/messung/last.py` auf demselben Rechner.

## Ablauf

1. **Leerlauf:** alle drei Rollen bereit (`/api/sources` antwortet 200), 60 s ohne Anfragen.
2. **Warm:** jeder Endpunkt einmal abgerufen (1 Client, 8 s; beim Team zusätzlich als Team mit
   Stufe 2), danach 15 s Ruhe.
3. **Spitze:** `last.py` mit 20 parallelen Clients für 60 s je Rolle, nacheinander, damit sich die
   Rollen die CPU nicht teilen. Beim Team als angemeldete Person mit Stufe 2, also mit den
   schwersten Abfragen (Teamstatistik, Export).
4. **Datenaufbau Team:** fünfmal `POST /api/admin/reload` (Daten neu laden, Exporte neu bauen),
   danach sechs Neuaufbauten im Abstand von 30 s, während Partner und Öffentlich je 10 Clients
   für 180 s bedienen und ihre Exporte jede Minute abgleichen.

Wiederholen:

```bash
python deploy/messung/last.py http://127.0.0.1:8080 --clients 20 --sekunden 60          # öffentlich
python deploy/messung/last.py http://127.0.0.1:8081 --clients 20 --sekunden 60          # Partner
python deploy/messung/last.py http://127.0.0.1:8082 --clients 20 --sekunden 60 \
  --team-pw "$QE_TEAM_PASSWORD"                                                          # Team, Stufe 2
```

Das Skript bricht vorher ab, wenn ein Endpunkt nicht 200 liefert (z. B. 503, solange eine Instanz
noch keine Daten hat), damit nie Fehlerseiten gemessen werden.

## Ergebnisse

| Rolle | Leerlauf | Warm | Spitze (Last) | Spitze (Datenaufbau) | CPU unter Last |
|---|---|---|---|---|---|
| team | 164 MiB, 0,2 % | 167 MiB | 349 MiB | 422 MiB | 1 Kern (103 %) |
| partner | 161 MiB, 0,2 % | 161 MiB | 166 MiB | 161 MiB | 1 Kern (106 %) |
| public | 72 MiB, 0,2 % | 72 MiB | 78 MiB | 72 MiB | 1 Kern (111 %) |

- **Speicher ist fest, CPU ist elastisch.** Der Datenbestand liegt im Speicher und wächst nicht
  mit der Zahl der Anfragen (öffentlich: 72 → 78 MiB unter Last). Die CPU folgt dem Verkehr und
  ist im Leerlauf nahe null.
- **Ein Prozess nutzt höchstens einen Kern** (ein Python-Prozess). Mehr CPU-Limit bringt nichts;
  mehr Durchsatz kommt über weitere Replikate (Partner und Öffentlich sind zustandslos, siehe
  `docs/betrieb.md`).
- **Team nach dem Neuaufbau:** Der Speicher bleibt nach einem Neuaufbau bei etwa 415 MiB stehen
  (Python gibt den Heap nicht sofort zurück). Deshalb liegt die Anforderung (request) beim Team
  über dem Leerlaufwert.
- **Partner hält zwei Exporte** (Stufe 0 und 1), deshalb mehr Grundspeicher als Öffentlich.
  Beim Abgleich eines geänderten Exports liegt kurz eine zweite Kopie im Speicher: Stufe 1 hat
  10 MB als JSON, zwei geparste Kopien kosten zusammen 107 MiB, eine also etwa 55 MiB. Im Test
  änderte sich der Export nicht, deshalb ist dieser Zuschlag gerechnet, nicht gemessen.
- **Live-Abruf nicht gemessen:** Der vollständige Abruf aus dem Repository (`/jobs/refresh`,
  nächtlich über `QE_AUTO_REFRESH_HOUR`) war hier nicht möglich, weil die Netzrichtlinie der
  Messumgebung das Repository sperrt. Gemessen ist der Neuaufbau aus vorhandenen Daten
  (0,8 s je Lauf, Spitze 422 MiB). Beim Team liegt deshalb mehr Reserve im Limit; vor der
  Produktivnahme einmal im Cluster nachmessen
  (`kubectl top pod -l app.kubernetes.io/instance=quellenpanel-team` während eines Abrufs).

### Antwortzeiten unter Last (20 Clients, 60 s)

| Endpunkt | öffentlich P50 / P90 | Partner P50 / P90 | Team Stufe 2 P50 / P90 |
|---|---|---|---|
| `/api/capabilities` | 40 / 54 ms | 39 / 52 ms | 124 / 176 ms |
| `/api/meta/filters` | 52 / 67 ms | 51 / 65 ms | 156 / 213 ms |
| `/api/sources` (Seite 1) | 67 / 84 ms | 67 / 84 ms | 200 / 257 ms |
| `/api/sources` (Suche, Seite 2) | 68 / 85 ms | 70 / 92 ms | 200 / 260 ms |
| `/api/stats` | 53 / 67 ms | 52 / 70 ms | 173 / 226 ms |
| `/api/kennzahl` | 54 / 70 ms | 54 / 71 ms | 150 / 206 ms |
| `/api/sources/{id}` | 52 / 67 ms | 51 / 67 ms | 159 / 220 ms |
| `/api/stats/team` | – | – | 205 / 262 ms |
| `/api/export.json` | – | – | 239 / 309 ms |
| Durchsatz | 354 Anfragen/s | 355 Anfragen/s | 109 Anfragen/s |

Ohne Last (1 Client) liegen alle Endpunkte unter 25 ms; die Zeiten oben sind vor allem Wartezeit
in der Warteschlange eines voll ausgelasteten Kerns. Der Live-Abruf
`/api/sources/{id}/contents` fehlt absichtlich: Er fragt das Repository an, ist pro Client
gedrosselt und misst damit nicht diesen Dienst.

### Image

| | Größe |
|---|---|
| entpackt (`docker image inspect`) | 270 MB |
| komprimiert (`docker save \| gzip`) | 64 MB |

Das Image enthält keine Daten; das Team baut sie beim ersten Start im Volume `/data` auf
(5,8 MB Startdaten, Exporte 18 MB).

## Empfehlung

Requests und Limits je Rolle, so eingetragen in `deploy/helm/quellenpanel/values-<rolle>.yaml`.
Regel: Limit ≈ Spitze + 20–30 %, Request ≈ warmer Wert.

| Rolle | requests.cpu | requests.memory | limits.cpu | limits.memory |
|---|---|---|---|---|
| team | `100m` | `448Mi` | `1` | `1Gi` |
| partner | `50m` | `192Mi` | `1` | `288Mi` |
| public | `50m` | `96Mi` | `1` | `160Mi` |

Begründung:

- **CPU:** Leerlauf nahe null, deshalb kleine Requests. Limit 1 Kern, weil ein Prozess nicht
  mehr nutzt; ein kleineres Limit würde unter Last drosseln.
- **team:** gemessene Spitze 422 MiB. Das Limit 1 Gi lässt mehr als die üblichen 20–30 % Reserve,
  weil der Live-Abruf nicht gemessen werden konnte (siehe oben). Nach einer Messung im Cluster auf
  Spitze + 25 % senken.
- **partner:** Spitze 166 MiB plus eine zweite Exportkopie beim Abgleich (etwa 55 MiB) = 221 MiB,
  plus 25 % ≈ 288 MiB.
- **public:** Spitze 78 MiB plus eine zweite Kopie des Exports Stufe 0 (7,5 MB JSON, etwa 40 MiB)
  = 118 MiB, plus 25 %, aufgerundet auf 160 MiB.
- Die Compose-Datei setzt keine Limits (Einzelrechner); wer sie braucht, übernimmt die Werte oben
  als `mem_limit` und `cpus`.
