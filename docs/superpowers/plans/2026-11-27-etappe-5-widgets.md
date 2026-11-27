# Etappe 5: Widgets – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gastseiten (Fachportale, Schulseiten, edu-sharing) binden das Quellenverzeichnis mit einem
Skript und einem Tag ein, oder als iframe. Dazu Einbau-Doku und Testseiten.

**Architecture:**
- **Leichtes Widget-Skript** `quellenpanel-widgets.js` (Vanilla-TypeScript, mit esbuild gebaut, keine
  Abhängigkeiten, wenige KB). Es registriert:
  - `<wlo-quellen-liste>`: einfache Liste (Suchfeld + kompakte Zeilen: Name, Fächer, Anzahl Inhalte,
    Link). `variante="schlicht"` = für helle Hintergründe, ohne Rahmen/Hintergrund, `suche="aus"`
    blendet das Suchfeld aus (Jans Wunsch).
  - `<wlo-quellen-top fach="…" max="10">`: Top N nach Inhalten je Fach, nummeriert (Jans Wunsch).
  - `<wlo-quellen-zahl fach="…">`: Kennzahl „N Quellen · M Inhalte“ mit Link ins Verzeichnis.
  - `<wlo-quelle quelle="<id>">`: kompakter Steckbrief einer Quelle (Name, Beschreibung, Fächer,
    Stufen, Lizenz/OER, Anzahl, Link).
  - `<wlo-quellen-statistik>`: Balken der Fächer und Bildungsstufen (aus `/api/stats`).
  - `<wlo-quellen-kacheln>` und `<wlo-quellenpanel>`: laden beim ersten Vorkommen das vorhandene
    Angular-Element-Bundle nach (`/widgets/element/main.js`), das beide Namen registriert.
- Gemeinsame Attribute: `api-base`, `fach`, `bildungsstufe`, `suche` (Vorbelegung), `max`, `sprache`
  (`de`/`en`), `nur-oer`. `api-base` fehlt → Herkunft des Skripts + `/api`.
- **iframe-Seiten** `/embed/<name>?…` (Backend): kleines HTML ohne Inline-Skript, lädt das
  Widget-Skript und `embed.js`; Höhe per `postMessage` nur auf Anfrage der Elternseite
  (`{type:"quellenpanel:hoehe?"}` → Antwort `{type:"quellenpanel:hoehe", hoehe}`, danach bei Änderung).
  CSP-Kopf mit `frame-ancestors` aus `QE_FRAME_ANCESTORS` (Standard `*`; Rolle team: `'self'`).
- **Backend:** `GET /api/kennzahl` (Stufe 0, alle Rollen; gleiche Filter wie `/api/sources`) →
  `{quellen, inhalte}`; Mount `/widgets` → `frontend/dist-widgets`.

**Tech Stack:** TypeScript, esbuild (schon in node_modules über `@angular/build`), Angular Elements,
FastAPI.

**Spec:** §6.6, §8 Etappe 5; Jans Wünsche vom 27.11.2026 (schlichte Liste, Top 10 je Fach) und die
von Claude gewählten Zusätze (Kennzahl, `nur-oer`, Bildungsstufe).

## Global Constraints

- Öffentliche Widgets senden keine Cookies (`credentials: "omit"`). Kein `with-credentials` im
  leichten Skript.
- Kein Shadow DOM, aber alle Styles unter dem Element-Selektor (z. B. `wlo-quellen-liste .wq-…`),
  keine Selektoren auf `html`/`body`/`:root`, eigener Font-Stack und Farben über CSS-Variablen
  `--wq-*` (überschreibbar). Styles über `adoptedStyleSheets` (CSP-tauglich), Fallback `<style>`.
- Daten nur über `textContent`/Attribute in den DOM, nie `innerHTML` mit Daten. Links nur `http(s)`,
  mit `target="_blank" rel="noopener"` und Hinweis „öffnet in neuem Tab“ (visuell versteckt + `title`).
- CSP-tauglich: kein `eval`, keine Inline-Skripte auf `/embed/*`, Schriften vom System.
- Ladezustand und Fehlerzustand sichtbar (kurzer Text), `aria-live="polite"` für Ergebnisse.
- Zahlen im deutschen Format (`de-DE`) bzw. `en` bei `sprache="en"`.

---

### Task 1: Backend – Kennzahl, Embed-Seiten, Widgets-Mount

**Files:** Modify `backend/app.py`, `backend/config.py`; Create `backend/embed.py`,
`backend/tests/test_widgets_backend.py`

**Interfaces:**
- `GET /api/kennzahl?subject=&level=&oer=&q=` → `{"quellen": int, "inhalte": int}` aus Export Stufe 0.
- `GET /embed/{name}` mit `name` ∈ `quellen-liste, quellen-top, quellen-zahl, quelle, quellen-statistik,
  quellen-kacheln, quellenpanel`; Query-Parameter werden zu Attributen, nur erlaubte Namen
  (`fach, bildungsstufe, suche, max, sprache, nur-oer, variante, quelle`), Werte HTML-escaped, höchstens
  200 Zeichen. Unbekannter Name → 404.
- Kopf `Content-Security-Policy: default-src 'self'; img-src * data:; style-src 'self'; frame-ancestors <QE_FRAME_ANCESTORS>`.
  `config.frame_ancestors()`: Env, Standard `*`, in Rolle team `'self'`.
- `/widgets/…` liefert `frontend/dist-widgets/` aus, wenn vorhanden.
- [ ] Step 1: Failing tests (Kennzahl mit/ohne Fach, nur-oer; Embed: Attribute escaped, unerlaubte
  Parameter weg, 404, CSP-Kopf je Rolle und Env; `/embed` nicht unter dem 503-Gate fürs Team nötig).
- [ ] Step 2: Run → FAIL. Step 3: Implement. Step 4: Suite + ruff. Step 5: Commit.

### Task 2: Widget-Kern (Hilfsfunktionen) mit Tests

**Files:** Create `frontend/src/widgets/core.ts`, `frontend/src/widgets/core.spec.ts`

**Interfaces:** `apiBaseFor(scriptSrc, attr)`, `queryFromAttributes(el)` (→ URLSearchParams mit
`subject, level, oer, q, sort=contentCount, order=desc, page_size`), `formatZahl(n, sprache)`,
`sichererLink(url)` (nur http/https), `el(tag, cls, text?)`, `externerLink(href, text, sprache)`,
`styles(css)` (einmal pro Element-Typ), `holeJson(url)` (fetch mit `credentials: "omit"`, Zeitlimit 15 s).
- [ ] Step 1: Failing specs. Step 2: Run → FAIL. Step 3: Implement. Step 4: Tests grün. Step 5: Commit.

### Task 3: Elemente liste, top, zahl, quelle, statistik + Loader für kacheln/panel

**Files:** Create `frontend/src/widgets/elements.ts`, `frontend/src/widgets/widgets.ts` (Einstieg),
`frontend/src/widgets/embed.ts`, `frontend/src/widgets/elements.spec.ts`; Modify `src/main.element.ts`
(zusätzlich `wlo-quellen-kacheln`), `app.component.ts` (Inputs `fach`, `bildungsstufe`, `suche`),
`package.json` (`build:widgets` mit esbuild), `scripts/build-widgets.mjs`.
- [ ] Step 1: Failing specs (mit gemocktem `fetch`): Liste rendert Namen per textContent (HTML im
  Namen bleibt Text), Top nummeriert und begrenzt auf `max`, Zahl formatiert, `suche="aus"` ohne Feld,
  `variante="schlicht"` setzt Klasse, Fehlerzustand bei 500, Quelle zeigt Link nur bei http(s),
  Statistik-Balken; `embed.ts` antwortet nur auf `quellenpanel:hoehe?`.
- [ ] Step 2: FAIL. Step 3: Implement. Step 4: Tests grün; `npm run build:widgets` erzeugt
  `dist-widgets/quellenpanel-widgets.js` (< 30 KB) und `embed.js`; `npm run build:element` ok.
- [ ] Step 5: Commit. **Zwischenreview** (frischer Reviewer) über Task 1–3, Befunde beheben.

### Task 4: Image, Doku, Testseiten, Probe

**Files:** Modify `Dockerfile` (Widgets und Element bauen und kopieren), `.github/workflows/ci.yml`
(build:widgets, build:element), Create `docs/widgets.md` (Einbau-Beispiele je Element, iframe, Attribute,
CSS-Variablen, CSP-Hinweise für Gastseiten), `frontend/widgets-beispiele/leer.html`,
`frontend/widgets-beispiele/gast.html` (Gastseite mit eigenen, aggressiven Styles), kopiert nach
`dist-widgets/beispiele/`. `backend/tests/test_deploy_files.py` (Dockerfile baut Widgets).
- [ ] Step 1: Failing test (Dockerfile enthält build:widgets, kopiert dist-widgets).
- [ ] Step 2–3: Implement. Step 4: Playwright-Probe beider Testseiten gegen lokalen Server (Loopback):
  Widgets rendern, Gast-Styles brechen sie nicht, Gastseite bleibt unverändert, keine Konsolenfehler;
  iframe-Seite mit Höhen-Nachricht. Screenshots.
- [ ] Step 5: Version 0.5.0, Commit, Push, **Abschlussreview**, Befunde beheben, PR-Text.

## Review Focus

- XSS über Daten (Namen, Beschreibungen, URLs mit `javascript:`), über Embed-Query-Parameter.
- Style-Leaks in beide Richtungen (Gastseite → Widget, Widget → Gastseite).
- CSP der Gastseite (kein Inline, kein eval), `frame-ancestors`.
- postMessage: keine Daten an fremde Fenster ohne Anfrage, keine Auswertung fremder Nachrichten außer
  der Höhen-Anfrage.
- Cookies nie gesendet; Rollen partner/public liefern Widgets nur Stufe 0.
