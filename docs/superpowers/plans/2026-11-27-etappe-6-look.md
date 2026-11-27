# Etappe 6: Look – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das Panel sieht aus wie edu-sharing 11 mit WLO-Branding, ist in Sie-Form betextet und
besteht ein A11y-Audit nach WCAG 2.1 AA, auch eingebettet.

**Architecture:**
- **Token-Schicht** in `frontend/src/_tokens.scss`: die edu-sharing-Tokens aus `DESIGN.md` der
  UX-Skills (Farben, Radien, Abstände, Fokus) als CSS-Variablen unter denselben Namen
  (`--primary`, `--textMain`, `--textLight`, `--backgroundColor`, `--borderRadiusCards` …), dazu die
  Tönungen `--primaryBackground50/100/300` und `--primaryForeground800` per `color-mix` aus
  `--primary`. Die alten `--wlo-*`/`--q-*` werden Aliase auf diese Tokens (keine Doppelpflege).
- **Branding aus dem Profil:** `/api/capabilities` liefert `branding: {primary, accent}` aus
  `profil.toml`; das Frontend setzt `--primary`/`--accent` am Host (`:root` bzw. Element), nur
  wenn der Wert ein gültiger Hex-Farbwert ist. Material-Theme (`--mat-sys-primary` usw.) zeigt auf
  `var(--primary)`.
- **Schrift:** Open Sans lokal über `@fontsource/open-sans` (400, 600), Roboto entfällt.
- **Kachel-Anatomie** nach `node-entries-anatomy.md` §1/§5, angepasst an Quellen: Kopfleiste 40px
  (Typ-Badge links, OER/Familie, Checkbox rechts), Vorschaubild 150px (contain vor unscharfer
  Kopie), Titel linksbündig max. 2 Zeilen, Metadaten-Zeilen Label/Wert, Fußleiste mit Anzahl und
  Qualität; kein Radius, Raster `minmax(270px, 1fr)`, Abstand 20px.
- **Texte:** i18n-Wörterbuch nach `write-copy` (Sie-Form, Verb vorn, Leer-/Fehlertexte mit
  nächstem Schritt).
- **Kopfzeile** unter 900px umbrechend (offener Befund aus Etappe 3).
- **A11y-Audit:** axe-core (devDependency) per Playwright-Skript über alle Ansichten, Kontrast mit
  `contrast.mjs` der UX-Skills; Befunde beheben.

**Tech Stack:** Angular 21, Angular Material 21, SCSS, @fontsource/open-sans, axe-core, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` §6.7, §8 Etappe 6.
UX-Regeln: `github.com/janschachtschabel/edu-sharing-11-ux-skills` (`DESIGN.md`,
`build-components/references/{tokens,node-entries-anatomy}.md`, `write-copy`, `audit-accessibility`).

## Global Constraints

- Farben in Komponenten nur `var(--…)`; Hex nur in `_tokens.scss`/`_theme.scss` (Token-Quelle).
- Radien: Seitencontainer `--borderRadiusCards` 20px, Badges `--borderRadiusBadges` 10px, Buttons
  `--borderRadiusButtons` 18px; Kacheln ohne Radius.
- Abstände aus 5/10/15/20/25/30/40px; 2px nur Linien/Fokus.
- Fokus sichtbar: 2px `--focusColor`, Offset 2px.
- Kontrast Text ≥ 4,5:1, große Schrift/Icons/Ränder ≥ 3:1. `--accent` (#e4f700) nie als Text/Icon auf Hell.
- Klickziele ≥ 24×24px.
- Texte de + en, Deutsch siezt.
- Breakpoints 900px / 700px.
- Die Widgets (Etappe 5) bleiben unverändert isoliert; das Element-Bundle setzt Tokens nur am Host-Tag.

## Review Focus

- Branding-Wert aus dem Profil ist kein gültiger Farbwert (z. B. `red; background:url(…)`) → wird ignoriert, Standard-Primärfarbe bleibt (Test in Task 1).
- Eine fremde Primärfarbe mit wenig Kontrast (hell) → Text auf Primärflächen bleibt lesbar: Text auf Primär nutzt `--primaryForeground800`/weiß nur bei dunkler Primärfarbe (Probe in Task 4 mit `primary=#7fb2e5`).
- Eingebettet (`<wlo-quellen-kacheln>`) → Tokens nur am Host, Gastseite unverändert (bestehender Test `test_element_bundle_styles_never_touch_host_page` bleibt grün).
- Kachel ohne Vorschaubild, ohne Beschreibung, mit sehr langem Namen → gleiche Höhe der Fußleiste, Titel mit „…“ (Probe in Task 2).
- Englische Oberfläche → keine deutschen Reste in den geänderten Texten (Test in Task 3: jeder Schlüssel hat de und en).

---

### Task 1: Tokens, Branding aus dem Profil, Open Sans

**Files:** Create `frontend/src/_tokens.scss`, `frontend/src/app/branding.ts`, `frontend/src/app/branding.spec.ts`;
Modify `frontend/src/_theme.scss`, `styles.scss`, `styles.element.scss`, `angular.json` (Schriften),
`package.json` (`@fontsource/open-sans@5`), `backend/app.py` (capabilities), `backend/tests/test_branding.py`.

**Interfaces:**
- `GET /api/capabilities` → zusätzlich `"branding": {"primary": str, "accent": str}` (nur Werte aus `profil.toml [branding]`, gültige Hex-Farben `^#[0-9a-fA-F]{6}$`, sonst Feld weggelassen).
- `istFarbe(v: unknown): v is string` und `wendeBrandingAn(el: HTMLElement, b: {primary?: string; accent?: string} | undefined): void` in `branding.ts` (setzt `--primary`/`--accent` per `style.setProperty`, ungültige Werte werden ignoriert).
- Token-Namen wie DESIGN.md; `@mixin tokens` in `_tokens.scss`, eingebunden in `wlo-theme-vars`.
- [ ] Step 1: Failing tests: `test_capabilities_has_profile_branding`, `test_invalid_branding_is_dropped`; spec `branding.spec.ts` (gültig gesetzt, `red;x` ignoriert, undefined harmlos).
- [ ] Step 2: Run → FAIL. Step 3: Implement; Material-Variablen auf Tokens; Open Sans statt Roboto. Step 4: Backend- und Frontend-Tests, Build, Element-Build. Step 5: Commit.

### Task 2: Komponenten auf Tokens, Kachel-Anatomie, Kopfzeile

**Files:** Modify `frontend/src/app/*.component.ts` (Inline-Styles), `tiles.component.ts` (Anatomie),
`app.component.ts` (Kopfzeile responsive); Create `frontend/scripts/lint-design.mjs` (ruft die
Regeln aus den UX-Skills auf, mit lokaler Kopie unter `frontend/scripts/lint-design-rules.mjs`),
`package.json` Script `lint:design`.
- [ ] Step 1: Failing check: `npm run lint:design` meldet FEHLER (`no-color-literal`) in den Komponenten.
- [ ] Step 2: Komponenten umstellen; Kachel nach Anatomie (Kopfleiste 40px, Bild 150px mit unscharfer Kopie, Titel 2 Zeilen, Label/Wert-Zeilen, Fußleiste), Raster `minmax(270px,1fr)` gap 20px; Kopfzeile bricht unter 900px um.
- [ ] Step 3: `npm run lint:design` → 0 FEHLER; Frontend-Tests grün; Build im Budget. CI-Schritt `lint:design`.
- [ ] Step 4: Browser-Probe 1280/900/375px: Kacheln (mit/ohne Bild, langer Name), Liste, Detail, Statistik. Screenshots. Commit.

### Task 3: Texte (Sie-Form)

**Files:** Modify `frontend/src/app/i18n.service.ts`, Komponenten mit fest verdrahtetem Text; Test `i18n.service.spec.ts`.
- [ ] Step 1: Failing spec: jeder Schlüssel des Wörterbuchs hat `de` und `en`; kein `du/dein/dich` in de-Texten (Wortgrenzen); Leer- und Fehlertexte nennen einen nächsten Schritt (Schlüssel `empty.*`, `error.*` enthalten ein Verb aus einer kurzen Liste oder „bitte“).
- [ ] Step 2: FAIL. Step 3: Texte nach `write-copy` überarbeiten. Step 4: Tests grün. Commit.

### Task 4: A11y-Audit und Befunde

**Files:** Create `frontend/scripts/a11y-audit.mjs` (Playwright + axe-core gegen lokalen Server, alle Ansichten und Stufen-Schalter, Ergebnis als JSON), devDependency `axe-core`; Modify betroffene Komponenten; `docs/a11y.md` (Ergebnis, bekannte Ausnahmen).
- [ ] Step 1: Audit laufen lassen → Befundliste (erwartet: Kontrast, Namen von Icon-Buttons, Landmarken …).
- [ ] Step 2: Befunde beheben, je Befund mit Test wo möglich (Spec auf aria-label/Rolle), sonst Audit als Beleg.
- [ ] Step 3: Audit erneut → 0 Verstöße der Stufen `serious`/`critical`; Tastaturdurchlauf (Tab-Reihenfolge, Fokus sichtbar, Dialog fängt Fokus) per Probe; Kontrast-Probe mit hellem Branding.
- [ ] Step 4: Version 0.6.0, README/betrieb, Commit, Push, **Abschlussreview**, Befunde beheben, PR-Text.
