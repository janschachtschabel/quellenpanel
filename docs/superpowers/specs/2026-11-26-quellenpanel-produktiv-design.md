# Quellenpanel produktionsreif machen – Design

Stand: 26.11.2026 · Auftraggeber: Jan · Status: Entwurf zur Freigabe

## 1. Absicht

Quellenpanel zeigt, welche Inhaltsquellen in WirLernenOnline (WLO) stecken. Es soll vom
funktionierenden Prototyp zu einem Dienst werden, den Team 6 (T6) nach dem Diensteleitfaden
übernehmen und betreiben kann, und der drei Zielgruppen bedient:

| Use-Case | Zielgruppe | Stufe | Zugang |
|---|---|---|---|
| Öffentliche Quellenliste auf der Webseite | alle | 0 | offen, einbettbar |
| Quellensteckbriefe-App | Partner | 1 | Passwort (erste Schwelle) |
| Interne Audit-Quelle | WLO-Team | 2 | nur intern erreichbar + Team-Passwort |

Dazu kommen: ein generischer Kern, bei dem alles WLO-Spezifische in einem einheitlichen
**Profil** liegt; mehrere sicher einbettbare **Widgets** (darunter eine einfache Liste); und ein
Look nahe am **edu-sharing-11-Designsystem**.

## 2. Ziele, Nicht-Ziele, Anti-Ziele

**Ziele**
- Diensteleitfaden erfüllen, soweit er für einen Dienst ohne LLM und ohne b-api gilt (Abschnitt 7).
- Ein Image, drei Instanzen (Rollen) mit getrennten Datenbeständen.
- WLO-Spezifika (Metadatenfelder, Vokabulare, Spider-Sonderfälle, Korrekturen) in `profiles/wlo/`;
  der Kern läuft mit einem anderen Profil gegen ein anderes edu-sharing.
- Korrekturen als Semikolon-CSV, im Team-Bereich bearbeitbar, mit Import fremder Dateien.
- Widgets: einfache Liste, Kacheln, Einzel-Steckbrief, Statistik, Gesamt-App; jeweils als Custom
  Element und als iframe-Seite.
- UI auf edu-sharing-Tokens mit WLO-Branding.

**Nicht-Ziele**
- Kein LLM, keine b-api-Delegation (Quellenpanel ruft keine b-api-Funktion auf).
- Keine personenbezogene Anmeldung (kein edu-sharing-/Keycloak-Login) in dieser Runde.
- Keine Datenbank; kein horizontales Skalieren der Team-Instanz.
- Keine Änderung der fachlichen Merge-Logik (Join-Präzedenz, Flags) außer dort, wo WLO-Sonderfälle
  ins Profil wandern.

**Anti-Ziele** (wäre ein Fehlschlag, auch wenn es technisch läuft)
- Die öffentliche Instanz hält interne Felder oder Datenproblem-Flags im Speicher oder auf Platte.
- Ein eingebettetes Widget verändert Styles der Gastseite oder schickt Cookies mit.
- Nach dem Umbau ergibt derselbe Rohdatenabruf eine andere `truth.json` als vorher (ohne bewusste,
  dokumentierte Änderung).
- Die Redaktion braucht Git, um eine Korrektur einzutragen.

## 3. Ausgangslage (Analyse vom 26.11.2026)

- Backend FastAPI (~3.900 Zeilen), Frontend Angular 21 + Material (~3.900 Zeilen), 44 Backend- und
  41 Frontend-Tests grün. Stufenmodell 0/1/2 mit `QE_PUBLIC_ONLY` sauber gelöst (`tiers.py`,
  `field_policy.py`, `serialize.py`).
- WLO-Spezifika verteilt: `truth_loaders.py` (`ccm:oeh_*`-Qualitätsfelder, Feldnamen),
  `fetcher.py` (NGSearch-Pfad `mds_oeh`, LRT-„Quelle“-URI, Vokabular-URL), `config.WLO_SPIDERS`,
  `truth_record.py` (`wirlernenonline_spider`, Legacy-Bindung), `truth_text.IGNORE_SPIDERS`.
- Kuratiertes in drei Formaten: `inputs/quellen_korrektur.csv` (361 Black-/Whitelist-Zeilen +
  BQ-/Spider-Override), `source_supplements.json` (37 Beschreibungen/Bilder),
  `inputs/datencrawler.csv` (179 Spalten, Export der Crawler-Tabelle).
- Lücken zum Leitfaden: Klartext-Logs ohne Trace-ID; ein Port (Health/OpenAPI öffentlich, keine
  Metriken); Team-Pfade in der OpenAPI; `truth.json` (5 MB) im Image; Rebuild schreibt in den
  Container; Team-Sitzungen im Prozess-Speicher; Chart ohne NetworkPolicy/PrometheusRule/PVC;
  kein Steckbrief.
- Frontend: ein Custom Element `<wlo-quellenpanel>` (gesamte App), eigener Material-3-Look.
- Backup des Ausgangsstands: Branch `backup/vor-umbau-2026-11-26`.

## 4. Getroffene Entscheidungen (Jan, 26.11.2026)

1. **Getrennte Instanzen aus einem Image.** Öffentliche Instanz enthält nur öffentliche Daten,
   Partner-Instanz mit Passwort, Team-Instanz nur intern erreichbar plus Team-Passwort. Betrieb
   ohne b-api, im Steckbrief begründet.
2. **Korrekturen als Semikolon-CSV**, zusätzlich ein Verwaltungsbereich in der Team-Stufe zum
   Bearbeiten/Ergänzen; externe maschinenlesbare Dateien (meist CSV) leicht einspielbar.
3. **Speicherort: CSV-Dateien auf einem Volume der Team-Instanz** (ein Pod, Recreate).
4. **Schrittweiser Umbau im bestehenden Code, je Etappe ein PR.**
5. Performance: Korrekturen werden beim Start und nach Änderungen in den Speicher geladen; die
   öffentliche/Partner-Instanz liefert einen vorab erzeugten Export aus dem Speicher mit ETag.
6. **Crawler-Tabelle** pflegt das Datenteam in unregelmäßigen Abständen → Upload im Team-Bereich
   (mit Prüfung der Spaltenzuordnung), kein Release nötig.
7. **Widgets ohne Login.** Wie im heutigen Widget sind Zusatzinfos optional per Passwort
   zuschaltbar. Extern ausgespielte Widgets laufen ohne Passwortschutz; **Steckbrief-Erzeugung und
   Fehler-Audit sind schützenswert** und nie ohne Passwort erreichbar.
8. **Kein Vercel mehr.** Ausgeliefert wird nur noch ein Container-Image (Docker) mit Helm-Chart
   nach Dienste-Steckbrief. Eine ältere, ähnliche Version läuft noch produktiv; sie bleibt bis zur
   Ablösung unberührt, deshalb ist kein Kompatibilitätszwang für API-Pfade nötig. Das Element
   `<wlo-quellenpanel>` behält trotzdem Namen und Attribute (`api-base`, `with-credentials`).


## 5. Ansätze (betrachtet)

| Frage | Betrachtet | Gewählt | Warum |
|---|---|---|---|
| Betrieb/Zugang | (a) getrennte Instanzen · (b) eine Instanz wie heute · (c) Team-Login über edu-sharing | (a) | interne Daten nie auf dem öffentlichen Server; keine Abhängigkeit von b-api/T6 |
| Korrektur-Pflege | (a) Tabelle/CSV · (b) YAML per Git · (c) nur Editier-UI | (a) + UI aus (c) | Redaktion ohne Git; UI für das Team |
| Speicher | (a) CSV auf Volume · (b) PostgreSQL · (c) Commit ins Repo | (a) | wenige Nutzer, ein Pod, CSV bleibt die Wahrheit |
| Vorgehen | (a) schrittweise, PR je Etappe · (b) neuer Kern daneben | (a) | Datenkern ist getestet; App bleibt jederzeit lauffähig |

## 6. Architektur

### 6.1 Rollen

Ein Image, Rolle per `QE_ROLE`:

| Rolle | Max. Stufe | Daten | Schreibt | Erreichbar |
|---|---|---|---|---|
| `team` | 2 | Rohabruf + Profil + Korrekturen → `truth.json` → Exporte je Stufe | Volume `/data` | nur intern (Ingress intern/VPN, NetworkPolicy) |
| `partner` | 1 | nur Exporte Stufe 0 + 1 | nichts (nur `/tmp`) | öffentlich; Basisansicht offen, Details + Steckbrief-Erzeugung (PDF) nur mit Partner-Passwort |
| `public` | 0 | nur Export Stufe 0 | nichts (nur `/tmp`) | öffentlich, einbettbar |

`QE_PUBLIC_ONLY` entfällt zugunsten von `QE_ROLE=public` (bleibt als Alias für eine Übergangszeit).
Die Stufen-Obergrenze ergibt sich aus der Rolle; `tiers.effective_tier` bleibt die einzige Stelle,
die sie anwendet.

### 6.2 Datenfluss

```
Team-Instanz
  ① Abruf (fetcher, generisch, Felder/Endpunkte aus dem Profil)  → /data/raw/
  ② Profil (profiles/<id>/): profil.toml + crawler.csv           ┐
  ③ Korrekturen /data/korrekturen.csv (Start: Kopie aus Profil)   ├→ Merge (truth*) → /data/truth.json
  ④ Exporte: /data/exports/stufe0.json, stufe1.json (+ .etag)    ┘   (nur serialisierte Felder der Stufe,
                                                                     inkl. vorgerechneter Statistik/Filter)
  interner Port: GET /internal/exports/stufe{0,1}.json

Partner-/Öffentliche Instanz
  beim Start und alle QE_EXPORT_POLL_MINUTES: Export laden von QE_EXPORT_SOURCE
  (URL der Team-Instanz ODER Dateipfad, z. B. gemountetes Volume) → im Speicher, letzter
  gültiger Stand bleibt bei Fehlern; Kopie in /tmp für schnellen Neustart im selben Pod.
  live pro Anfrage weiterhin: Beispielinhalte (/api/sources/{id}/contents), Vorschaubild-Proxy.
```

Der Export Stufe 0 wird mit dem **gleichen** Serializer erzeugt, der heute Stufe 0 ausliefert;
dadurch kann die öffentliche Instanz nichts zeigen, was der Stufe-0-Serializer nicht ausgibt. Ein
Test prüft, dass kein Feld aus `field_policy.INTERNAL_*`/`INTERNAL_FLAGS` im Export vorkommt.

### 6.3 Profil

```
profiles/wlo/
  profil.toml        Repo-/Such-URL, MDS-ID, NGSearch-Kriterium „ist Quelle“, Vokabular-URL,
                     Feldzuordnung (Kernfeld → edu-sharing-Property, z. B. publisher →
                     ccm:oeh_publisher_combined), Qualitätsfelder, Migrations-/Ignore-Spider,
                     Spaltenzuordnung der Crawler-Tabelle, Branding (Name, Logo, Primärfarbe)
  daten/crawler.csv      Export der Crawler-Tabelle (heute inputs/datencrawler.csv) – nicht im Image
  daten/korrekturen.csv  Startstand der Korrekturen (Langformat, s. u.) – nicht im Image
```

- `QE_PROFILE=wlo` (Standard) wählt das Profil. TOML, weil Python es ohne Abhängigkeit liest
  (`tomllib`) und Entwickler es pflegen; die Redaktion pflegt nur CSV.
- Der Kern (`fetcher`, `truth_loaders`, `truth_record`, `truth`) liest Feldnamen, URIs und
  Sonderfälle nur noch aus dem Profil. Kein `ccm:oeh_*`, kein `wirlernenonline` mehr im Kern
  (per Test mit `grep` abgesichert).
- `profiles/beispiel/` als minimales zweites Profil (nur Pflichtfelder) beweist die Neutralität in
  einem Test.

### 6.4 Korrekturen (Langformat)

Datei `korrekturen.csv`, UTF-8 mit BOM (Excel), Trennzeichen `;`:

```
Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am
node;4c1df1cc-…;whitelist;;MaterialdatenbankChemie;migration;2026-11-26
node;16489b8d-…;spider_setzen;zum_spider;;migration;2026-11-26
bezugsquelle;youtube;beschreibung;Auf YouTube findest du …;;migration;2026-11-26
bezugsquelle;youtube;vorschaubild;https://…/preview?nodeId=…;;migration;2026-11-26
```

- `Typ`: `node` · `spider` · `bezugsquelle`. `Aktion`: `blacklist` · `whitelist` ·
  `bezugsquelle_setzen` · `spider_setzen` · `beschreibung` · `vorschaubild` (Liste im Profil
  erweiterbar, Kern kennt die Wirkung).
- Einmaliges Migrationsskript überführt `quellen_korrektur.csv` + `source_supplements.json`
  verlustfrei; Test: Merge mit alten Dateien = Merge mit migrierter Datei.
- Validierung beim Laden: unbekannter Typ/Aktion, doppelte widersprüchliche Zeilen, ungültige
  UUID → Zeile wird übersprungen und im Audit-Bereich als Fehler gelistet; App startet trotzdem.

### 6.5 Team-Bereich „Korrekturen“

- Tabelle mit Suche/Filter, Zeile anlegen/ändern/löschen, direkt aus dem Steckbrief einer Quelle
  („auf Blacklist“, „Beschreibung ergänzen“).
- **Import**: CSV (`;` oder `,`, Erkennung), JSON (Liste von Objekten) und XLSX hochladen →
  Spaltenzuordnung (automatisch nach Namen, manuell änderbar) → Vorschau neu/geändert/fehlerhaft →
  übernehmen. Modus „ergänzen“ oder „ersetzen“.
- **Export**: aktuelle `korrekturen.csv` herunterladen.
- **Verlauf**: jede Änderung als Zeile in `/data/korrekturen-verlauf.csv` (wer: frei eingegebenes
  Kürzel, wann, alt, neu); vor jedem Ersetzen eine datierte Sicherung.
- Schreiben atomar (temp-Datei + rename) mit Prozess-Sperre. Nach dem Speichern: Merge im Speicher
  neu rechnen und Exporte neu schreiben (ohne Live-Abruf; Sekundenbereich).

### 6.6 Widgets und Einbettung

Ein Skript `quellenpanel-widgets.js` registriert:

| Element | Inhalt |
|---|---|
| `<wlo-quellen-liste>` | **einfach**: Suchfeld + kompakte Liste (Name, Fächer, Anzahl Inhalte, Link), keine Filterleiste, keine Popups |
| `<wlo-quellen-kacheln>` | Kacheln mit Filtern (heutige Hauptansicht) |
| `<wlo-quelle quelle="…">` | Steckbrief einer Quelle |
| `<wlo-quellen-statistik>` | Statistik |
| `<wlo-quellenpanel>` | gesamte App |

Gemeinsame Attribute: `api-base`, `fach`, `bildungsstufe`, `suche` (Vorbelegung), `max`,
`sprache`. Jedes Element zusätzlich als iframe-Seite `/embed/<name>?…` (transparenter
Hintergrund, Höhe per `postMessage` an die Elternseite nur auf deren Anforderung – Muster aus dem
edu-sharing-Embed-Skill).

Sicherheitsregeln: öffentliche Widgets ohne Cookies (`credentials: omit`); `with-credentials` nur
in der Partner-/Team-Instanz; kein Shadow DOM, aber **keine** globalen Selektoren auf
`html`/`body`/`:root` (alle Styles unter dem Element-Selektor, Overlays mit explizitem Font und
z-index); externe Links `rel="noopener"` + „öffnet in neuem Tab“; CSP-tauglich (kein
`eval`/Inline-Script; Schriften lokal statt Google Fonts); `frame-ancestors` für `/embed/*` per
Env (`QE_FRAME_ANCESTORS`). Dokumentation mit Einbau-Beispielen für Betreiber von Gastseiten.

### 6.7 Look

edu-sharing-Tokens aus `DESIGN.md` der UX-Skills als CSS-Variablen, WLO-Branding (primary
`#003b7c`, accent `#e4f700`) aus dem Profil; Open Sans lokal; Kachel-Anatomie und Abstände nach
`node-entries-anatomy`/`tokens`; Texte in Sie-Form nach `write-copy`. Prüfung mit
`lint-design-rules.mjs` und dem A11y-Audit (`audit-accessibility`, WCAG 2.1 AA).

## 7. Diensteleitfaden – Umsetzung

| Kapitel | Umsetzung |
|---|---|
| Dienst-ID | `quellenpanel` (Logs `service`, `OTEL_SERVICE_NAME`, Chart, Image) |
| 1 API | OpenAPI aus FastAPI mit `info.title/description`, Beispielen je Endpunkt; **nur öffentliche Pfade der jeweiligen Rolle** (Team-Pfade nur in der Team-Instanz); Fehler als JSON mit `trace_id`; 4xx/5xx sauber getrennt, `retryAfter` bei Abhängigkeits-429/5xx; keine Header vom Client außer den Passwort-Headern (begründet); Antwortzeiten je Endpunkt im Steckbrief. Repository-Unabhängigkeit über das Profil. |
| 2.1 LLM | entfällt (kein LLM) |
| 2.2 b-api | entfällt: „Betrieb ohne b-api“ begründet (öffentliche Webseiten-Daten, kein Personenbezug, anonymer Lesezugriff, den die b-api nicht bietet); eigene Auth = Rollen + Passwörter; Env und Auth-Konzept dokumentiert |
| 2.3 Logs/Tracing | JSON nach stdout (`timestamp, level, service, trace_id, span_id, message`), Klartext per `LOG_FORMAT=text`, `LOG_LEVEL`; B3 lesen/prüfen/weitergeben an Repository und Team-Instanz, sonst neu anlegen; `x-client-trace-id` durchreichen; eine Zeile je Anfrage mit Routenklasse statt Pfad; uvicorn-Access-Log aus; keine Passwörter/Header-Werte; Suchbegriffe nur pseudonymisiert |
| 3 Betrieb | Port 8080 öffentlich (API, SPA, Widgets), Port 9090 intern (`/health`, `/ready`, `/metrics`); Readiness ohne Abhängigkeiten; `/ready` prüft Repository/Export-Quelle höchstens alle 30 s; Prometheus-Basis- und App-Metriken (Rebuild-Dauer/-Erfolg, Alter der Daten, Export-Abrufe, Repo-Fehlerrate); `X-Forwarded-For` nur mit `TRUST_PROXY`; Zustand: Team-Instanz 1 Pod mit RWO-Volume (Recreate), Partner/Öffentlich zustandslos und skalierbar; Team-Sitzung als signiertes Cookie (HMAC, `QE_SESSION_SECRET`) statt Prozess-Speicher; SIGTERM sauber, laufender Rebuild schreibt Status; Stand der Daten in `/health` |
| 3 Große Daten | `truth.json` nicht mehr im Image: Team erzeugt sie auf dem Volume; erster Start ohne Volume-Daten → einmaliger Abruf (Status „Daten werden aufgebaut“), optional Seed per `QE_SEED_URL` |
| 3 Daten-Updates | nächtlicher Rebuild **im Team-Pod** (`QE_AUTO_REFRESH_HOUR`), weil das RWO-Volume nur dort gemountet ist; Begründung im Steckbrief; Alarm „seit 26 h kein erfolgreicher Rebuild“ |
| 4 Build/Helm | Dockerfile multi-stage, nicht root, read-only rootfs + `/tmp`, Basis-Image per Digest; Chart `deploy/helm/quellenpanel`, `version = appVersion` (Test), Werte für alle Env mit `## @param`, `role`-Wert + Beispiel-Values `values-public.yaml`, `values-partner.yaml`, `values-team.yaml`; PVC nur bei `team`; NetworkPolicy (Standard aus), ServiceMonitor, PrometheusRule (mit `promtool test rules`), Pod Security „restricted“; CI: lint, Tests, `pip-audit`/`npm audit`, `helm lint --strict`, `kubeconform`, Tag = Version in `package.json`/`pyproject`; Compose-Referenz mit drei Diensten |
| 5 Kestra | entfällt |
| 6 Übergabe | `docs/uebergabe/steckbrief.md`, Zeile Kompatibilitätsmatrix, gemessene Ressourcen (Leerlauf/warm/Spitze je Rolle), Image-Größe, Architekturübersicht, Env-/Secret-Liste, Changelog; Ansprechperson/Vertretung trägt Jan ein |

## 8. Etappen (je ein PR, App nach jeder Etappe lauffähig)

1. **Kern und WLO-Profil** – `profiles/wlo/`, Profil-Lader, Kern liest Felder/URIs/Sonderfälle aus
   dem Profil, Korrekturen im Langformat + Migrationsskript. Abnahme: Golden-Test – aus denselben
   Roh-Caches entsteht byte-gleich dieselbe `truth.json` (Fixture-Ausschnitt im Repo + einmaliger
   Vollvergleich lokal); kein WLO-Feldname im Kern.
2. **Rollen und Exporte** – `QE_ROLE`, Exporte je Stufe, Partner/Öffentlich laden nur Export, ETag;
   No-Leak-Test auf dem Export.
3. **Betrieb nach Leitfaden** – Vercel-Pfad entfernen (`vercel.json`, `backend/api/`); Ports, Logs/Tracing, Metriken, OpenAPI je Rolle, Fehlerformat,
   signierte Sitzung, Daten aus dem Image, Dockerfile/Chart/Compose/CI.
4. **Korrektur-Verwaltung** – Team-Bereich (Tabelle, Import mit Vorschau, Export, Verlauf) und
   Upload der Crawler-Tabelle durch das Datenteam.
5. **Widgets** – fünf Elemente + iframe-Seiten + Einbau-Doku + Testseiten (leere Seite, Gastseite
   mit eigenen Styles).
6. **Look** – edu-sharing-Tokens, Kachel-Anatomie, Texte, A11y-Audit.
7. **Übergabe** – Steckbrief, Matrix, Ressourcenmessung, Changelog, Release `v1.0.0`.

## 9. Festlegungen des Umsetzenden (Claude, zur Prüfung)

- **Export-Weg:** Standard ist `QE_EXPORT_SOURCE=http://<team-service>:9090/internal/exports/stufe{N}.json`
  (interner Port; NetworkPolicy erlaubt nur Partner-/Öffentlich-Pods → Team-Port 9090). Alternativ
  Dateipfad (z. B. RWX-Volume oder Objektspeicher-Mount), falls T6 das bevorzugt. Namespaces und
  Cluster-Aufteilung fordert das Übergabepaket bei T6 an. Die Exporte enthalten nur Daten der
  jeweiligen Stufe; eigene Auth ist daher nicht nötig, solange Port 9090 nicht nach außen geht.
- **Golden-Test:** Referenz ist ein einmaliger Rohabruf vor Etappe 1 (lokal/Team-Volume, nicht im
  Repo) plus die heutigen Kuratierdateien; daraus erzeugte `truth.json` vorher/nachher müssen
  byte-gleich sein. Im Repo liegt ein kleiner Fixture-Ausschnitt für CI. Die Supplements
  (`beschreibung`/`vorschaubild`) wirken weiterhin erst beim Ausliefern (nicht im Merge), damit die
  Gleichheit gilt. Die Suche nach Dateien außerhalb des Repos (`../quellen-analyse`, `Wissen/…`)
  entfällt; Pfade kommen aus `QE_DATA_DIR`.
- **Keine kuratierten Daten im Image:** `profiles/wlo/` im Image enthält nur `profil.toml`.
  `crawler.csv` und `korrekturen.csv` liegen im Repo unter `profiles/wlo/daten/` (per
  `.dockerignore` ausgeschlossen) als Startstand. Auf das Team-Volume kommen sie per Upload im
  Team-Bereich (Crawler-Tabelle: „ersetzen“ mit Spaltenprüfung und Vorschau der Auswirkungen) oder
  einmalig per `QE_SEED_URL`.
- **Leitfaden-Quelle:** Der Diensteleitfaden (Stand 17.11.2026) liegt dem Umsetzenden vor; er wird
  nicht ins Repo kopiert (ungeprüftes internes Dokument), der Steckbrief folgt seiner Zeilenliste.

## 10. Dem Umsetzenden überlassen

- Modul-Schnitt innerhalb des Backends (z. B. Paket `core/` vs. bestehende Dateien), solange die
  Etappen-Abnahmen gelten.
- Bibliotheken für Metriken/Tracing (Empfehlung: `prometheus-client`, OpenTelemetry mit B3).
- Genaue Spaltennamen der Metriken, Intervall des Export-Abrufs (Vorschlag 10 min).
- XLSX-Import nur, wenn `openpyxl` die Image-Größe nicht spürbar erhöht; sonst CSV/JSON.
