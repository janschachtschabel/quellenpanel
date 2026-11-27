# Changelog

Je Release die Änderungen und die **Hinweise für den Betrieb**. Format nach
[Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach SemVer. Die Versionen
0.3.0 bis 0.6.0 waren Zwischenstände auf dem Weg zu 1.0.0 und wurden nicht als Release getaggt.

## [1.0.0] – 2026-11-27

Erstes produktives Release: aus der Einzel-App wird ein Dienst nach dem Diensteleitfaden.
Zusammenfassung der Etappen 1 bis 7 (Details in den Abschnitten darunter).

### Hinweise für den Betrieb

Wer von der Version vor dem Umbau kommt (ein Container, Daten im Image, Port 8080):

- **Daten liegen nicht mehr im Image.** Die Team-Instanz baut sie im Volume `/data`
  (`QE_DATA_DIR`) auf; beim ersten Start optional aus Startdaten unter `QE_SEED_URL`. Bis dahin
  antworten Datenrouten mit 503 „Daten werden aufgebaut“. Volume vor dem ersten Start anlegen
  (Helm: PVC 2 Gi, nur bei `role: team`).
- **Drei Instanzen statt einer.** `QE_ROLE` = `team`, `partner` oder `public`. Partner und
  Öffentlich holen ihren Export von `QE_EXPORT_SOURCE` alle `QE_EXPORT_POLL_MINUTES`. Die
  Variable hat im Code keinen Standard (Helm und Compose setzen den Team-Port 9090); ohne sie
  antworten Partner und Öffentlich mit 503. Ohne `QE_ROLE` läuft eine Instanz als `team`
  (lokale Entwicklung); im Betrieb die Rolle immer setzen und die Team-Instanz hinter VPN/SSO legen. `QE_PUBLIC_ONLY=1` gilt nur noch als Übergangsname für
  `QE_ROLE=public`.
- **Zweiter Port 9090** für `/health`, `/ready`, `/metrics` und die Exporte. Nie veröffentlichen.
  Liveness und Startup fragen `9090/health`, die Readiness `8080/api/health` (fragt keinen anderen
  Dienst; Team immer bereit, Partner/Öffentlich sobald ihr Export geladen ist). `/ready` dient nur
  dem Monitoring.
- **Image-Tag `latest` entfällt.** Images heißen nach der Version (`1.0.0`, `1.0`) oder nach
  Branch und Commit. Deployments auf einen Versions-Tag umstellen.
- **Port-Variable:** `PORT` entfällt, jetzt `QE_PORT` (8080) und `QE_INTERNAL_PORT` (9090);
  `QE_HOST` setzt die Bind-Adresse (Standard `0.0.0.0`).
- **Neue Secrets:** `QE_SESSION_SECRET` (Team-Sitzung übersteht Neustarts; leer = Abmeldung bei
  jedem Neustart). `QE_TEAM_PASSWORD` und `QE_TIER1_PASSWORD` bleiben; ohne
  `QE_TIER1_PASSWORD` ist Stufe 1 auf dem Partner zu (fail-closed).
- **Neue Variablen:** `QE_PROFILE` und `QE_PROFILES_DIR` (Repository-Profil, Standard `wlo`),
  `QE_FRAME_ANCESTORS` (wer die iframe-Widgets einbetten darf; Helm `config.frameAncestors`),
  `QE_THUMB_CACHE_MB` (Zwischenspeicher der Vorschaubilder, Standard 16 MiB statt fest 128 MiB), `TRUST_PROXY` (Client-IP aus
  `X-Forwarded-For`, nur hinter einem Proxy, der den Header überschreibt), `LOG_FORMAT`
  (`json`/`text`) und `LOG_LEVEL`. Unverändert: `QE_REPO_URL`, `QE_SEARCH_URL`,
  `QE_ALLOWED_ORIGINS`, `QE_AUTO_REFRESH_HOUR`, `QE_RENAME_UNREP_BQ` (Umbenennung nicht
  repräsentierter Bezugsquellen, `0` = aus).
- **Ressourcen** je Rolle stehen gemessen in den Helm-Values (`docs/messung.md`); das Team-Limit
  nach der ersten Messung des Live-Abrufs im Cluster prüfen.
- **Container laufen read-only** als uid 10001 mit beschreibbarem `/tmp` (Compose: tmpfs, Helm:
  `emptyDir`); nur das Team schreibt nach `/data`.
- **Image-Tags je Pipeline:** GitHub → Docker Hub `1.0.0`/`1.0`; GitLab → `docker.edu-sharing.com`
  `1.0.0` und `v1.0.0`, Chart `quellenpanel` 1.0.0 (früher `edu_sharing-projects-wlo-quellenpanel`;
  im Chart-Repo erscheint der neue Name).
- **NetworkPolicy in allen drei Rollen an**, jetzt auch ausgehend: nur DNS (53), HTTPS (443) und für
  Partner/Öffentlich der Team-Port 9090. Wer die Exporte über einen anderen Port holt, ergänzt
  `networkPolicy.extraEgress`. `networkPolicy.ingressNamespace` auf den Namespace des
  Ingress-Controllers setzen, dann erreicht nur er Port 8080.
- **Sauberes Beenden:** `preStop` 5 s (`preStopSleepSeconds`), danach 20 s für laufende Anfragen;
  `terminationGracePeriod` 30 s nicht senken.

### Hinzugefügt

- Übergabe-Doku: Steckbrief, Zeile der Kompatibilitätsmatrix, Übergabepaket
  (`docs/uebergabe/`), Ressourcenmessung mit Lastskript (`deploy/messung/last.py`).
- Schlanke Einbettung: `kopf`, `fuss`, `filter`, `rahmen` = `aus`, feste `ansicht`
  (`kacheln`/`liste`), `hintergrund` und `farbe` als `#rrggbb`; gleich als Attribut am Element, als
  Parameter der iframe-Seiten und der App. Übersicht aller Optionen in `docs/widgets.md`, Testseite
  `/widgets/beispiele/schlank.html`.
- README auf Deutsch und Englisch (`README.en.md`) mit Installation, Nutzung, Zugangsstufen und
  ihrem Schutz, Bearbeitungsbereich und Datenabruf über die API.
- OpenAPI: Beschreibung für jeden Parameter, Beispielantworten für die öffentlichen Leserouten,
  Fehlerantworten je Route.
- Dependabot (pip, npm, Actions, Basis-Images); GitLab prüft jetzt Versionsgleichheit, Tag und
  `helm lint` je Rolle.

### Geändert

- `info.description` der OpenAPI auf zwei Sätze gekürzt (Kurzbeschreibung des Steckbriefs).
- Helm-Requests und -Limits je Rolle aus der Messung.
- `GET /api/health` dient als Readiness-Probe (vorher `9090/ready`) und wird nicht mehr geloggt
  oder gezählt.
- Fehlerklassen: 503 ohne Export und alle 429 (auch Login-Drossel und Vorschaubilder) mit
  `Retry-After`; ein 4xx des Repositorys wird 502 ohne Wiederholungshinweis.
- Suchbegriff-Pseudonym im Log als HMAC mit Schlüssel je Prozess statt reinem SHA-256; unbekannte
  HTTP-Methoden erscheinen in Log und Metriken als `OTHER`.
- Vorschaubild-Zwischenspeicher 16 MiB statt 128 MiB (`QE_THUMB_CACHE_MB`).
- Paginator auf Deutsch und Englisch („1–25 von 3.721“).
- `docker-compose.build.yml` im Wurzelverzeichnis startet eine Team-Instanz mit Volume (Entwicklung).

### Hinzugefügt (Server mit Traefik)

- `docker-compose.yml` im Hauptordner für einen Docker-Server mit vorhandenem Traefik-Proxy: drei
  Instanzen aus einem Image, das aus diesem Repository gebaut wird; Traefik-Labels je Instanz
  (`DOMAIN`, `PARTNER_DOMAIN`, `TEAM_DOMAIN`), keine veröffentlichten Ports, kein externes Netz. Der
  erste Start braucht keine Variable; Startdaten kommen aus `profiles/wlo/daten`. Vorlage `.env.example`.
  Ohne Domain direkt erreichbar über `PORT` (18080) und `PARTNER_PORT` (18081); der Team-Port
  `TEAM_PORT` (18082) lauscht nur auf dem Server, außer `TEAM_BIND` ist gesetzt.
- `TRUST_PROXY` wertet `X-Forwarded-For` nur aus, wenn die Anfrage von einer privaten Adresse kommt.
- Ohne `QE_SESSION_SECRET` legt das Team einmal `session.key` im Datenordner an; Anmeldungen
  überstehen so Neustarts.
- Die bisherige Entwicklungsdatei heißt jetzt `docker-compose.build.yml`.

### Abhängigkeiten aktualisiert (Dependabot)

- Angular und Angular Material 22.3 (mit TypeScript 6.0, Vitest 5, happy-dom 21, tslib 2.9). Die
  Komponenten behalten mit `ChangeDetectionStrategy.Eager` das bisherige Verhalten, `provideHttpClient`
  nutzt ausdrücklich `withXhr()`.
- FastAPI 0.165, uvicorn 0.54, pytest 9.2, PyYAML 6.0.4, ruff 0.17 (Regelauswahl in `ruff.toml` jetzt
  fest auf E4/E7/E9/F, wie bisher). Die OpenAPI der partner- und public-Instanz blendet die Team-Pfade
  jetzt über ihr Präfix aus, weil FastAPI eingebundene Router nicht mehr auflöst.
- GitHub-Actions: checkout 7, setup-node 7, setup-python 7, setup-helm 5, build-push 7, setup-buildx 4.
- Nicht übernommen: TypeScript 7 (Angular 22 verlangt 6.0) und Node 25 (keine LTS-Linie); Dependabot
  schlägt beides nicht mehr vor.

### Behoben (Abschluss-Audit)

- Ohne `korrekturen.csv` und `crawler.csv` startet kein Datenaufbau mehr: vorher erschien eine
  Neuinstallation ohne `QE_SEED_URL` mit Blacklist-Quellen und ohne Korrekturen. Die Oberfläche
  zeigt den Grund an.
- Der Knopf „Daten aktualisieren“ ruft `/jobs/refresh` auf der richtigen Adresse auf.
- Passwörter in den Kopfzeilen `x-team-password` und `x-tier1-password` sind gedrosselt wie der
  Login (8 Fehlversuche je Adresse in 5 Minuten).
- Ein Import mit Vermerk ersetzt keinen Blacklist-Eintrag derselben Quelle mehr.
- `POST /jobs/refresh` und `POST /api/admin/reload` prüfen die Herkunft (`Origin`) wie die
  übrigen Team-Schreibzugriffe; das Neuladen wartet auf einen laufenden Datenaufbau.
- Live-Inhalte gesperrter Quellen gibt es auf der Team-Instanz nur mit Team-Login.
- CSV-Downloads (`/api/export.csv`, `/api/protokoll.csv`) setzen vor Zellen mit `=`, `+`, `-`, `@`
  ein `'`, damit Tabellenprogramme sie nicht als Formel ausführen.
- Filterwerte im Export stammen nur aus Quellen, die der Export auch zeigt.
- `QE_EXPORT_SOURCE` darf weitere geschweifte Klammern enthalten; ersetzt wird nur `{tier}`.

## [0.6.0] – 2026-11-27 · Look

### Geändert

- Oberfläche mit den edu-sharing-Tokens (Farben, Schrift Open Sans, Abstände, Schatten),
  Kacheln nach der edu-sharing-Anatomie, Kopfzeile für schmale Fenster.
- Markenfarbe aus dem Profil (`branding` in `/api/capabilities`); helle Markenfarben werden für
  Text automatisch abgedunkelt, damit der Kontrast reicht.
- Texte in Sie-Form, Leer- und Fehlertexte nennen den nächsten Schritt.

### Hinzugefügt

- A11y-Audit aller Ansichten (WCAG 2.1 AA), Design-Regeln als CI-Schritt (`lint:design`).

### Hinweise für den Betrieb

- Keine neuen Variablen. Die Markenfarbe kommt aus `profil.toml` (`[branding] primary`).

## [0.5.0] – 2026-11-27 · Widgets

### Hinzugefügt

- Widgets zum Einbetten: Quellenliste, Top 10 je Fach, Kennzahl, eine Quelle, Statistik; Kacheln
  und Panel als nachgeladenes Element; iframe-Seiten unter `/embed/<name>`; Testseiten unter
  `/widgets/`. Öffentliche Kennzahl `GET /api/kennzahl`.

### Hinweise für den Betrieb

- `QE_FRAME_ANCESTORS` legt fest, welche Seiten die iframe-Widgets einbetten dürfen (CSP
  `frame-ancestors`, Quellen durch Leerzeichen getrennt); leer = überall auf Partner und
  Öffentlich, nur dieselbe Herkunft auf dem Team.

## [0.4.0] – 2026-11-26 · Korrektur-Verwaltung

### Hinzugefügt

- Team-Ansicht „Korrekturen“: Tabelle, Anlegen/Ändern/Löschen, Import aus CSV/JSON/XLSX mit
  Vorschau, Download, Verlauf; Upload der Crawler-Tabelle; „Auf Blacklist“ und „Beschreibung
  ergänzen“ im Steckbrief.

### Hinweise für den Betrieb

- Neue Dateien im Volume: `korrekturen.csv`, `korrekturen-verlauf.csv`, Sicherungen
  `korrekturen-<zeit>.csv` und `crawler-<zeit>.csv` (werden nicht automatisch gelöscht).
- Uploads bis 5 MB: am Ingress des Teams `proxy-body-size` mindestens `6m`.

## [0.3.0] – 2026-11-26 · Betrieb nach Leitfaden

### Hinzugefügt

- JSON-Logs (`LOG_FORMAT`, `LOG_LEVEL`), B3-Tracing, eine Logzeile je Anfrage.
- Interner Port 9090 mit `/health`, `/ready`, `/metrics` und den Exporten.
- Einheitliches Fehler-JSON mit `trace_id`; OpenAPI nur mit den Pfaden der Rolle.
- Signierte Team-Sitzung (`QE_SESSION_SECRET`), `TRUST_PROXY`.
- Helm-Chart mit Values je Rolle, ServiceMonitor, PrometheusRule, NetworkPolicy; Compose mit drei
  Diensten; CI mit Audits, `helm lint --strict` und `kubeconform`.

### Entfernt

- Daten im Image, Vercel-Pfad, Image-Tag `latest`, Variable `PORT`.

### Hinweise für den Betrieb

- Erststart braucht ein Volume unter `/data` (`QE_DATA_DIR`) und optional `QE_SEED_URL`.
- Ports über `QE_PORT` und `QE_INTERNAL_PORT`, Bind-Adresse über `QE_HOST`.

## [0.2.0] – 2026-11-26 · Rollen und Exporte (ohne Versionsnummer im Code)

### Hinzugefügt

- `QE_ROLE` (team, partner, public) begrenzt die Zugangsstufe. Das Team schreibt Exporte je
  Stufe; Partner und Öffentlich laden nur ihren Export von `QE_EXPORT_SOURCE` (ETag, alle
  `QE_EXPORT_POLL_MINUTES`) und behalten bei Fehlern den letzten gültigen Stand.

### Hinweise für den Betrieb

- `QE_PUBLIC_ONLY=1` entspricht jetzt `QE_ROLE=public`.

## [0.1.0] – 2026-11-26 · Kern und Repository-Profil (ohne Versionsnummer im Code)

### Geändert

- Generischer Kern; alles Repository-Spezifische (Felder, Sonderfälle, Korrekturen,
  Crawler-Tabelle) liegt im Profil `profiles/wlo/`. Korrekturen im Langformat.

### Hinweise für den Betrieb

- Profil-Auswahl mit `QE_PROFILE` (Standard `wlo`) aus `QE_PROFILES_DIR` (Standard
  `profiles/` im Repo bzw. Image).
