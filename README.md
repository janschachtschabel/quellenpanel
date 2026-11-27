# Quellenpanel

**Deutsch** · [English](README.en.md)

Quellenpanel zeigt die Quellen eines edu-sharing-Repositorys (Standard: WirLernenOnline): als
öffentliche Quellenliste mit Widgets, als Steckbrief für Partner und als internes Audit für das
Team. Ein Image: als eine Instanz, die alle Stufen per Passwort trennt, oder als drei Instanzen mit je
einer Zugangsstufe. Version und Änderungen:
[`CHANGELOG.md`](CHANGELOG.md).

## Überblick

| Stufe | Für wen | Was man sieht | Wo |
|---|---|---|---|
| **0 Basis** | alle | Quellen, Filter, Qualitätsmerkmale, Beispielinhalte, Statistik | Instanz `public` (und alle anderen) |
| **1 Details** | Partner, Steckbrief-Erstellung | zusätzlich Herkunft, Lizenzen, Felderzeugung, Export, Steckbrief-PDF | jede Instanz außer `public`, mit dem Stufe-1-Passwort |
| **2 Audit** | Team | zusätzlich interne Felder, Datenprobleme, Protokoll, Korrekturen, Datenabgleich | nur Instanz `team`, mit Team-Passwort |

Jede Instanz liefert unter Stufe 2 nur aus ihrem Export. Die öffentliche Instanz hat die Daten der
Stufen 1 und 2 gar nicht erst im Speicher.

## Installation

**Lokal ausprobieren** (Python 3.12, Node 22 oder 26):

```bash
cd frontend && npm ci && npm run build && npm run build:element && npm run build:widgets && cd ..
cd backend && pip install -r requirements.txt
QE_TEAM_PASSWORD=geheim python serve.py      # http://localhost:8080 (Rolle team)
```

Ohne `QE_ROLE` läuft die Instanz als `team`; das ist nur für die Entwicklung gedacht. Beim ersten
Start ohne Daten baut sie die Daten aus dem Repository auf (einige Minuten, bis dahin antworten
die Datenrouten mit 503) oder lädt Startdaten von `QE_SEED_URL`. Im Container (Compose, Helm) fehlen Korrekturen und Crawler-Tabelle im Image: dort `QE_SEED_URL` setzen oder beide Dateien im Team-Bereich hochladen, sonst baut das Team keine Daten.

**Server mit Traefik** (Docker-Server, auf dem schon ein Traefik-Proxy mit Let's Encrypt läuft,
etwa ein Docker-Panel mit „Compose aus URL“): Die `docker-compose.yml` im Hauptordner startet eine
Instanz, die alle Stufen über einen Port liefert (Stufe 1 und 2 nur mit ihrem Passwort), zieht bei jedem
Update das neueste Image von main aus GitHub (`QE_VERSION` legt eine Version fest) und braucht beim ersten Start keine einzige Variable. Danach in der `.env`
(Vorlage `.env.example`) `DOMAIN` oder `PORT` und die Passwörter eintragen und erneut bereitstellen.
Getrennte Partner- und öffentliche Instanzen lassen sich mit `SEPARATE_INSTANCES=1` zuschalten. Schritt für Schritt in [`deploy/README.md`](deploy/README.md#server-with-traefik).

**Server mit Docker Compose** (drei Instanzen aus einem veröffentlichten Image, Schritt für Schritt in
[`deploy/README.md`](deploy/README.md)):

```bash
cp deploy/.env.example deploy/.env       # IMAGE, Passwörter, Ports eintragen
docker compose -f deploy/docker-compose.yml up -d
```

Team auf `127.0.0.1:8082`, Partner auf `8081`, Öffentlich auf `8080`. Eine Variante mit
automatischem HTTPS (Caddy) liegt daneben.

**Kubernetes mit Helm** (eine Release je Rolle, Details in
[`deploy/helm/quellenpanel/README.md`](deploy/helm/quellenpanel/README.md)):

```bash
helm upgrade --install quellenpanel-team    deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-team.yaml \
  --set config.existingSecret=quellenpanel-team-secrets
helm upgrade --install quellenpanel-partner deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-partner.yaml
helm upgrade --install quellenpanel-public  deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-public.yaml
```

Betrieb (Ports, Probes, Metriken, Alarme, Logs, Secrets, Daten-Updates):
[`docs/betrieb.md`](docs/betrieb.md). Gemessene Ressourcen: [`docs/messung.md`](docs/messung.md).
Übergabe an den Betrieb: [`docs/uebergabe/`](docs/uebergabe/README.md).

## Nutzung

Die App hat drei Ansichten: **Kacheln**, **Liste** und **Statistiken**. Oben stehen Suche,
Quellenart und Sortierung, darunter Fach, Bildungsstufe, Inhaltstyp, Mindestzahl an Inhalten und
OER. **Feld-Profil** zeigt nur Quellen, zu denen die Crawler-Tabelle angibt, wie ihre Metadatenfelder
entstehen. Ein Klick auf eine Quelle öffnet den Steckbrief mit Beispielinhalten aus dem Repository.

Rechts oben wählt man die Stufe (**Basisinfos**, **Details**, **Audit**) und die Sprache (DE/EN).
**Details** fragt einmal nach dem Stufe-1-Passwort, **Audit** nach dem Team-Passwort.
In Details und Audit lassen sich mehrere Quellen auswählen und als Steckbrief-PDF ausgeben; die
gefilterte Liste gibt es als CSV, JSON oder Tabellen-PDF.

## Zugangsstufen und Schutz

| Was | Wie | Wirkung |
|---|---|---|
| Rolle der Instanz | `QE_ROLE=team`, `partner` oder `public` | begrenzt die höchste Stufe (2, 1, 0); immer setzen |
| Stufe 1 (Partner und Team) | `QE_TIER1_PASSWORD` (Secret) | ohne Passwort bleibt Stufe 1 auf jeder Instanz zu; die App fragt danach, API-Aufrufe senden es im Header `x-tier1-password` |
| Stufe 2 (Team) | `QE_TEAM_PASSWORD` (Secret) | ohne Passwort gibt es keinen Team-Zugang; Login über den Knopf **Audit** |
| Team-Sitzung | `QE_SESSION_SECRET` (Secret, `openssl rand -hex 32`) | signiertes Cookie für 12 h; mit festem Schlüssel übersteht die Anmeldung Neustarts |
| Team-Instanz abschirmen | Ingress hinter VPN/SSO (empfohlen) | die Team-Instanz hält alle Daten und die Schreibrouten; öffentlich erreichbar schützen sie nur die Passwörter und die Fehlversuchsbremse |
| Port 9090 (Exporte, Metriken) | `networkPolicy.enabled` (in `values-team.yaml` an) | nur Quellenpanel-Pods und Monitoring erreichen ihn; nie veröffentlichen |
| Team-Login aus fremder Seite | `QE_ALLOWED_ORIGINS` | nur für eingebettete Team-Ansichten, nur über HTTPS |

**Hinter der b-api** (optional): Die API-Endpunkte können hinter dem Dienste-Proxy der b-api liegen.
Der Dienst erkennt das je Anfrage am Delegations-Token und bietet dort keine eigene Anmeldung an
(Stufe 0 anonym, Stufe 1 nur mit `X-Tier1-Password`, kein Team-Bereich). Direkt bleibt alles wie
oben. Proxy-Eintrag: [`docs/betrieb.md`](docs/betrieb.md#betrieb-mit-und-ohne-b-api).

Passwörter tauschen: Secret ändern und die Pods neu starten. Ein neuer `QE_SESSION_SECRET` meldet
alle Team-Sitzungen ab. Fehlversuche mit Passwörtern (Login und Kopfzeilen) sind je Adresse gedrosselt.

## Bearbeitungsbereich (Korrekturen)

Der Bearbeitungsbereich gibt es nur auf der **Team-Instanz**:

1. Team-Instanz öffnen (Server mit Traefik: `http://<SERVER-IP>:18080` oder die Domain; drei
   Instanzen mit `deploy/`: intern `http://127.0.0.1:8082`).
2. Rechts oben **Audit** wählen und das Team-Passwort (`QE_TEAM_PASSWORD`) eingeben.
3. In der Ansichtsleiste erscheint **Korrekturen**.

Dort pflegt das Team die Korrekturen (Tabelle mit Suche, Anlegen, Ändern, Löschen, Verlauf mit
Kürzel), importiert Listen aus CSV, JSON oder XLSX mit Vorschau und ersetzt die Crawler-Tabelle.
Im Steckbrief einer Quelle gibt es zusätzlich **Auf Blacklist** und **Beschreibung ergänzen**.
Nach jeder Änderung rechnet das Team die Daten neu; Partner und Öffentlich übernehmen sie beim
nächsten Abgleich (Standard alle 10 Minuten). **Daten aktualisieren** im Audit holt die Daten neu
aus dem Repository. Dateien und Sicherungen: [`docs/betrieb.md`](docs/betrieb.md#korrekturen-und-crawler-tabelle-team-bereich).

## Daten über die API

Alle Lese-Endpunkte liefern JSON ohne Anmeldung (Stufe 0). Am saubersten holt man Daten von der
öffentlichen Instanz; sie kennt nur öffentliche Felder. Die vollständige Beschreibung steht unter
`/openapi.json` (interaktiv unter `/docs`).

```bash
H=https://quellen.example.de

# Liste mit Filtern und Blättern (Seite 1, 50 Einträge, Mathematik, nur OER, nach Inhalten absteigend)
curl "$H/api/sources?subject=Mathematik&oer=true&page=1&page_size=50&sort=contentCount&order=desc"

# Suche, Bildungsstufe, nur Crawler, mindestens 10 Inhalte
curl "$H/api/sources?q=physik&level=Sekundarstufe%20I&crawler=true&min_count=10"

# Eine Quelle (id aus der Liste, z. B. crawler:bpb_spider)
curl "$H/api/sources/crawler:bpb_spider"

# Beispielinhalte einer Quelle live aus dem Repository
curl "$H/api/sources/crawler:bpb_spider/contents?max_items=12&skip=0"

# Kennzahl (Anzahl Quellen und Inhalte) und Werte für die Filter
curl "$H/api/kennzahl?subject=Biologie"
curl "$H/api/meta/filters"

# Statistik (Fächer, Bildungsstufen, Inhaltstypen)
curl "$H/api/stats"

# Flacher Export als JSON oder CSV (ab Stufe 1: Partner mit Passwort)
curl -H "x-tier1-password: $PW" "$H/api/export.csv?tier=1&subject=Chemie"
```

Felder einer Quelle in der Liste: `id`, `name`, `contentCount`, `url`, `searchUrl` (Link in die
Suche), `bezugsquelle`, `description`, `subjects`, `educationalContext`, `contentTypes`, `license`,
`oer`, `language`, `previewUrl`, `erschliessungsstatus`, `quality` (Kosten, Werbung, Anmeldung,
Datenschutz …). Die Antwort der Liste hat `total`, `page`, `pageSize`, `pages` und `items`.

Hinweise: Höchstens 200 Einträge je Seite. Exporte (`/api/export.json`, `/api/export.csv`) haben
dieselben Filter wie die Liste. Der Live-Abruf `/contents` ist je Client gedrosselt (429 mit
`Retry-After`). Fehler kommen immer als `{"error", "message", "status", "trace_id"}`.

Alle Endpunkte:

```
GET  /api/sources · /api/sources/{id} · /api/sources/{id}/contents · /api/kennzahl
GET  /api/meta/filters · /api/stats · /api/capabilities · /api/health
GET  /api/export.json · /api/export.csv                        ab Stufe 1
POST /api/sources/batch                                         mehrere Quellen auf einmal
GET  /api/stats/team · /api/protokoll.md|.json|.csv              Team
POST /api/auth · /api/logout · GET /api/auth/status              Team-Login
POST /jobs/refresh · GET /jobs/latest                            Datenabgleich (Team)
GET|POST /api/team/korrekturen · PUT|DELETE /api/team/korrekturen/{id}   Korrekturen (Team)
GET  /embed/{name} · /widgets/…                                  Widgets
```

## Einbetten (Widgets)

Ein kleines Skript bringt Quellenliste, Top 10 je Fach, Kennzahl, eine Quelle und Statistik, dazu
Kacheln und die ganze App. Schlank auf einer weißen Seite, ohne Kopf, Fuß und Rahmen:

```html
<script src="https://quellen.example.de/widgets/quellenpanel-widgets.js" defer></script>
<wlo-quellen-kacheln kopf="aus" fuss="aus" rahmen="aus" hintergrund="#ffffff"></wlo-quellen-kacheln>
<wlo-quellen-kacheln ansicht="liste" kopf="aus" fuss="aus" filter="aus" rahmen="aus" fach="Chemie"></wlo-quellen-kacheln>
<wlo-quellen-top fach="Biologie" max="10" farbe="#003b7c"></wlo-quellen-top>
```

Dasselbe als iframe (`/embed/quellen-kacheln?kopf=aus&fuss=aus&rahmen=aus`) oder als Link auf die
App (`/?kopf=aus&ansicht=liste`). Alle Elemente, Attribute und Farben:
[`docs/widgets.md`](docs/widgets.md); Testseiten unter `/widgets/beispiele/`.

## Konfiguration

| Variable | Standard | Zweck |
|---|---|---|
| `QE_ROLE` | `team` | `team`, `partner` oder `public` |
| `QE_TEAM_PASSWORD` | leer (kein Team-Zugang) | Passwort Stufe 2 |
| `QE_TIER1_PASSWORD` | leer (Stufe 1 zu) | Passwort Stufe 1 |
| `QE_SESSION_SECRET` | `session.key` im Datenordner | Schlüssel der Team-Sitzung |
| `QE_EXPORT_SOURCE`, `QE_EXPORT_POLL_MINUTES` | leer, `10` | Partner/Öffentlich: Export-Quelle mit `{tier}`, Abgleich in Minuten |
| `QE_SEED_URL` | leer | Team: Startdaten für den ersten Start |
| `QE_AUTO_REFRESH_HOUR` | leer (aus) | Team: Stunde des nächtlichen Abgleichs |
| `QE_ALLOWED_ORIGINS` | leer | Origins für Team-Login aus eingebetteten Seiten |
| `QE_FRAME_ANCESTORS` | `*` (Team: `'self'`) | wer die iframe-Widgets einbetten darf |
| `QE_THUMB_CACHE_MB` | `16` | Zwischenspeicher für Vorschaubilder in MiB (`0` = aus) |
| `QE_REPO_URL`, `QE_SEARCH_URL` | aus dem Profil | Repository und Suche |
| `QE_PROFILE`, `QE_PROFILES_DIR` | `wlo`, `profiles/` | Repository-Profil |
| `QE_VERSION` | leer (`main`) | nur Server-Compose: Image-Version aus GitHub |
| `B_API_DELEGATION_HEADER` | leer | hinter der b-api mit eigenem `delegationHeader` |
| `QE_DATA_DIR` | `backend/data` (Image: `/data`) | Datenverzeichnis |
| `TRUST_PROXY` | aus | Client-Adresse aus `X-Forwarded-For` (nur hinter eigenem Proxy) |
| `LOG_FORMAT`, `LOG_LEVEL` | `json`, `INFO` | Logs |
| `QE_PORT`, `QE_INTERNAL_PORT`, `QE_HOST` | `8080`, `9090`, `0.0.0.0` | Ports, Bind-Adresse |

Vollständig mit Rollen und Secrets: [`docs/betrieb.md`](docs/betrieb.md#secrets-und-umgebung).

## Anderes Repository anbinden

Alles, was ein edu-sharing-Repository ausmacht, steht in einem **Profil** unter `profiles/<name>/`.
Der Code bleibt unverändert. Eine Instanz bedient genau ein Repository; für ein zweites startet man
eine zweite Instanz.

**Gleicher Metadatensatz, andere Adresse** (z. B. ein Testsystem): nur `QE_REPO_URL` und
`QE_SEARCH_URL` setzen (Server: in der `.env`) und neu starten.

**Eigener Metadatensatz:** ein eigenes Profil anlegen.

1. `profiles/beispiel/` nach `profiles/<name>/` kopieren. In `profil.toml` `id`, `name` und
   `[repository]` (Adresse, Suche, Metadatensatz `mds`, woran ein Quelldatensatz zu erkennen ist)
   eintragen.
2. Unter `[felder]` die Properties des eigenen Metadatensatzes eintragen, unter `[qualitaet]` die
   Qualitätskriterien (darf leer sein), unter `[spider]`, woran ein Crawler zu erkennen ist.
3. Die Crawler-Tabelle beschreibt je Quelle die Herkunft der Metadaten (Spider, Rechts- und
   KI-Felder, Crawl-Status, Feld-Erzeugung). Unter `[crawler_tabelle]` die eigenen Spaltennamen
   den festen Schlüsseln zuordnen. Welche Schlüssel es gibt und wer sie sieht, steht in
   [`profiles/README.md`](profiles/README.md#crawler-tabelle).
4. Startdaten unter `profiles/<name>/daten/` ablegen: `crawler.csv` und `korrekturen.csv`. Für den
   Anfang genügt je die Kopfzeile; ohne beide Dateien baut die Team-Instanz keine Daten.
5. Lokal prüfen: `QE_PROFILE=<name> QE_TEAM_PASSWORD=geheim python serve.py`, dann im Audit
   **Daten aktualisieren**.
6. Auf main bringen. GitHub baut das Image mit dem neuen Profil.
7. Auf dem Server eine eigene Instanz anlegen (eigener Ordner bzw. eigenes Projekt im Docker-Panel,
   damit Volume und Container getrennt bleiben) und in deren `.env` setzen:
   `QE_PROFILE=<name>`, `QE_SEED_URL=https://raw.githubusercontent.com/janschachtschabel/quellenpanel/main/profiles/<name>/daten`
   und einen freien `PORT`. Bereitstellen.

Danach pflegt das Team Korrekturen, Black- und Whitelist und die Crawler-Tabelle im
Bearbeitungsbereich dieser Instanz. Grenzen: Die Arten von Feldern und ihre Stufe (öffentlich,
Partner, Team) sind im Code festgelegt (`backend/field_policy.py`). Eine Spalte, die keinem
Schlüssel entspricht, wird nicht angezeigt; dafür braucht es eine kleine Code-Änderung.

## Entwicklung und Tests

```bash
python -m ruff check .                         # Lint (im Repo-Wurzelverzeichnis)
cd backend && python -m pytest -q              # Backend
cd frontend && npm test -- --watch=false       # Frontend (vitest)
cd frontend && npm run lint:design             # Design-Regeln (edu-sharing)
```

Aufbau: `backend/` (FastAPI, Datenaufbereitung, Rollen und Stufen), `frontend/` (Angular 22,
Material, Widgets), `profiles/` (Repository-Profile), `deploy/` (Compose, Helm, Messung), `docs/`.
Wie die Daten entstehen: [`docs/datenaufbereitung.md`](docs/datenaufbereitung.md). Die CI
(`.github/workflows/ci.yml`) prüft zusätzlich `pip-audit`, `npm audit`, Helm, kubeconform,
Alarmregeln und die Versionsgleichheit.
