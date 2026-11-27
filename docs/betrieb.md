# Betrieb – Quellenpanel (Dienst-ID `quellenpanel`, Version 1.0.0)

Dieses Dokument beschreibt den Betrieb nach dem Diensteleitfaden: Rollen, Ports, Probes, Metriken,
Alarme, Logs und Tracing, Erststart, Daten-Updates, Secrets. Bereitstellung: Compose in
[`deploy/README.md`](../deploy/README.md), Kubernetes in
[`deploy/helm/quellenpanel/README.md`](../deploy/helm/quellenpanel/README.md).

## Rollen und Zustand

Ein Image, drei Instanzen (`QE_ROLE`):

| Rolle | Stufe | Zustand | Skalierung |
|---|---|---|---|
| `team` | 2 (Audit) | Daten auf einem RWO-Volume unter `/data` | genau 1 Pod, Strategie `Recreate` |
| `partner` | 1 (Steckbrief, Passwort) | nur Export Stufe 0/1, vom Team geholt | zustandslos, beliebig |
| `public` | 0 (Quellenliste, Widgets) | nur Export Stufe 0, vom Team geholt | zustandslos, beliebig |

Ohne `QE_ROLE` (und ohne `QE_PUBLIC_ONLY`) läuft eine Instanz als `team`; das ist für die lokale
Entwicklung gedacht. Das Helm-Chart setzt immer eine Rolle (Standard `public`), Compose ebenfalls.
Eine Team-Instanz gehört im Kubernetes-Betrieb hinter VPN/SSO: Sie hält alle Daten und die Schreibrouten. Stufe 1 und 2 sind dort nur mit ihrem Passwort erreichbar.

Partner und Öffentlich halten nie die internen Daten. Sie holen `stufe{tier}.json` vom internen Port
des Teams (ETag, alle `QE_EXPORT_POLL_MINUTES`, solange ein Export fehlt alle 15 s) und behalten bei
Fehlern den letzten gültigen Stand, auch als Kopie in `/tmp`.

## Ports und Probes

| Port | Inhalt | Erreichbar |
|---|---|---|
| 8080 | API, SPA, Widgets, `/openapi.json` (nur Pfade der Rolle) | öffentlich (Team: intern) |
| 9090 | `GET /health`, `GET /ready`, `GET /metrics`, `GET /internal/exports/stufe{0,1}.json` (nur Team) | nur im Cluster |

- **Liveness/Startup:** `/health` ist 200, solange der Prozess lebt. Der Body zeigt Rolle, Version,
  Datenstand (`data.state` = `ready` / `building` / `missing`, `generatedAt`, `ageSeconds`) und den
  Rebuild (`rebuild`, mit `rebuild.last` aus `$QE_DATA_DIR/status.json`).
- **Readiness-Probe (alle Rollen):** `GET /api/health` auf dem öffentlichen Port 8080. Sie fragt keinen
  anderen Dienst (Leitfaden: Readiness ohne Abhängigkeiten), nur den eigenen Prozess und seine Daten
  im Speicher. Ein Pod mit kaputtem öffentlichem Listener fällt so aus der Rotation.
  **Team:** immer 200, damit der einzelne Team-Pod auch beim Datenaufbau erreichbar bleibt (Login,
  „Daten aktualisieren“); Datenrouten antworten bis dahin mit 503 „Daten werden aufgebaut“ und
  `Retry-After: 60`. **Partner/Öffentlich:** 503 `status: starting`, bis alle Exporte der Rolle
  geladen sind, dann 200. So ersetzt ein Rolling Update bei ausgefallenem Team keine alten Pods, die
  noch den letzten gültigen Export halten. Fällt das Team später aus, bleiben die Pods bereit und
  liefern den letzten Stand. Die Probe wird weder geloggt noch in `http_requests_total` gezählt.
- **`/ready` (nur Monitoring):** 200, sobald die Daten der Rolle im Speicher sind (Team: Datensätze;
  sonst alle Exporte der Rolle), sonst 503. `source.ok` meldet, ob Repository bzw. Export-Quelle
  erreichbar sind; diese Prüfung läuft höchstens alle 30 s. `/ready` ist bewusst **keine**
  Kubernetes-Probe.
- **Sauberes Beenden:** Kubernetes ruft zuerst den `preStop`-Haken (`sleep 5`, Wert
  `preStopSleepSeconds`), damit der Pod aus dem Service genommen ist, bevor SIGTERM kommt. Dann
  beendet `serve.py` beide Server: neue Verbindungen werden abgelehnt, laufende Anfragen haben 20 s
  (`timeout_graceful_shutdown`), danach läuft der Lifespan zu Ende. `terminationGracePeriod` (30 s)
  liegt darüber. Läuft gerade ein Rebuild, steht danach `status: "abgebrochen"` in `status.json`.
  Endet ein Server unerwartet (Port belegt, Start fehlgeschlagen), endet der Prozess mit Exit-Code ≠ 0.
  Compose wartet beim Stoppen 10 s (Docker-Standard); `stop_grace_period` kann das verlängern.

## Erststart, Seed, Daten-Updates

- Die Daten sind **nicht im Image** (`.dockerignore`: `truth.json`, `raw/`, `exports/`,
  `profiles/*/daten/`).
- **Ohne Korrekturen kein Datenaufbau:** Das Image enthält weder `korrekturen.csv` noch
  `crawler.csv` (sie können interne Vermerke enthalten). Fehlt eine der beiden im Volume, lehnt das
  Team jeden Aufbau ab (Log-Fehler, `status.json` und `/jobs/latest` mit „Startdaten fehlen“,
  Zähler `quellenpanel_rebuild_total{result="error"}`), statt Quellen ohne Blacklist zu
  veröffentlichen. Abhilfe: `QE_SEED_URL` setzen oder beide Dateien im Bereich „Korrekturen“
  hochladen (Import „ersetzen“ und Crawler-Tabelle), dann „Daten aktualisieren“.
- **Erststart Team mit leerem Volume:** Seed, Laden und Aufbau laufen im Hintergrund; die Ports
  antworten sofort. Fehlende `crawler.csv`, `korrekturen.csv`, `truth.json` werden von
  `QE_SEED_URL` geladen (vorhandene Dateien werden nie überschrieben; HTML-Seiten und eine
  `truth.json` ohne `meta`/`records` werden verworfen; Zeitlimit 5 min). Eine vorhandene, aber
  kaputte `truth.json` wird nach `truth.json.kaputt-<zeit>` verschoben, dann startet der Aufbau. Fehlt `truth.json`
  danach noch, startet der Datenaufbau im Hintergrund. Bis er fertig ist, antworten alle Datenrouten
  mit 503 `{"error": "service_unavailable", "message": "Daten werden aufgebaut", "retryAfter": 60}`
  und `Retry-After: 60`. `/health` und `/api/health` sind 200 (`data.state = building`), `/ready` 503. Schlägt der Aufbau
  fehl, bleibt der Status unter `/health` → `rebuild.last` lesbar. **Wiederherstellung:** Ursache
  beheben (Netz, `QE_SEED_URL`), dann als Team anmelden und „Daten aktualisieren“ drücken, oder den
  Pod neu starten. Ohne Eingriff versucht es erst der nächste nächtliche Lauf; nach 6 h ohne Daten
  meldet `QuellenpanelNoData`.
- **Nächtlicher Rebuild im Team-Pod** (`QE_AUTO_REFRESH_HOUR`, z. B. `3`): Er läuft dort, weil nur
  dieser Pod das RWO-Volume eingebunden hat. Ein separater CronJob bräuchte ein RWX-Volume oder
  einen zweiten Weg zu den Daten; der Rebuild nutzt dieselbe Sperre wie der Knopf
  „Daten aktualisieren“, läuft also nie doppelt. Nach dem Rebuild baut das Team die Exporte neu,
  Partner und Öffentlich übernehmen sie beim nächsten Abruf.

## Korrekturen und Crawler-Tabelle (Team-Bereich)

Die Team-Instanz hat die Ansicht **Korrekturen** (Stufe 2, nach dem Team-Login). Sie pflegt zwei
Dateien auf dem Volume:

| Datei | Inhalt |
|---|---|
| `/data/korrekturen.csv` | Korrekturen im Langformat. Bis zur ersten Änderung gilt der Startstand aus dem Profil; der wird nie überschrieben. |
| `/data/crawler.csv` | Crawler-Tabelle, per Upload ersetzt (Pflichtspalten aus `profil.toml`: Spider- und Quelldatensatz-Spalte). |
| `/data/korrekturen-verlauf.csv` | Verlauf: `Zeitpunkt;Wer;Vorgang;Alt;Neu`; „Wer“ ist das im Browser eingegebene Kürzel. |
| `/data/korrekturen-<zeit>.csv`, `/data/crawler-<zeit>.csv` | Sicherungen vor jedem Ersetzen (Import „ersetzen“, Crawler-Upload). Werden nicht automatisch gelöscht. |

- **Funktionen:** Tabelle mit Suche und Filter, Anlegen/Ändern/Löschen, Download als CSV, Import
  aus CSV (`;` oder `,`), JSON (Liste von Objekten) und XLSX mit Spaltenzuordnung und Vorschau
  (neu, geändert, unverändert, fehlerhaft, entfallen), Modus „ergänzen“ oder „ersetzen“. Im
  Steckbrief einer Quelle: „Auf Blacklist“ und „Beschreibung ergänzen“.
- **Wirkung:** Nach jeder Änderung rechnet der Team-Pod den Merge aus den Roh-Caches
  (`/data/raw/`) neu, lädt die Daten und schreibt die Exporte (Sekundenbereich, ohne Live-Abruf).
  Partner und Öffentlich übernehmen sie beim nächsten Export-Abruf. Fehlen die Roh-Caches (Pod
  nur mit `truth.json` geseedet), wirken Beschreibungen und Vorschaubilder sofort, Node-Korrekturen
  und die Crawler-Tabelle beim nächsten Datenaufbau; die Oberfläche sagt das an.
- **Schutz:** Die Routen `/api/team/…` gibt es nur in der Rolle `team` (sonst 404) und nur mit
  Team-Login (403). Schreibende Anfragen mit fremdem `Origin` werden abgewiesen (CSRF), ebenso
  Änderungen während eines Rebuilds (409) und Änderungen auf veraltetem Stand (409, Feld `version`).
  Uploads dürfen bis 5 MB groß sein (sonst 1 MB), XLSX höchstens 20 000 Zeilen.
- Die Routen sind auch beim Erststart ohne Daten erreichbar, damit das Team eine fehlerhafte
  Crawler-Tabelle ersetzen kann.

## Metriken (`/metrics`, Prometheus)

| Metrik | Art | Bedeutung |
|---|---|---|
| `http_requests_total{route,method,status}` | Counter | Anfragen je Routenklasse (Vorlage, nie der Pfad) |
| `http_request_duration_seconds{route,method}` | Histogram | Antwortzeiten |
| `quellenpanel_rebuild_total{result}` | Counter | Rebuilds `success` / `error` |
| `quellenpanel_rebuild_duration_seconds` | Histogram | Dauer der Rebuilds |
| `quellenpanel_rebuild_last_success_timestamp_seconds` | Gauge | letzter erfolgreicher Rebuild (seit Prozessstart) |
| `quellenpanel_data_age_seconds` | Gauge | Alter des ausgelieferten Datenstands (`NaN` = keiner) |
| `quellenpanel_export_fetch_total{tier,result}` | Counter | Export-Abrufe `ok` / `not_modified` / `error` |
| `quellenpanel_upstream_requests_total{target,result}` | Counter | ausgehende Anfragen an `repository` / `export_source` |

Dazu die Prozess-Metriken von `prometheus_client`.

## Alarme (PrometheusRule, `metrics.prometheusRule.enabled`)

| Alarm | Bedingung | Rolle |
|---|---|---|
| `QuellenpanelRebuildStale` | `quellenpanel_data_age_seconds > 26 h` (15 min) | team |
| `QuellenpanelNoData` | seit 6 h überhaupt keine Daten (erster Aufbau fehlgeschlagen) | team |
| `QuellenpanelHigh5xx` | mehr als 5 % 5xx über 10 min | alle |
| `QuellenpanelExportFetchFailing` | 30 min nur fehlgeschlagene Export-Abrufe | partner, public |

Der Rebuild-Alarm misst das Alter der Daten statt des letzten Rebuild-Zeitpunkts, weil dieser Zähler
bei jedem Pod-Neustart bei null beginnt und sonst nach jedem Neustart fälschlich auslösen würde. Die
Regeln sind mit `promtool test rules deploy/helm/quellenpanel/tests/rules-test.yaml` getestet.

## Logs und Tracing

- **Format:** eine JSON-Zeile je Ereignis auf stdout: `timestamp` (UTC), `level`, `service`
  (`quellenpanel`), `logger`, `trace_id`, `span_id`, `message` und Zusatzfelder. `LOG_FORMAT=text`
  schaltet auf Klartext, `LOG_LEVEL` (Standard `INFO`) regelt die Menge.
- **Eine Zeile je Anfrage** (`message: "request"`): `method`, `route` (Routenvorlage, z. B.
  `/api/sources/{source_id:path}`; unbekannte Pfade `<unmatched>`, statische Dateien `<static>`),
  `status`, `duration_ms`, bei Suchanfragen `q_pseudonym` (die ersten 12 Hex-Zeichen eines HMAC-SHA256 mit einem Schlüssel je Prozess: innerhalb eines Laufs vergleichbar, nicht per Wortliste umkehrbar).
  Der uvicorn-Access-Log ist aus.
- **Nie im Log:** Passwort-Header, Session-Cookie, Pfade mit IDs, Query-Strings, Suchbegriffe im
  Klartext. Ein Test prüft das auch für 404 und 500.
- **B3:** `X-B3-TraceId`/`X-B3-SpanId`/`X-B3-Sampled` oder `b3` werden gelesen und geprüft (Trace-ID 16
  oder 32, Span-ID 16 Hex-Zeichen, klein). Ungültige Werte werden verworfen und eine neue Trace-ID
  angelegt. Die Antwort trägt `X-B3-TraceId`; ausgehende Aufrufe an Repository und Export-Quelle
  bekommen einen Kind-Span. `x-client-trace-id` (bis 64 Zeichen `[A-Za-z0-9._-]`) wird durchgereicht.
- **Fehler** haben immer die Form `{"error", "message", "status", "trace_id"}`. Mit der `trace_id`
  findet man die Logzeilen der Anfrage. 500 zeigt nur „Interner Fehler“; der Stacktrace steht im Log.

## Secrets und Umgebung

| Variable | Rolle | Secret | Zweck |
|---|---|---|---|
| `QE_ROLE` | alle | | `team` / `partner` / `public` |
| `QE_TEAM_PASSWORD` | team | ja | Team-Login (Stufe 2); leer = kein Team-Zugang |
| `QE_SESSION_SECRET` | team | ja | HMAC-Schlüssel der Team-Sitzung; leer = einmal zufällig erzeugt in `session.key` im Datenordner (Volume), ohne beschreibbaren Datenordner zufällig je Prozess |
| `QE_TIER1_PASSWORD` | partner, team | ja | Passwort für Stufe 1; leer = Stufe 1 bleibt zu (auf jeder Instanz) |
| `QE_SEED_URL` | team | | Startdaten für den Erststart |
| `QE_AUTO_REFRESH_HOUR` | team | | Stunde des nächtlichen Rebuilds |
| `QE_EXPORT_SOURCE`, `QE_EXPORT_POLL_MINUTES` | partner, public | | Export-Quelle mit `{tier}`, Abrufintervall |
| `QE_ALLOWED_ORIGINS` | team | | Origins für den Team-Login aus eingebetteten Widgets |
| `TRUST_PROXY` | alle | | Client-IP aus dem rechten `X-Forwarded-For`-Eintrag, nur wenn die Anfrage von einer privaten Adresse (dem Proxy) kommt; nur hinter einem Proxy, der den Header setzt |
| `QE_REPO_URL`, `QE_SEARCH_URL` | alle | | Repository und öffentliche Suche (Links); Standard aus dem Profil |
| `QE_PROFILE`, `QE_PROFILES_DIR` | alle | | Repository-Profil (Standard `wlo`) und sein Verzeichnis (Standard `profiles/`) |
| `QE_FRAME_ANCESTORS` | alle | | wer die iframe-Widgets (`/embed/…`) einbetten darf; leer = überall, auf dem Team nur `'self'` |
| `QE_THUMB_CACHE_MB` | alle | | Speicher für zwischengespeicherte Vorschaubilder (PDF-Export) in MiB, Standard 16, `0` = aus; zählt zum Speicherlimit |
| `QE_REVISION` | alle | | Commit, aus dem das Image gebaut wurde; setzt die CI als Build-Argument. `/api/capabilities` zeigt ihn als `revision`. Nicht von Hand setzen |
| `QE_PUBLIC_ONLY` | | | Übergangsname: `1` entspricht `QE_ROLE=public` |
| `QE_RENAME_UNREP_BQ` | team | | `0` schaltet die Umbenennung nicht repräsentierter Bezugsquellen beim Datenaufbau ab |
| `QE_DATA_DIR` | alle | | Datenverzeichnis (Image: `/data`) |
| `LOG_FORMAT`, `LOG_LEVEL` | alle | | Logs |
| `QE_PORT`, `QE_INTERNAL_PORT`, `QE_HOST` | alle | | Ports (8080, 9090) und Bind-Adresse (`0.0.0.0`) |

**Passwörter und Sitzungsschlüssel wechseln:** Wert im Secret ändern (Helm: `config.existingSecret`
oder die Werte im Chart-Secret; Compose: `deploy/.env`), dann die Pods neu starten
(`kubectl rollout restart deployment/<release>` bzw. `docker compose up -d`). Ein neues
`QE_TEAM_PASSWORD` oder `QE_TIER1_PASSWORD` gilt ab dem Neustart; bestehende Team-Sitzungen laufen
weiter, bis sie ablaufen (12 h). Ein neues `QE_SESSION_SECRET` beendet sofort alle Team-Sitzungen; ohne die Variable tut das das Löschen von `session.key` im Datenordner und ein Neustart.

**Team-Sitzung:** Der Login setzt ein httpOnly-Cookie `qe_session` = `<ablauf>.<nonce>.<hmac>`
(12 h). Jede Instanz mit demselben `QE_SESSION_SECRET` erkennt es; ein Neustart beendet keine
Sitzung. Logout sperrt die Nonce bis zum Ablauf, aber nur im Speicher dieses Pods (die Team-Instanz
hat genau einen).

## Betrieb ohne b-api

Quellenpanel ruft keine b-api-Funktion auf und braucht auch keine: Es zeigt öffentliche
Webseiten-Daten der Quellen ohne Personenbezug, für einen anonymen Lesezugriff, den die b-api nicht
anbietet. Die Zugangsstufen regelt der Dienst selbst über Rollen (getrennte Instanzen) und Passwörter;
interne Daten liegen nie auf den öffentlichen Instanzen.

## Versionen und Freigabe

Die einzige Versionsquelle ist `backend/pyproject.toml`. Helm-Chart (`version`, `appVersion`) und
`frontend/package.json` müssen gleich sein; CI und Tests prüfen das. Ein Release-Tag heißt `v` +
Version (`v1.0.0`); das Image wird dann mit `1.0.0` und `1.0` getaggt. Die Basis-Images sind per
Digest festgelegt und werden bewusst angehoben.
