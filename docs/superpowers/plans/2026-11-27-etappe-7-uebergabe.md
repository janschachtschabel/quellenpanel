# Etappe 7: Übergabe – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Team 6 kann Quellenpanel ohne Rückfragen übernehmen: Übergabepaket vollständig,
Steckbrief beantwortet jede Zeile, Ressourcen gemessen, Changelog, Release 1.0.0.

**Architecture:** Nur Doku, Messung und Konfiguration, kein neues Verhalten.
- **Messung:** Image aus dem echten Dockerfile bauen, Compose mit drei Rollen starten, Leerlauf,
  warm und Spitze mit `docker stats` messen; Lastskript `deploy/messung/last.py` (stdlib,
  nebenläufige Abrufe der öffentlichen Endpunkte, P50/P90 je Endpunkt); Datenaufbau des Teams
  (Rebuild aus Roh-Caches bzw. Erststart) separat messen. Ergebnis `docs/messung.md`.
- **Helm-Values:** Requests und Limits je Rolle aus der Messung (Limit ≈ Spitze + 20–30 %).
- **Übergabe-Doku:** `docs/steckbrief.md` (Zeilen aus dem Diensteleitfaden §6),
  `docs/kompatibilitaet.md` (eine Zeile der Matrix), `docs/uebergabe.md` (Übergabepaket als
  Checkliste mit Verweisen), `CHANGELOG.md` (je Release Hinweise für den Betrieb).
- **Version 1.0.0** in allen Versionsquellen; der Tag `v1.0.0` wird erst nach dem Merge gesetzt
  (Push nur auf den Arbeits-Branch).

**Tech Stack:** Docker, Compose, Python stdlib, Helm.

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` §7, §8 Etappe 7;
Diensteleitfaden (Stand 17.11.2026, Kapitel 4 Ressourcen, Kapitel 6 Übergabe und Wartung).

## Global Constraints

- Ressourcen messen statt schätzen: Leerlauf, warm, Spitze; fest oder elastisch; Limit ≈ Spitze + 20–30 %.
- Steckbrief: jede Zeile mit knapper Angabe und Status; Abweichungen begründet.
- Kosten: kein Modell, keine kostenpflichtigen Drittdienste → „nur Betriebskosten“.
- Ansprechperson und Vertretung: Jan trägt sie ein (offen markiert, nicht erfunden).
- Kein Leitfadentext ins Repo kopieren (ungeprüftes internes Dokument), nur die Zeilenliste beantworten.

## Review Focus

- Helm-Values und Compose widersprechen der Messung (Limit unter der gemessenen Spitze) → Test prüft, dass `values-*.yaml` Requests/Limits je Rolle tragen und die Doku dieselben Werte nennt (Task 1).
- Version uneinheitlich (Chart, package.json, pyproject, Doku) → bestehender Versionstest auf 1.0.0 (Task 3).
- Steckbrief nennt Endpunkte, die es in der Rolle nicht gibt → Steckbrief-Endpunkte gegen OpenAPI der Rollen geprüft (Test in Task 2).
- Changelog ohne Betriebshinweise für Breaking Changes (Daten aus dem Image, `latest` entfällt, neue Env) → Test: CHANGELOG nennt jede Env-Variable aus `config.py`, die seit 0.x neu ist (Task 2).
- Messung im Container ohne Daten (503) verfälscht → Lastskript bricht ab, wenn Antworten nicht 200 sind (Task 1).

---

### Task 1: Messung und Helm-Ressourcen

**Files:** Create `deploy/messung/last.py`, `docs/messung.md`; Modify `deploy/helm/quellenpanel/values-{team,partner,public}.yaml` (resources), `docker-compose.yml` (mem_limit/cpus, falls vorhanden), `backend/tests/test_chart.py`.
- [ ] Step 1: Failing test `test_values_resources_match_messung`: jede Rolle hat requests/limits für cpu und memory; `docs/messung.md` nennt dieselben Limits.
- [ ] Step 2: Image bauen, Compose starten, messen (Leerlauf, warm nach Erstaufruf, Spitze unter `last.py` mit 20 parallelen Clients 60 s; Team zusätzlich beim Rebuild). Image-Größe komprimiert.
- [ ] Step 3: Werte eintragen. Step 4: Tests + helm lint. Commit.

### Task 2: Steckbrief, Matrix, Übergabepaket, Changelog

**Files:** Create `docs/steckbrief.md`, `docs/kompatibilitaet.md`, `docs/uebergabe.md`, `CHANGELOG.md`; Test `backend/tests/test_uebergabe_docs.py`.
- [ ] Step 1: Failing tests: Steckbrief enthält jede Pflichtzeile (Kurzbeschreibung, Funktionen, b-api, Ruft selbst die b-api?, Abhängigkeiten, Clusterfähigkeit, Updates und CronJobs, Ressourcen, Image-Größe, Ansprechperson); Kurzbeschreibung = `info.description` der OpenAPI; jeder im Steckbrief genannte `/api/…`-Pfad existiert in der OpenAPI einer Rolle; CHANGELOG nennt alle `QE_*`-Variablen aus `config.py`.
- [ ] Step 2: FAIL. Step 3: Dokumente schreiben. Step 4: Tests grün. Commit.

### Task 3: Version 1.0.0, Abschluss

- [ ] Step 1: Versionstests auf 1.0.0 → FAIL. Step 2: Versionen anheben (pyproject, package.json/lock, Chart, README, betrieb.md). Step 3: volle Prüfung (Backend, Frontend, Builds, lint:design, helm lint). Step 4: Commit, Push, **Abschlussreview über den ganzen Branch**, Befunde beheben, PR-Text, Bericht.
