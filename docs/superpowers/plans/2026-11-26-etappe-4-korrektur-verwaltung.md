# Etappe 4: Korrektur-Verwaltung – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Team pflegt Korrekturen und die Crawler-Tabelle in der App selbst: Tabelle mit Suche,
Anlegen/Ändern/Löschen, Import (CSV/JSON/XLSX) mit Spaltenzuordnung und Vorschau, Export, Verlauf,
Upload der Crawler-Tabelle mit Vorschau der Auswirkungen. Danach rechnet die App den Merge neu und
schreibt die Exporte, ohne Live-Abruf.

**Architecture:**
- `korrektur_store.py`: die Datei `$QE_DATA_DIR/korrekturen.csv` als Zustand. Liest, prüft die
  Version (Hash des Inhalts), schreibt atomar unter einer Prozess-Sperre, führt den Verlauf
  (`korrekturen-verlauf.csv`) und legt vor jedem Ersetzen eine datierte Sicherung an.
- `korrektur_import.py`: reine Funktionen. Datei lesen (CSV `;`/`,`, JSON-Liste, XLSX), Spalten
  automatisch zuordnen, Vorschau neu/geändert/unverändert/fehlerhaft, Ergebnis für „ergänzen“ oder
  „ersetzen“ berechnen.
- `crawler_upload.py`: Crawler-Tabelle prüfen (Pflichtspalten aus dem Profil), Auswirkungen
  gegenüber dem aktuellen Stand zeigen (Spider neu/entfallen/geändert), ersetzen mit Sicherung.
- `anwenden.py`: nach jeder Änderung Merge neu rechnen (`truth.main()` aus den Roh-Caches), Daten
  laden, Supplements neu lesen, Exporte schreiben. Ohne Roh-Caches nur Supplements und Exporte;
  die Antwort sagt dann `wirktBeimNaechstenAufbau: true`.
- Routen unter `/api/team/…` in `app.py`, nur Rolle team, nur mit Team-Login.
- Frontend: Ansicht „Korrekturen“ (Stufe 2) mit Tabelle, Dialogen, Import-Assistent, Verlauf und
  Crawler-Upload; im Steckbrief die Knöpfe „Auf Blacklist“ und „Beschreibung ergänzen“.

**Tech Stack:** Python 3.12, FastAPI, `openpyxl` (neu, nur Lesen), Angular 21 + Material.

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` (§6.4, §6.5, §8 Etappe 4,
§9 „Keine kuratierten Daten im Image“, §10 XLSX)

## Global Constraints

- Nur die Team-Instanz hat diese Routen: auf partner/public 404 (`require_team_role`), ohne Login 403.
- Schreibende Routen (POST/PUT/DELETE) mit Cookie-Sitzung prüfen den `Origin`: fehlt er oder ist er
  gleich dem Host oder steht er in `QE_ALLOWED_ORIGINS`, ist es gut; sonst 403 (CSRF-Schutz, weil
  Uploads ohne Preflight kämen). Uploads kommen als Rohdaten (`application/octet-stream`), nicht
  als multipart (keine neue Abhängigkeit `python-multipart`).
- Uploads unter `/api/team/` dürfen bis 5 MB groß sein, alle anderen Anfragen weiter 1 MB. XLSX
  wird mit `openpyxl` im `read_only`-Modus gelesen, höchstens 20 000 Zeilen.
- Jede Änderung trägt ein Kürzel (`wer`, 1–40 Zeichen, frei eingegeben) und das Datum. Der Verlauf
  hat die Spalten `Zeitpunkt;Wer;Vorgang;Alt;Neu` (UTF-8 mit BOM, `;`).
- Optimistische Sperre: Jede schreibende Anfrage schickt die `version` (SHA-256 des Dateiinhalts,
  16 Hex-Zeichen), die sie gelesen hat. Weicht sie ab → 409 „Die Korrekturen wurden inzwischen
  geändert“.
- Während eines Rebuilds (`refresh.status()["status"] == "running"`) antworten schreibende Routen 409.
- Geschrieben wird immer nach `$QE_DATA_DIR`; fehlt die Datei dort, ist der Startstand aus dem Profil
  der Ausgangspunkt.
- Logs: nie Dateiinhalte, Kommentare oder Werte loggen; nur Anzahlen.
- Fehlerformat wie in Etappe 3 (`errors.response`).

---

### Task 1: Korrektur-Store (Lesen, Version, CRUD, Verlauf, Sicherung)

**Files:** Create `backend/korrektur_store.py`, `backend/tests/test_korrektur_store.py`

**Interfaces:**
- Produces:
  - `store_path() -> Path` (= `config.data_dir() / "korrekturen.csv"`), `verlauf_path() -> Path`
  - `lesen() -> dict` mit `version`, `eintraege` (Liste von Dicts mit `id` = Zeilenindex ab 0 und den
    Feldern `typ, schluessel, aktion, wert, kommentar, geaendert_von, geaendert_am`), `fehler`,
    `warnungen` (je `{zeile, text}`)
  - `anlegen(k: dict, wer: str, version: str) -> dict`, `aendern(id: int, k: dict, wer, version)`,
    `loeschen(id: int, wer, version)` → jeweils das neue `lesen()`-Ergebnis
  - `ersetzen_alle(eintraege: list[Korrektur], wer, version, vorgang: str, sicherung: bool) -> dict`
  - `verlauf(limit: int = 200) -> list[dict]` (neueste zuerst)
  - Ausnahmen `VersionKonflikt`, `UngueltigeKorrektur(text)`
- `geaendert_von`/`geaendert_am` setzt der Store (wer, heutiges Datum), nicht der Client.

- [ ] **Step 1: Failing tests:**
  - `lesen()` ohne Datei im Datenverzeichnis liefert den Profil-Startstand mit Version.
  - `anlegen` schreibt nach `$QE_DATA_DIR/korrekturen.csv`, setzt `geaendert_von`/`geaendert_am`,
    hängt eine Verlaufszeile an (`Vorgang=anlegen`, `Alt` leer, `Neu` = Zeile).
  - `aendern`/`loeschen` mit Verlauf `Alt`/`Neu`; unbekannte `id` → `UngueltigeKorrektur`.
  - Ungültige Zeile (z. B. Node-ID keine UUID, Aktion unbekannt) → `UngueltigeKorrektur`, Datei
    unverändert.
  - Falsche `version` → `VersionKonflikt`, Datei unverändert.
  - `ersetzen_alle(..., sicherung=True)` legt `korrekturen-<YYYYmmdd-HHMMSS>.csv` mit dem alten
    Inhalt an.
  - Leeres oder zu langes `wer` → `UngueltigeKorrektur`.
- [ ] **Step 2:** `cd backend && python -m pytest -q tests/test_korrektur_store.py`. Expected: FAIL (Modul fehlt).
- [ ] **Step 3: Implement** mit `korrekturen.load_korrekturen`/`write_korrekturen`/`_check`, Sperre
  `threading.Lock`, Version = `hashlib.sha256(bytes).hexdigest()[:16]`.
- [ ] **Step 4:** Tests grün; `python -m ruff check .` sauber.
- [ ] **Step 5: Commit** `feat(korrekturen): Store mit Version, Verlauf und Sicherung`.

### Task 2: Import (Lesen, Zuordnung, Vorschau, Ergebnis)

**Files:** Create `backend/korrektur_import.py`, `backend/tests/test_korrektur_import.py`;
Modify `backend/requirements.txt` (`openpyxl==3.1.5`)

**Interfaces:**
- Produces:
  - `lesen_datei(data: bytes, format: str) -> tuple[list[str], list[dict[str, str]]]` — Spalten und
    Zeilen; `format` ∈ `csv`, `json`, `xlsx`. Fehler → `ImportFehler(text)`.
  - `auto_zuordnung(spalten: list[str]) -> dict[str, str | None]` — Zielfeld → Quellspalte. Zielfelder:
    `typ, schluessel, aktion, wert, kommentar`. Erkennt die Kopfzeile von `korrekturen.HEADER`
    und Aliasse (`Node-Id`/`nodeId` → schluessel, `Liste` → aktion, `type` → typ, …), Groß/Klein und
    Umlaute egal (`truth_text._norm`).
  - `vorschau(zeilen, zuordnung, bestand: list[Korrektur], modus: str) -> dict` mit `neu`,
    `geaendert` (`{alt, neu}`), `unveraendert` (Anzahl), `fehlerhaft` (`{zeile, text}`), `entfallen`
    (nur bei `ersetzen`) und `ergebnis: list[Korrektur]`.
  - Schlüssel einer Korrektur für den Abgleich: `(typ, schluessel, aktion)`; bei `blacklist`,
    `whitelist`, `vermerk` gilt `(typ, schluessel, "liste")`, damit ein Listenwechsel als „geändert“
    erscheint.
- [ ] **Step 1: Failing tests:** CSV mit `;` und `,`; JSON-Liste; XLSX (mit openpyxl im Test
  erzeugt); kaputtes JSON → `ImportFehler`; mehr als 20 000 Zeilen → `ImportFehler`; auto-Zuordnung
  der eigenen Kopfzeile und der Alt-Kopfzeile; Vorschau „ergänzen“ zählt neu/geändert/unverändert/
  fehlerhaft richtig; „ersetzen“ meldet `entfallen`; Listenwechsel blacklist→whitelist ist „geändert“.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Tests grün, ruff sauber; `pip install openpyxl==3.1.5`.
- [ ] **Step 5: Commit** `feat(korrekturen): Import CSV/JSON/XLSX mit Zuordnung und Vorschau`.

### Task 3: Anwenden und Crawler-Upload

**Files:** Create `backend/anwenden.py`, `backend/crawler_upload.py`, `backend/tests/test_anwenden.py`,
`backend/tests/test_crawler_upload.py`

**Interfaces:**
- Produces:
  - `anwenden.nach_aenderung() -> dict` → `{"neuBerechnet": bool, "wirktBeimNaechstenAufbau": bool}`.
    Mit Roh-Caches (`config.raw_dir() / "quellen_nodes.json"` vorhanden): `truth.main()`, `store.load()`,
    `enduser.reload_supplements()`, Exporte neu. Ohne: nur Supplements und Exporte.
  - `crawler_upload.pruefen(data: bytes) -> dict` → `{zeilen, spalten, fehlendePflicht, spider: {neu,
    entfallen, geaendert, gleich}}`; Pflichtspalten: `profil.crawler_spider_spalte` und
    `profil.crawler_quelldatensatz_spalte` (bzw. was das Profil dafür nennt). Fehlen sie → `ok: false`.
  - `crawler_upload.ersetzen(data: bytes, wer: str) -> dict`: prüft erneut, sichert die alte
    `crawler.csv` als `crawler-<ts>.csv`, schreibt atomar, Verlaufszeile `Vorgang=crawler_ersetzen`
    (Alt/Neu = Zeilenzahlen), ruft `anwenden.nach_aenderung()`.
- [ ] **Step 1: Failing tests:** `nach_aenderung` ohne Roh-Caches → `wirktBeimNaechstenAufbau` true und
  Supplements neu gelesen; mit Roh-Caches (Fixture-Ausschnitt aus `tests/fixtures/golden`) → `truth.main`
  läuft, `store._DATA` enthält das BLACKLIST-Flag einer frisch angelegten blacklist-Korrektur.
  `pruefen` meldet fehlende Pflichtspalte; Spider-Diff neu/entfallen; `ersetzen` legt Sicherung an.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Tests grün, ruff sauber.
- [ ] **Step 5: Commit** `feat(team): Merge nach Änderung neu rechnen, Crawler-Tabelle hochladen`.

### Task 4: API-Routen

**Files:** Modify `backend/app.py`; Create `backend/tests/test_team_korrekturen_api.py`

**Interfaces:**
- Produces (alle `dependencies=_TEAM_ONLY`, Login über `tiers.is_team`, schreibende mit Origin-Prüfung
  `_same_origin_or_trusted`):
  - `GET /api/team/korrekturen` → `korrektur_store.lesen()`
  - `POST /api/team/korrekturen` Body `{korrektur, wer, version}` → `{…lesen(), anwenden}`
  - `PUT /api/team/korrekturen/{id}` Body `{korrektur, wer, version}`
  - `DELETE /api/team/korrekturen/{id}?wer=…&version=…`
  - `GET /api/team/korrekturen.csv` → Datei-Download (`text/csv; charset=utf-8`, `Content-Disposition`)
  - `GET /api/team/korrekturen/verlauf?limit=` → Liste
  - `POST /api/team/korrekturen/import/vorschau?format=&modus=` Body roh → `{spalten, zuordnung,
    vorschau (ohne ergebnis, Listen auf 200 gekürzt, dazu Anzahlen)}`; optional Header
    `X-Zuordnung` (JSON) für eine manuelle Zuordnung
  - `POST /api/team/korrekturen/import?format=&modus=&wer=&version=` Body roh, `X-Zuordnung` →
    übernehmen (Sicherung bei `ersetzen`), `{…lesen(), anwenden}`
  - `POST /api/team/crawler/vorschau` Body roh → `crawler_upload.pruefen`
  - `POST /api/team/crawler?wer=` Body roh → `crawler_upload.ersetzen`
  - Fehler: `VersionKonflikt`/Rebuild läuft → 409, `UngueltigeKorrektur`/`ImportFehler` → 422 mit Text.
  - Middleware: Body-Grenze 5 MB für Pfade unter `/api/team/`; `_CORS_METHODS` um PUT, DELETE ergänzen.
- [ ] **Step 1: Failing tests:** 404 auf partner/public; 403 ohne Login; CRUD-Durchlauf mit Cookie;
  409 bei falscher Version und während eines laufenden Rebuilds; 403 bei fremdem `Origin`; Import-
  Vorschau und Übernahme CSV; CSV-Download beginnt mit BOM und Kopfzeile; Verlauf enthält die
  Vorgänge; Crawler-Vorschau mit fehlender Pflichtspalte → `ok: false`; Upload 2 MB wird nicht mit 413
  abgelehnt, 6 MB schon; OpenAPI der Rolle public enthält keine `/api/team/`-Pfade.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Volle Backend-Suite grün, ruff sauber.
- [ ] **Step 5: Commit** `feat(api): Team-Routen für Korrekturen und Crawler-Tabelle`.

### Task 5: Frontend – Ansicht „Korrekturen“ (Tabelle, Dialoge, Export, Verlauf)

**Files:** Create `frontend/src/app/korrekturen.service.ts`, `korrekturen.service.spec.ts`,
`korrekturen.component.ts`, `korrektur-dialog.component.ts`; Modify `app.component.ts` (Ansicht
`korrekturen` nur bei Stufe 2), `models.ts`, `i18n.service.ts`

**Interfaces:**
- Produces: `KorrekturenService` mit `lesen()`, `anlegen()`, `aendern()`, `loeschen()`, `verlauf()`,
  `exportUrl()`, `importVorschau()`, `importieren()`, `crawlerVorschau()`, `crawlerErsetzen()`;
  Kürzel `wer` aus `localStorage` (`qe.wer`), beim ersten Schreiben per Dialog abgefragt.
- Component: Filterfeld (Volltext über alle Spalten), Auswahl Typ/Aktion, `mat-table` mit Paginator,
  Knöpfe Anlegen/Ändern/Löschen, Export-Link, Reiter „Verlauf“, Anzeige der Ladefehler (`fehler`,
  `warnungen`) und des Hinweises „wirkt beim nächsten Datenaufbau“.
- [ ] **Step 1: Failing spec** `korrekturen.service.spec.ts`: richtige URLs/Methoden/Bodies, `version`
  wird mitgeschickt, `wer` aus localStorage.
- [ ] **Step 2:** `CHROME_BIN=/opt/pw-browsers/chromium npx ng test --watch=false`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Tests grün; `npx ng build` ohne Fehler.
- [ ] **Step 5: Commit** `feat(frontend): Ansicht Korrekturen`.

### Task 6: Frontend – Import-Assistent, Crawler-Upload, Knöpfe im Steckbrief

**Files:** Create `frontend/src/app/korrektur-import.component.ts`, `crawler-upload.component.ts`,
`korrektur-import.spec.ts`; Modify `detail.component.ts`, `korrekturen.component.ts`, `i18n.service.ts`

**Interfaces:**
- Import-Assistent: Datei wählen (Format aus der Endung `.csv/.json/.xlsx`), Modus ergänzen/ersetzen,
  Vorschau abrufen, Zuordnung je Zielfeld per Auswahl ändern (erneute Vorschau), Anzahlen und Listen
  neu/geändert/fehlerhaft/entfallen, „Übernehmen“ (bei ersetzen mit Bestätigung).
- Crawler-Upload: Datei wählen → Vorschau (Zeilen, fehlende Pflichtspalten, Spider neu/entfallen/
  geändert) → „Ersetzen“.
- Steckbrief (Stufe 2, Datensatz mit Node-ID): „Auf Blacklist“ legt `node;<id>;blacklist` an;
  „Beschreibung ergänzen“ öffnet den Dialog mit `bezugsquelle;<Name>;beschreibung`.
- Reine Hilfsfunktion `formatAusDateiname(name)` und `zuordnungGeaendert(...)` mit Spec.
- [ ] **Step 1: Failing spec** für die Hilfsfunktionen.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Tests grün, Build ok; Probe im Browser (Playwright-Screenshot der Ansicht mit Team-Login).
- [ ] **Step 5: Commit** `feat(frontend): Import-Assistent, Crawler-Upload, Korrektur aus dem Steckbrief`.

### Task 7: Version, Doku, Zwischenprüfung

**Files:** Modify `backend/pyproject.toml`, `frontend/package.json`, `deploy/helm/quellenpanel/Chart.yaml`
(0.4.0), `backend/tests/test_version.py`, `docs/betrieb.md` (Abschnitt „Korrekturen und Crawler-Tabelle“),
`README.md`

- [ ] **Step 1:** `test_version.py` auf 0.4.0 → FAIL.
- [ ] **Step 2:** Versionen anheben, Doku schreiben.
- [ ] **Step 3: Volle Prüfung:** Backend-Suite, ruff, Frontend-Tests, Build, `helm lint` (Docker).
- [ ] **Step 4: Commit und Push** `docs: Korrektur-Verwaltung; Version 0.4.0`.
- [ ] **Step 5: Abschlussreview** mit frischem Reviewer, Befunde per Test beheben, PR-Text ergänzen.

## Review Focus

- CSRF über Cookie-Sitzung bei Uploads (Origin fehlt vs. fremd), Größenlimit pro Pfad.
- Gleichzeitige Änderungen (Version), Rebuild parallel zu einer Änderung.
- XLSX-Bomben/Riesen-Dateien, Formeln in Zellen (werden als Werte gelesen, `data_only=True`).
- CSV-Injection beim Export (Werte mit `=`, `+`, `-`, `@` am Anfang) – Excel ist das Zielwerkzeug.
- Datei im Profil-Startstand darf nie überschrieben werden; geschrieben wird nur ins Datenverzeichnis.
