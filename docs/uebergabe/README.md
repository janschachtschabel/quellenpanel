# Übergabepaket Quellenpanel (Version 1.0.0)

Checkliste nach dem Diensteleitfaden, Kapitel 6. Jeder Punkt verweist auf die Stelle, die ihn
beantwortet. Offen sind die Ansprechperson mit Vertretung und wer Updates anstößt. Zwei Schritte
liegen beim Betrieb (Spalte „Stand“: **Schritt für den Betrieb**).

| Punkt | Stand | Wo |
|---|---|---|
| Repo und CI | erfüllt: GitHub `janschachtschabel/quellenpanel`. GitHub-CI prüft Lint, Tests, Design-Regeln, `pip-audit`/`npm audit`, `helm lint --strict`, `kubeconform`, Versionsgleichheit und baut bei einem Tag `v1.0.0` das Image `1.0.0` und `1.0` für Docker Hub (kein `latest`). Die GitLab-Pipeline baut bei demselben Tag das Image `1.0.0` (und `v1.0.0`) für `docker.edu-sharing.com` und das Chart `quellenpanel` 1.0.0; diese Registry ist der Standard im Chart (Tag = `appVersion`). Wer Docker Hub nutzt, setzt `global.image.registry`/`repository`. Die Prüfungen laufen nur in der GitHub-CI. | [ci.yml](../../.github/workflows/ci.yml), [docker-publish.yml](../../.github/workflows/docker-publish.yml), [.gitlab-ci.yml](../../.gitlab-ci.yml) |
| OpenAPI, Anzeigename, Beschreibung | erfüllt: `/openapi.json` je Instanz, nur Pfade der eigenen Rolle. Anzeigename „Quellenpanel“, Beschreibung = `info.description` (Kurzbeschreibung im Steckbrief). | [steckbrief.md](steckbrief.md) |
| Ports (öffentlich / intern) | erfüllt: 8080 öffentlich bei Partner und Öffentlich (API, Oberfläche, Widgets), 9090 nur im Cluster (`/health`, `/ready`, `/metrics`, Exporte des Teams). | [betrieb.md](../betrieb.md#ports-und-probes) |
| Team nur intern | **Schritt für den Betrieb:** Das Chart kann den Team-Ingress nicht selbst abschirmen. Den Ingress der Team-Instanz hinter VPN/SSO legen (z. B. oauth2-proxy-Annotation in `values-team.yaml`). Auf dem Team ist Stufe 1 ohne Passwort offen und der Team-Login nur gedrosselt, deshalb darf der Host nicht aus dem Internet erreichbar sein. `values-team.yaml` schaltet `networkPolicy.enabled` ein, damit Port 9090 (Exporte) nur von Quellenpanel-Pods und dem Monitoring erreichbar ist; die NetworkPolicy setzt ein CNI voraus, das sie durchsetzt. | [values-team.yaml](../../deploy/helm/quellenpanel/values-team.yaml), [betrieb.md](../betrieb.md#rollen-und-zustand) |
| Header, Content-Types, Antwortzeiten, Job-Endpunkte | erfüllt: Anfrage-Header nur `x-tier1-password` (Partner) und `x-team-password` (Team-Login), sonst das Cookie `qe_session`; B3-Header werden gelesen. Antworten JSON, dazu CSV (`/api/export.csv`, `/api/protokoll.csv`, `/api/team/korrekturen.csv`) und Markdown (`/api/protokoll.md`); Uploads als `multipart/form-data` bis 5 MB. Job: `POST /jobs/refresh`, Status `GET /jobs/latest`. Laufzeiten je Endpunkt im Steckbrief. | [steckbrief.md](steckbrief.md#funktionen-laufzeit-je-endpunkt), [widgets.md](../widgets.md) |
| b-api bzw. Auth-Konzept | Abweichung begründet: ohne b-api. Getrennte Instanzen je Zugangsstufe, Passwörter je Instanz, signierte Team-Sitzung (HMAC, `QE_SESSION_SECRET`), interne Daten nie auf Partner oder Öffentlich. | [betrieb.md](../betrieb.md#betrieb-ohne-b-api), [steckbrief.md](steckbrief.md) |
| Prometheus, Metriken, Alarmregeln | erfüllt: `/metrics` auf 9090, Anfrage-, Rebuild-, Datenalter- und Export-Metriken; ServiceMonitor und PrometheusRule im Chart, Regeln mit `promtool` getestet. | [betrieb.md](../betrieb.md#metriken-metrics-prometheus) |
| Log-Format, Dienst-ID, Trace-Header | erfüllt: JSON je Zeile auf stdout, `service: quellenpanel`, eine Zeile je Anfrage mit Routenvorlage, B3 gelesen und weitergegeben, `x-client-trace-id`. | [betrieb.md](../betrieb.md#logs-und-tracing) |
| Zustand, Skalierung, Architektur | erfüllt: Team 1 Pod mit RWO-Volume (`Recreate`), Partner und Öffentlich zustandslos und skalierbar. Architektur siehe unten. | [betrieb.md](../betrieb.md#rollen-und-zustand) |
| Ressourcen gemessen | erfüllt: Leerlauf, warm, Spitze je Rolle; Empfehlung mit Puffer in den Helm-Values. Team-Limit mit mehr Reserve, bis der Live-Abruf im Cluster gemessen ist. | [messung.md](../messung.md) |
| Datenbank, große Daten | erfüllt: keine Datenbank. Daten nicht im Image; das Team baut sie im Volume `/data` (2 Gi) auf, optional aus Startdaten unter `QE_SEED_URL`. Heute 5,8 MB Startdaten und 18 MB Exporte. | [betrieb.md](../betrieb.md#erststart-seed-daten-updates), [datenaufbereitung.md](../datenaufbereitung.md) |
| Updates der Daten | erfüllt: nächtlich im Team-Pod (`QE_AUTO_REFRESH_HOUR`), kein CronJob (RWO-Volume); Alarm bei Daten älter als 26 h. | [steckbrief.md](steckbrief.md), [betrieb.md](../betrieb.md#erststart-seed-daten-updates) |
| Env, Helm-Values, Secrets, Dockerfile, Compose | erfüllt: Env-Tabelle mit Secrets in `betrieb.md`; Chart mit `values-team.yaml`, `values-partner.yaml`, `values-public.yaml`; Secrets `QE_TEAM_PASSWORD`, `QE_SESSION_SECRET`, `QE_TIER1_PASSWORD`; Dockerfile und Compose als Referenz. | [betrieb.md](../betrieb.md#secrets-und-umgebung), [Chart](../../deploy/helm/quellenpanel/README.md), [Compose](../../deploy/README.md), [Dockerfile](../../Dockerfile) |
| Netzpartner (NetworkPolicy) | erfüllt: eingehend 8080 von überall bzw. vom Ingress, 9090 nur von Quellenpanel-Pods und Monitoring (`networkPolicy.enabled`). Ausgehend: Team → Repository (HTTPS) und `QE_SEED_URL`; Partner und Öffentlich → Team:9090 und Repository (Beispielinhalte, Vorschaubilder). Von T6 angefordert: Namespaces von Ingress-Controller und Monitoring. | [Chart](../../deploy/helm/quellenpanel/README.md) |
| Kosten je Funktion | erfüllt: nur Betriebskosten (kein Modell, keine kostenpflichtigen Drittdienste). Laufzeit je Funktion im Steckbrief. | [steckbrief.md](steckbrief.md) |
| Kompatibilitätsmatrix | erfüllt: Zeile `quellenpanel`. | [kompatibilitaet.md](kompatibilitaet.md) |
| Changelog | erfüllt: je Release mit Hinweisen für den Betrieb. | [CHANGELOG.md](../../CHANGELOG.md) |
| Ansprechperson und Vertretung | offen: werden vor der Übergabe eingetragen. | [steckbrief.md](steckbrief.md) |
| Wer Updates anstößt | offen: vor der Übergabe festzulegen (siehe Wartung). | diese Seite |

## Architektur in Kürze

```
                     Repository (edu-sharing, öffentliche REST-API)
                        ▲  Live-Abruf nachts      ▲  Beispielinhalte, Vorschaubilder
                        │                          │
  intern (VPN/SSO) ── team :8080  ── /data (RWO) ──┤
                        │ :9090 /internal/exports/stufe0|1.json (ETag)
                ┌───────┴────────┐                 │
           partner :8080     public :8080 ─────────┘
          (Stufe 1, Passwort) (Stufe 0, Widgets)
```

Ein Image, drei Instanzen. Das Team baut die Daten und schreibt je Stufe einen Export. Partner und
Öffentlich halten nur ihren Export im Speicher und behalten bei Fehlern den letzten gültigen Stand.

## Wartung

- **Wer Updates anstößt:** vor der Übergabe festzulegen (Abhängigkeiten, Sicherheitspatches,
  Basis-Images per Digest). Dependabot ist nicht eingerichtet; `pip-audit` und `npm audit` laufen in
  der CI bei jedem Push.
- **Release:** Version in `backend/pyproject.toml`, `frontend/package.json` und im Chart gleich
  halten (Test), Changelog ergänzen, Tag `v<version>` setzen.
- **Andere Repositorys:** neues Profil unter `profiles/<name>/`, Auswahl mit `QE_PROFILE`.
