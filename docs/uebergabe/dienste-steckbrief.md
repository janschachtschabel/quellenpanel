# Dienste-Steckbrief Quellenpanel

Kompakt nach der Vorlage der Dienste-Steckbriefe. Ausführlich: [steckbrief.md](steckbrief.md),
Checkliste: [README.md](README.md).

| Stammdaten | |
|---|---|
| **Service** | Quellenpanel (Dienst-ID `quellenpanel`) |
| **Funktionalität** | Zeigt die Quellen des Repositorys (WLO): öffentliche Quellenliste mit Widgets, Steckbrief für Partner, internes Audit mit Korrekturen fürs Team |
| **Stabile Version** | `vorhanden` (1.0.0, Tag `v1.0.0`) |
| **Technischer Owner** | Jan Schachtschabel |
| **Jira** | `nicht vorhanden` |
| **Deployment Status** | `In Klärung` (Vorgängerversion läuft produktiv; 1.0.0 noch nicht im Cluster) |
| **Repository** | `vorhanden` ([GitHub](https://github.com/janschachtschabel/quellenpanel)) |
| **OpenAPI Spec** | `vorhanden` (`GET /openapi.json`, je Instanz nur deren Pfade) |
| **Pipeline und Git-Tags** | `vorhanden` (Tags `v<version>`, `.gitlab-ci.yml` und `.github/workflows/` im Repo) |
| **Endpunkte** | `vorhanden` (öffentlich: `/api/sources`, `/api/sources/{id}`, `/api/kennzahl`, `/api/stats`, `/widgets/…`, `/embed/…`; Infrastruktur: `/health`, `/ready`, `/metrics`) |
| **Endpunkte auf zwei Ports** | `vorhanden` (8080 API und Oberfläche, 9090 Infrastruktur und Exporte, nur im Cluster) |
| **Header / Content-Types** | `geprüft` (`x-tier1-password`, `x-team-password`, B3; JSON, CSV, Markdown) |
| **Asynchrone Job-Endpunkte** | `geprüft` (`POST /jobs/refresh`, Status `GET /jobs/latest`) |
| **Timeout für Requests** | `geprüft` (Live-Abruf 20 s, Vorschaubild 8 s; kein Endpunkt synchron über 30 s) |
| **Readiness Status** | `bereit zur Übergabe` (offen: Vertretung, wer Updates anstößt) |

| Architektur | |
|---|---|
| **Überblick** | FastAPI-Backend und Angular-22-Oberfläche in einem Image; drei Instanzen: team (Stufe 2), partner (Stufe 1), public (Stufe 0) |
| **Horizontale Skalierbarkeit** | `geprüft` (partner und public ja; team 1 Pod wegen RWO-Volume) |
| **Integriert in B-API** | `geprüft` (nein, begründet: anonymer Lesezugriff auf öffentliche Daten) |
| **Schreibt Suggestions** | `geprüft` (nein) |
| **Nutzt Routing** | `geprüft` (nein, kein LLM) |
| **Nutzt API Keys** | `geprüft` (nein, Passwörter je Instanz) |
| **Repo über B-API** | `geprüft` (nein, öffentliche REST-API des Repositorys, nur lesend) |
| **Benötigte Dienste** | `geprüft` (keine; liest Repository und Vokabular `vocabs.openeduhub.de`) |

| Deployment und Infrastruktur | |
|---|---|
| **HELM** | `vorhanden` (`deploy/helm/quellenpanel`, eine Release je Rolle) |
| **Docker-Files** | `vorhanden` (`Dockerfile`, `deploy/docker-compose.yml`, `docker-compose.yml` für Server mit Traefik) |
| **Abschaltbare Komponenten** | `geprüft` (ja: partner und public einzeln; NetworkPolicy, ServiceMonitor, Alarme per Value) |
| **Datenbank** | `geprüft` (nein) |
| **Große Daten** | `geprüft` (nein; Team-Volume 2 Gi, rund 25 MB belegt) |

| Security und Konfiguration | |
|---|---|
| **Authentifizierung** | `geprüft` (Stufe 0 offen; Stufe 1 Passwort auf partner; Stufe 2 Team-Passwort mit signierter Sitzung, Team-Host hinter VPN/SSO) |
| **Network Policy** | `vorhanden` (ein- und ausgehend, in allen drei Rollen an) |
| **ENV Variablen** | `vorhanden` (Tabelle in `docs/betrieb.md`) |
| **Benötigte Secrets** | `vorhanden` (`QE_TEAM_PASSWORD`, `QE_SESSION_SECRET`, `QE_TIER1_PASSWORD`) |

| Monitoring und Betrieb | |
|---|---|
| **Prometheus** | `vorhanden` (`/metrics` auf 9090, ServiceMonitor) |
| **Alarmregeln** | `vorhanden` (RebuildStale, NoData, High5xx, ExportFetchFailing; mit `promtool` getestet) |
| **B3-Tracing** | `vorhanden` (gelesen, an das Repository weitergegeben, `trace_id` in jeder Logzeile) |

| Ressourcen und Kosten | |
|---|---|
| **CPU, RAM und Storage** | `vorhanden` (gemessen: team 100m/448Mi, Limit 1/1Gi, PVC 2 Gi; partner 50m/192Mi, Limit 1/288Mi; public 50m/96Mi, Limit 1/160Mi) |
| **Kostenschätzung** | `vorhanden` (nur Betriebskosten: zusammen rund 0,25 CPU und 0,8 GiB angefordert (public mit 2 Replikas) plus 2 Gi Volume; keine Modelle, keine kostenpflichtigen Drittdienste) |
