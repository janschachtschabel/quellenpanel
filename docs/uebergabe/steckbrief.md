# Steckbrief Quellenpanel

Dienst-ID `quellenpanel`, Version 1.0.0, Stand 27.11.2026. Zeilen nach dem Diensteleitfaden,
Kapitel 6. Status: **erfüllt**, **Abweichung begründet**, **entfällt** (mit Grund) oder **offen**.

| Zeile | Angabe | Status |
|---|---|---|
| **Kurzbeschreibung** | Quellenpanel beschreibt die Quellen eines edu-sharing-Repositorys: als öffentliche Quellenliste mit Widgets (Stufe 0), als Steckbrief für Partner mit Passwort (Stufe 1) und als internes Team-Audit (Stufe 2). Jede Instanz läuft in genau einer Rolle (QE_ROLE = public, partner oder team) und beschreibt hier nur deren Pfade; Health, Readiness und Metriken liegen auf dem internen Port 9090. | erfüllt (gleich `info.description`) |
| **Funktionen** | Laufzeiten je Endpunkt siehe Tabelle unten (alle lesenden Endpunkte unter 25 ms ohne Last). Kosten je Aufruf: nur Betriebskosten (kein Modell, keine kostenpflichtigen Drittdienste). | erfüllt |
| **b-api** | Kein Proxy-Eintrag, keine Delegation, keine Route. Begründung: Der Dienst zeigt öffentliche Webseiten-Daten der Quellen ohne Personenbezug für einen anonymen Lesezugriff, den die b-api nicht anbietet. Zugang regelt der Dienst selbst über getrennte Instanzen je Rolle und Passwörter (`QE_TIER1_PASSWORD`, `QE_TEAM_PASSWORD`, signierte Team-Sitzung). | Abweichung begründet |
| **Ruft selbst die b-api?** | Nein. Ausgehend nur öffentliche, anonyme REST-Aufrufe ans Repository (Suche, Node-Metadaten, Vorschaubilder) und an das Vokabular-Verzeichnis und Partner/Öffentlich an den internen Port des Teams. Keine verifizierte Person nötig. | erfüllt |
| **Abhängigkeiten** | Repository (`QE_REPO_URL`, Standard `redaktion.openeduhub.net`, nur lesend), beim Datenaufbau das Quellen-Vokabular unter `vocabs.openeduhub.de` (aus dem Profil), optional Startdaten unter `QE_SEED_URL`. Partner und Öffentlich hängen von der Team-Instanz ab (Export über Port 9090). Keine Datenbank, keine anderen Dienste. Zeile in der [Kompatibilitätsmatrix](kompatibilitaet.md). | erfüllt |
| **Clusterfähigkeit** | Partner und Öffentlich sind zustandslos und skalieren beliebig. Das Team hält die Daten auf einem RWO-Volume: genau 1 Pod, Strategie `Recreate`, also bei jedem Update ein kurzer Ausfall der internen Team-Ansicht (Partner und Öffentlich liefern weiter den letzten Export). Die Team-Sitzung ist ein signiertes Cookie und übersteht Neustarts. | erfüllt (Recreate begründet) |
| **Updates und CronJobs** | Kein CronJob: Der nächtliche Datenaufbau läuft im Team-Pod (`QE_AUTO_REFRESH_HOUR`, z. B. 3 Uhr), weil nur dieser Pod das RWO-Volume eingebunden hat; dieselbe Sperre wie der Knopf „Daten aktualisieren“. Laufzeit: Neuaufbau aus vorhandenen Daten 0,8 s; der Live-Abruf aus dem Repository ist noch im Cluster zu messen (in der Messumgebung gesperrt), Metrik `quellenpanel_rebuild_duration_seconds`. Überwachung: Alarme `QuellenpanelRebuildStale` (Daten älter als 26 h), `QuellenpanelNoData`, `QuellenpanelExportFetchFailing`. Partner/Öffentlich gleichen ihren Export alle `QE_EXPORT_POLL_MINUTES` (10) per ETag ab. | erfüllt (Laufzeit Live-Abruf offen) |
| **Ressourcen** | Gemessen ([messung.md](../messung.md)): Speicher fest, CPU elastisch, höchstens 1 Kern je Pod. Team request 100m / 448Mi, limit 1 / 1Gi; Partner 50m / 192Mi, limit 1 / 288Mi; Öffentlich 50m / 96Mi, limit 1 / 160Mi. Team-Limit über Spitze + 30 %, weil der Live-Abruf noch nicht gemessen ist; Storage Team 2 Gi. | Abweichung begründet |
| **Image-Größe** | 64 MB komprimiert (270 MB entpackt). Keine Modelle, keine Daten im Image. | erfüllt |
| **Ansprechperson** | Jan Schachtschabel. Vertretung: offen, wird vor der Übergabe eingetragen. | teilweise (Vertretung offen) |

## Funktionen: Laufzeit je Endpunkt

Gemessen mit [`deploy/messung/last.py`](../../deploy/messung/last.py) gegen das Image, 3 558
Quellen. „Ohne Last“ = 1 Client, „Last“ = 20 parallele Clients auf einem Pod (dann ist der eine
Kern voll und die Zeit ist vor allem Wartezeit). Kosten aller Endpunkte: nur Betriebskosten.

| Endpunkt | Rolle | ohne Last P50 / P90 | Last P50 / P90 |
|---|---|---|---|
| `GET /api/capabilities` | alle | 1 / 1 ms | 40 / 54 ms |
| `GET /api/meta/filters` | alle | 1 / 2 ms | 52 / 67 ms |
| `GET /api/sources` (Seite) | alle | 4 / 5 ms | 67 / 84 ms |
| `GET /api/sources` (Suche) | alle | 6 / 7 ms | 68 / 85 ms |
| `GET /api/sources/{id}` | alle | 1 / 2 ms | 52 / 67 ms |
| `GET /api/stats` | alle | 1 / 2 ms | 53 / 67 ms |
| `GET /api/kennzahl` | alle | 3 / 4 ms | 54 / 70 ms |
| `GET /api/sources/{id}/contents` | alle | Live-Abruf beim Repository, Zeitlimit 20 s, pro Client gedrosselt (429) | – |
| `GET /api/thumb` | alle | Live-Abruf eines Vorschaubilds für den PDF-Export, Zeitlimit 8 s, danach aus dem Zwischenspeicher (`QE_THUMB_CACHE_MB`, 16 MiB), pro Client gedrosselt (429) | – |
| `GET /api/health` | alle | unter 1 ms (Readiness-Probe, ohne Abhängigkeiten) | – |
| `GET /api/stats/team` | team | 14 / 15 ms | 205 / 262 ms |
| `GET /api/export.json` (ab Stufe 1) | team, partner | 23 / 24 ms | 239 / 309 ms |
| `POST /api/admin/reload` | team | 0,8 s (Neuaufbau aus vorhandenen Daten) | – |
| `PUT /api/team/korrekturen/{id}` und Import | team | Sekundenbereich (Merge aus den Roh-Caches) | – |
| `POST /jobs/refresh` | team | Job, antwortet sofort; Status unter `GET /jobs/latest` | – |

Die Team-Werte gelten als angemeldete Person mit Stufe 2 (schwerste Abfragen). Kein Endpunkt
antwortet synchron länger als 30 s; der Live-Abruf läuft als Job.

Fehler kommen immer als `{"error", "message", "status", "trace_id"}`. Wenn ein späterer Versuch
helfen kann (503 ohne Daten, 429, 502 bei Netz- oder 5xx-Fehlern des Repositorys), stehen
`Retry-After` und `retryAfter` dabei; ein 4xx des Repositorys wird zu 502 ohne Wiederholungshinweis.
