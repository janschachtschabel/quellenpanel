# Etappe 2: Rollen und Exporte – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Image, drei Rollen (`QE_ROLE=team|partner|public`). Partner- und öffentliche Instanz halten nur den Export ihrer Stufe im Speicher. Alle Anfragen unterhalb von Stufe 2 werden auch auf der Team-Instanz aus diesem Export bedient.

**Architecture:**
- Die Team-Instanz baut aus `truth.json` je Stufe ein Export-Dokument und legt es unter `$QE_DATA_DIR/exports/stufe{0,1}.json` ab, jeweils mit ETag.
- Gebaut wird das Dokument mit genau den Serializern, die heute Stufe 0/1 ausliefern: `serialize.source`, `views.flat`, `stats.*`.
- Ein Abfragemodul filtert, sortiert und blättert über den Export-Einträgen. Damit kann keine Antwort unterhalb von Stufe 2 mehr enthalten, als der Serializer der Stufe ausgegeben hat.
- Partner und Öffentlich laden ihren Export aus `QE_EXPORT_SOURCE` (URL oder Datei) und fragen ihn regelmäßig neu ab. Bei Fehlern behalten sie den letzten gültigen Stand und legen eine Kopie in `/tmp` ab.

**Tech Stack:** Python 3.12, FastAPI, pytest, `urllib.request` (keine neue Abhängigkeit); Angular 21 (eine kleine Template-Änderung).

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` (§6.1 Rollen, §6.2 Datenfluss, §8 Etappe 2, §9 Export-Weg)

## Global Constraints

- Rollen: `team` (max. Stufe 2), `partner` (max. 1), `public` (max. 0) – „Die Stufen-Obergrenze ergibt sich aus der Rolle; `tiers.effective_tier` bleibt die einzige Stelle, die sie anwendet.“
- „`QE_PUBLIC_ONLY` entfällt zugunsten von `QE_ROLE=public` (bleibt als Alias für eine Übergangszeit).“
- Partner: „Basisansicht offen, Details + Steckbrief-Erzeugung (PDF) nur mit Partner-Passwort“. Steckbrief-Erzeugung und Fehler-Audit sind nie ohne Passwort erreichbar (Jan).
- Partner und Öffentlich schreiben nichts außer nach `/tmp`.
- „Der Export Stufe 0 wird mit dem **gleichen** Serializer erzeugt, der heute Stufe 0 ausliefert … Ein Test prüft, dass kein Feld aus `field_policy.INTERNAL_*`/`INTERNAL_FLAGS` im Export vorkommt.“
- Export-Abruf: `QE_EXPORT_SOURCE` (URL der Team-Instanz oder Dateipfad), Intervall `QE_EXPORT_POLL_MINUTES` (Vorschlag 10). Der letzte gültige Stand bleibt bei Fehlern erhalten; Kopie in `/tmp`.
- Live je Anfrage bleiben: Beispielinhalte (`/api/sources/{id}/contents`) und der Vorschaubild-Proxy.
- Der interne Port 9090 kommt erst in Etappe 3. In dieser Etappe liegt `/internal/exports/…` auf dem normalen Port und ist nur in der Rolle `team` vorhanden.
- Lint ist `python -m ruff check .` (ruff 0.12.9 wie in CI). Golden-Test, Neutralitätstest und alle bisherigen Tests bleiben grün.
- Arbeitsweise (Jan): regelmäßige Reviews mit Befundbehebung. Nach Task 3 und am Ende reviewt ein frischer Reviewer, Befunde werden per Test behoben.

## Review Focus

1. **Export-Quelle nicht erreichbar oder kaputt** (HTTP-Fehler, abgeschnittenes JSON, falsche Stufe im Dokument) → die Instanz behält den letzten gültigen Stand und loggt eine Warnung. Ohne jeden Stand meldet `/api/health` 503 statt Datensätze zu erfinden. Test in Task 5.
2. **Partner ohne `QE_TIER1_PASSWORD`** → Stufe 1 ist dort *nicht* offen (fail-closed, max. Stufe 0), mit Warnung im Log. Test in Task 1.
3. **Team-Routen auf Partner/Öffentlich** (`/api/stats/team`, `/api/protokoll.*`, `/jobs/refresh`, `/api/admin/reload`, `/internal/exports/…`) → 403/404, auch mit korrektem Team-Passwort-Header. Test in Task 4.
4. **Versteckte Datensätze**: BLACKLIST fehlt in jedem Export. ZWEITDATENSATZ ist nur in der Quelldatensatz-Ansicht (`has_node=true`) sichtbar, wie heute. Test in Task 3.
5. **Unverändertes Ergebnis**: Für die Filterkombinationen der Oberfläche liefern Export-Abfrage und alte Datensatz-Abfrage dieselben IDs in derselben Reihenfolge. Ausnahmen sind dokumentiert (Task 3). Test in Task 3.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `backend/config.py` | `ROLE`, `ROLE_MAX_TIER`, `EXPORT_SOURCE`, `EXPORT_POLL_MINUTES`; Alias `QE_PUBLIC_ONLY` |
| `backend/tiers.py` | Obergrenze aus der Rolle; Partner verlangt das Stufe-1-Passwort |
| `backend/exports.py` (neu) | `build_export(records, meta, tier)`, `write_exports(records, meta, dir)`, `etag(doc)`; Schema |
| `backend/export_query.py` (neu) | Filter/Sortierung/Blättern über den Export-Einträgen, Detail, Batch, Zeilen für CSV/JSON |
| `backend/export_store.py` (neu) | aktueller Export je Stufe im Speicher; Team: aus Datensätzen bauen; Partner/Öffentlich: laden, neu abfragen, `/tmp`-Kopie |
| `backend/app.py` | Stufe < 2 → `export_query` über `export_store`; Team-Routen nur in Rolle `team`; `/internal/exports/stufe{N}.json` mit ETag/304 |
| `backend/refresh.py` | nach dem Neubau auch die Exporte neu bauen |
| `frontend/src/app/app.component.ts` | Statusfilter nur zeigen, wenn Optionen vorhanden sind |
| `backend/tests/test_roles.py`, `test_exports.py`, `test_export_query.py`, `test_export_store.py` (neu) | Tests |
| `README.md`, `docs/datenaufbereitung.md` | Rollen, neue Variablen, Datenfluss |

## Export-Schema (gilt für Task 2–5)

```json
{
  "schema": 1, "tier": 0, "generatedAt": "<meta.generatedAt>",
  "meta": {"total": 0, "byKind": {}, "withFieldProfile": 0, "withNode": 0, "totalContents": 0,
           "wloProdContent": 0, "generatedAt": ""},
  "stats": {}, "filters": {},
  "items": [
    {"id": "node:…", "card": {}, "detail": {}, "row": {},
     "k": {"kind": "manuell", "node": true, "spider": false, "bq": true, "zweit": false,
           "oer": false, "fieldProfile": false, "contents": ["publisher", "Serlo"]}}
  ]
}
```

- `card` = `serialize.source(r, tier)` und `detail` = `serialize.source(r, tier, detail=True)`.
- `row` = `views.flat(r, team=False)`, nur bei `tier == 1`; bei Stufe 0 fehlt der Schlüssel.
- `stats`: Stufe 0 = `stats.compute_enduser_stats(visible, meta)`, Stufe 1 = `stats.compute_stats_full(records, meta)`.
- `filters` = `stats.compute_filter_options(records)` mit `"erschliessung": []`, weil die genauen Statuscodes intern sind.
- `k` enthält nur Wahrheitswerte und die öffentlichen Werte für die Live-Inhalte. Für Crawler mit Spider ist `contents` = `["replication_source", spider]`, sonst `["publisher", bezugsquelle or name]`; ohne Wert ist es `null`.
- In `items` stehen alle Datensätze außer BLACKLIST. ZWEITDATENSATZ ist enthalten, mit `k.zweit = true`.

---

### Task 1: Rollen in Konfiguration und Stufenmodell

**Files:**
- Modify: `backend/config.py`, `backend/tiers.py`, `backend/app.py` (`capabilities`)
- Test: `backend/tests/test_roles.py`

**Interfaces:**
- Produces:
  - `config.role() -> str` (`"team"|"partner"|"public"`) liest bei jedem Aufruf `QE_ROLE`. Fehlt der Wert, gilt bei `QE_PUBLIC_ONLY` wahr `"public"`, sonst `"team"`. Ein ungültiger Wert löst `ValueError` mit dem Wert im Text aus.
  - `config.ROLE_MAX_TIER = {"team": 2, "partner": 1, "public": 0}`
  - `config.PUBLIC_ONLY` bleibt als Name erhalten und bedeutet jetzt `role() == "public"`. Als Funktion: `config.public_only() -> bool`; die vier Aufrufstellen werden umgestellt.
  - `tiers.max_tier(...)` begrenzt mit `ROLE_MAX_TIER[config.role()]`.
  - In der Rolle `partner` ist Stufe 1 nur mit gesetztem *und* passendem `QE_TIER1_PASSWORD` erreichbar. Team-Login (Cookie oder Header) zählt dort nicht.
  - `tiers.is_team(...)` ist außerhalb der Rolle `team` immer `False`.
  - `/api/capabilities` gibt zusätzlich `"role"` aus. `teamAvailable` ist nur in der Rolle `team` wahr. `tier1Gated` ist in der Rolle `partner` immer wahr.

- [ ] **Step 1: Failing tests** in `test_roles.py`. Sie setzen die Umgebung per `monkeypatch` und nutzen den `_req()`-Helfer aus `test_tiers.py`, kopiert:
  - `test_role_default_is_team` prüft `config.role() == "team"`.
  - `test_public_only_alias` mit `QE_PUBLIC_ONLY=1` und ohne `QE_ROLE` prüft `role() == "public"` und `max_tier(_req(), None, "test-team-pw", None) == 0`.
  - `test_invalid_role_raises`: Bei `QE_ROLE=admin` löst `role()` einen `ValueError` mit `"admin"` im Text aus.
  - `test_partner_caps_at_1_and_ignores_team`: Mit `QE_ROLE=partner` und `QE_TIER1_PASSWORD=p` ergibt `max_tier(_req(), None, "test-team-pw", None)` 0 und `max_tier(_req(), None, None, "p")` 1.
  - `test_partner_without_tier1_pw_is_closed` (Review Focus 2): Mit `QE_ROLE=partner` und leerem `QE_TIER1_PASSWORD` ergibt `max_tier(_req(), None, None, None)` 0.
  - `test_is_team_false_outside_team_role` prüft beide Rollen mit korrektem Header.
  - `test_capabilities_reports_role(client)`: Antwort enthält `role == "team"`.
- [ ] **Step 2:** Run `cd backend && python -m pytest tests/test_roles.py -q`. Expected: FAIL (`config.role` fehlt).
- [ ] **Step 3: Implement.**
  - `TIER1_PW` und `TEAM_PW` bleiben Modulkonstanten.
  - Die Partner-Regel liest `config.TIER1_PW` zur Laufzeit; die Tests setzen sie per `monkeypatch.setattr`.
  - Beim Start in der Rolle `partner` ohne `TIER1_PW` wird im Lifespan eine Warnung geloggt.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: alles grün.
- [ ] **Step 5: Commit** `feat: Rollen team/partner/public begrenzen die Zugangsstufe`

### Task 2: Export je Stufe bauen

**Files:**
- Create: `backend/exports.py`
- Test: `backend/tests/test_exports.py`

**Interfaces:**
- Consumes:
  - `serialize.source(r, tier, detail=False)`
  - `views.flat(r, team=False)`
  - `stats.compute_enduser_stats(recs, meta)`, `stats.compute_stats_full(recs, meta)`, `stats.compute_filter_options(recs)`
  - `filtering.filter_records` für die sichtbare Menge
- Produces:
  - `exports.SCHEMA = 1`
  - `exports.build_export(records: list[dict], meta: dict, tier: int) -> dict` im Export-Schema oben; `tier` muss 0 oder 1 sein, sonst `ValueError`.
  - `exports.etag(doc: dict) -> str` ist der SHA-256 über das kompakte JSON mit `sort_keys=True` und `ensure_ascii=False`, in Anführungszeichen, wie ein HTTP-ETag.
  - `exports.dumps(doc) -> bytes` erzeugt genau diese kompakte Form.
  - `exports.write_exports(records, meta, out_dir: Path) -> dict[int, str]` schreibt `stufe0.json` und `stufe1.json` atomar (Temp-Datei + `os.replace`) und gibt `{tier: etag}` zurück.
  - `exports.validate(doc, tier) -> None` löst `ValueError` aus bei falschem `schema` oder `tier` oder wenn `items`, `stats`, `filters` oder `meta` fehlen.

- [ ] **Step 1: Failing tests.** Als Daten dient der Golden-Fixture-Lauf, wie in `test_golden.py`: `build_golden` erzeugt die Records.
  - `test_no_internal_in_export` (Spec-Abnahme), für Stufe 0 und 1:
    - Der Test läuft rekursiv über alle Schlüssel und Strings.
    - Kein Schlüssel kommt aus `field_policy.NODE_INTERNAL`, `CRAWLER_INTERNAL_KEYS` oder `{"internal", "provenance", "flags", "confidence", "related", "familyCount", "bind"}`.
    - Kein String ist gleich einem Element von `field_policy.INTERNAL_FLAGS`.
    - Kein `erschliessungsstatus` matcht `^\d+\.`.
  - `test_blacklist_absent_zweit_marked` (Review Focus 4): Keine ID eines Records mit BLACKLIST steht in `items`. Jeder Record mit ZWEITDATENSATZ steht mit `k.zweit is True` darin.
  - `test_card_detail_match_serializer`: Für jeden Eintrag gilt `card == serialize.source(r, tier)` und `detail == serialize.source(r, tier, detail=True)`.
  - `test_row_only_tier1`: Bei Stufe 1 gilt `"row" in item`, bei Stufe 0 nicht.
  - `test_filters_without_erschliessung`: `doc["filters"]["erschliessung"] == []`.
  - `test_write_exports_atomic_and_etag(tmp_path)`:
    - Beide Dateien existieren.
    - `etag(json.loads(file)) == rückgabe[tier]`.
    - Ein zweiter Lauf mit gleichen Daten ergibt gleiche ETags.
  - `test_validate_rejects_wrong_tier`: `validate(build_export(..., 0), 1)` löst `ValueError` aus.
- [ ] **Step 2:** Run `python -m pytest tests/test_exports.py -q`. Expected: FAIL (Modul fehlt).
- [ ] **Step 3: Implement** `exports.py` nach Schema. `items` = alle Records ohne BLACKLIST, in Record-Reihenfolge; `k.oer` = `"OER" in r["flags"]`, `k.fieldProfile` = `bool(r.get("fieldGeneration"))`; `meta` = genau die sieben Schlüssel des Schemas.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: Exporte je Stufe aus dem Stufen-Serializer`

### Task 3: Abfragen über den Export

**Files:**
- Create: `backend/export_query.py`
- Test: `backend/tests/test_export_query.py`

**Interfaces:**
- Consumes: Export-Schema (Task 2); die Filter-Dict-Form von `app._filters` mit den Schlüsseln `q, subject, level, erschliessung, oer, crawler, min_count, flag, show_blacklist, sort, order, only_field_profile, has_node, has_bezugsquelle, has_spider, lrt`.
- Produces:
  - `export_query.query(doc: dict, f: dict) -> list[dict]`: gefilterte, sortierte Einträge. `flag`, `show_blacklist` und `erschliessung` werden ignoriert, wie heute unter Stufe 2.
  - `export_query.page(doc, f, page: int, page_size: int) -> dict` liefert dieselbe Antwortform wie heute `/api/sources` unter Stufe 2: `tier, total, page, pageSize, pages, items` mit `items = [e["card"]…]`, ohne `hidden`.
  - `export_query.detail(doc, source_id) -> dict | None`
  - `export_query.batch(doc, ids: list[str]) -> list[dict]` (höchstens 100)
  - `export_query.rows(doc, f) -> list[dict]` liefert die `row`-Werte; nur bei Stufe 1 vorhanden.
  - `export_query.contents_target(doc, source_id) -> tuple[str, str] | None` liefert Profil-Feldschlüssel und Wert aus `k.contents`.
  - `export_query.index(doc) -> dict[str, dict]` (ID → Eintrag), einmal je Dokument berechnet.

Abbildung der Filter auf die Einträge (alle Vergleiche wie in `filtering.filter_records`: Teilstring ohne Groß-/Kleinschreibung):

| Filter | Feld |
|---|---|
| Ausblenden | `k.zweit` versteckt, außer `has_node is True` |
| `has_node` / `has_bezugsquelle` / `has_spider` | `k.node` / `k.bq` / `k.spider` |
| `oer` | `k.oer` |
| `min_count` | `card.contentCount` |
| `only_field_profile` | `k.fieldProfile` |
| `lrt` / `subject` / `level` | `card.contentTypes` / `card.subjects` / `card.educationalContext` |
| `q` | `card.name`, `card.bezugsquelle`, `card.description`, `card.subjects` |
| `crawler` | `k.kind == "crawler"` |
| Sortierung | `contentCount` (Zahl) oder `name` (klein), `order` wie heute; Python-`sorted` ist stabil, Ausgangsreihenfolge = Reihenfolge der Datensätze |

Dokumentierte Abweichung: `q` sucht in `card.description`, also inklusive der Bezugsquellen-Ergänzung. Heute sucht `q` nur in der Beschreibung des Datensatzes. Die Abweichung ist erwünscht: Gefunden wird, was man sieht.

- [ ] **Step 1: Failing tests.**
  - `test_equivalence_with_record_query` (Review Focus 5):
    - Das Fixture baut Golden-Records und beide Exporte.
    - Für Stufe 0 und 1 und für jede Kombination aus der Liste `CASES` gilt: `[e["id"] for e in query(doc, f)] == [r["id"] for r in app._query_records(tier, **f)]`.
    - `CASES` umfasst: Standard; `has_node=True`; `has_node=False`; `has_bezugsquelle=True`; `has_spider=True`; `crawler=True`; `oer=True`; `min_count=0`; `sort="name", order="asc"`; `subject=<erstes Fach aus filters>`; `level=…`; `lrt=…`; `only_field_profile=True`.
    - `q` wird mit einem Namensteil getestet, der in keiner Ergänzung vorkommt.
  - `test_zweit_only_in_node_view` (Review Focus 4)
  - `test_team_filters_ignored`: Mit `flag="BLACKLIST"`, `show_blacklist=True` und `erschliessung="9."` ist das Ergebnis gleich dem Standard.
  - `test_page_shape`: `page(doc, f, 2, 5)` enthält `total`, `pages` und 5 Karten und keinen Schlüssel `hidden`.
  - `test_detail_batch_contents`: `detail` gleich dem gespeicherten `detail`; unbekannte ID → `None`; `batch` mit 150 IDs → höchstens 100; `contents_target` eines Crawlers = `("replication_source", spider)`.
- [ ] **Step 2:** Run `python -m pytest tests/test_export_query.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `export_query.py`. Den Index speicherst du im Dokument unter einem privaten Schlüssel `_index`, damit er nicht jede Anfrage neu entsteht. `exports.dumps` schreibt Schlüssel mit `_` nicht mit.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: Listen, Detail und Batch aus dem Export`
- [ ] **Step 6: Zwischenreview (Jan: regelmäßige Reviews).**
  - Erzeuge ein Review-Paket über Task 1–3 und gib es einem frischen Reviewer (fähigstes Modell, `code-reviewer.md`, mit diesem Plan und der Spec).
  - Behebe Critical- und Important-Befunde jeweils mit einem Test, der vorher fehlschlägt, und halte sie im Ledger fest.
  - Minor-Befunde notierst du im Ledger.

### Task 4: App liest unter Stufe 2 aus dem Export; Team veröffentlicht Exporte

**Files:**
- Create: `backend/export_store.py` (Teil Team)
- Modify: `backend/app.py`, `backend/refresh.py`, `frontend/src/app/sources.service.ts`, `frontend/src/app/app.component.ts` (Filteroptionen mit Stufe)
- Test: `backend/tests/test_export_store.py`, `backend/tests/test_roles.py` (Routen); Frontend: `npm test`

**Interfaces:**
- Consumes: `exports.build_export/write_exports/etag/dumps/validate`, `export_query.*`, `store._DATA`
- Produces:
  - `export_store.current(tier: int) -> dict | None` für tier ∈ {0, 1}.
  - `export_store.etag(tier) -> str | None`
  - `export_store.rebuild_from_records(records, meta, out_dir: Path | None) -> None` baut beide Exporte in den Speicher und schreibt sie, wenn `out_dir` gesetzt ist.
  - `export_store.set_doc(tier, doc) -> None` validiert und tauscht das Dokument atomar.
  - App, Rolle `team`:
    - Nach `store.load()` (Lifespan, `admin_reload`, `refresh._run_refresh`) wird `rebuild_from_records(_DATA["records"], _DATA["meta"], config.data_dir() / "exports")` aufgerufen.
    - Schlägt das Schreiben fehl (z. B. bei schreibgeschütztem Dateisystem), wird nur geloggt; der Speicher-Export gilt trotzdem.
  - App-Routen mit Stufe < 2 bedienen sich aus `export_store.current(tier)` über `export_query`:
    - `/api/sources` nutzt `page`; `/api/sources/{id}` nutzt `detail`.
    - `/api/sources/batch` nutzt `batch`.
    - `/api/export.json|csv` nutzt `rows`, nur Stufe 1.
    - `/api/stats` nutzt `doc["stats"]`; `/api/meta/filters` nutzt `doc["filters"]` für die höchste Stufe der Rolle, wenn sie unter 2 liegt.
    - `/api/sources/{id}/contents` nutzt `contents_target` und `repo_profile.get().felder[key]`.
    - Bei Stufe 2 bleibt alles wie heute.
  - `/api/meta/filters`:
    - Mit `?tier=2` und Team-Recht gibt es die volle Liste, sonst die aus dem Export der Stufe `min(1, maximal erlaubt)`.
    - Die Route bekommt dafür `Depends(tiers.effective_tier)`. Das Frontend fragt sie heute **ohne** `tier` ab: `sources.service.ts` `filterOptions()` bekommt den Parameter `tier` wie `list()`; `app.component.ts` lädt die Optionen neu, wenn sich die Stufe ändert. Sonst verliert das Team den Statusfilter.
  - `/internal/exports/stufe{tier}.json` gibt es nur in der Rolle `team`, sonst 404:
    - Antwort sind die `exports.dumps`-Bytes mit `ETag`.
    - Bei passendem `If-None-Match` kommt 304 ohne Body.
  - Fehlt in der Rolle `team` der Export noch, antworten die Routen mit 503 und dem Text `"Daten werden geladen"`.
  - Team-Routen geben außerhalb der Rolle `team` 404 zurück: `/api/stats/team`, `/api/protokoll.*`, `/jobs/refresh`, `/api/admin/reload`, `/internal/exports/*`. Dafür gibt es einen Router, der nur bei `config.role() == "team"` eingebunden wird, oder eine Dependency `require_team_role`. Wichtig ist nur: 404, nicht 403.

- [ ] **Step 1: Failing tests.**
  - `test_tier0_list_comes_from_export(client)`:
    - Die Liste `/api/sources` ist gleich `export_query.page(export_store.current(0), …)`.
    - Kein Eintrag enthält `flags` oder `bind`.
  - `test_internal_export_etag_304(client, team_pw)`:
    - Der erste Abruf liefert 200 mit `ETag`.
    - Der zweite mit `If-None-Match` liefert 304.
    - `stufe2.json` liefert 404.
  - `test_team_routes_404_outside_team(monkeypatch)` (Review Focus 3): Für `QE_ROLE=partner` und `public` wird mit Export-Datei (Task 5) eine frische App gebaut, siehe Task 5, Step 3. Hier zuerst mit einer `require_team_role`-Dependency und `monkeypatch.setattr(config, "role", lambda: "partner")` am bestehenden Client:
    - Alle fünf Routen liefern 404, auch mit `X-Team-Password`.
  - `test_refresh_rebuilds_exports(tmp_path, monkeypatch)`:
    - Nach `refresh._run_refresh()` (mit gestubbtem fetcher und truth wie in `test_reload_supplements.py`) existiert `exports/stufe0.json` im Datenverzeichnis.
  - `test_tier2_list_unchanged(client, team_pw)`: Die Stufe-2-Liste enthält weiter `flags` und `hidden`.
- [ ] **Step 2:** Run `python -m pytest tests/test_export_store.py tests/test_roles.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Die bisherigen Tests in `test_routes.py` und `test_tiers.py` müssen unverändert grün bleiben. Bricht einer, ist das ein Befund: Grund klären, nicht den Test anpassen. Eine Ausnahme ist nur die dokumentierte `q`-Abweichung, und die steht im Ledger.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: Stufe 0/1 aus dem Export, Team veröffentlicht Exporte mit ETag`

### Task 5: Partner/Öffentlich laden nur ihren Export

**Files:**
- Modify: `backend/export_store.py`, `backend/config.py`, `backend/app.py` (Lifespan, Health)
- Test: `backend/tests/test_export_store.py`

**Interfaces:**
- Consumes: `exports.validate`, `exports.dumps`, `exports.etag`
- Produces:
  - `config.EXPORT_SOURCE` (`QE_EXPORT_SOURCE`) als Vorlage mit `{tier}`, z. B. `http://quellenpanel-team:8080/internal/exports/stufe{tier}.json` oder `/mnt/exports/stufe{tier}.json`.
  - `config.EXPORT_POLL_MINUTES` (`QE_EXPORT_POLL_MINUTES`, Standard 10, 0 = aus)
  - `export_store.load_remote(tier: int) -> bool`:
    - Holt die Quelle (URL über `urllib.request` mit `If-None-Match` des aktuellen ETags, Timeout 20 s, oder Datei) und validiert sie.
    - Bei Erfolg wird sie gesetzt und nach `/tmp/quellenpanel-stufe{tier}.json` geschrieben; Rückgabe `True`.
    - Bei 304 ist die Rückgabe `True` ohne Änderung.
    - Bei Fehler wird geloggt, der alte Stand bleibt, Rückgabe `False`.
  - `export_store.load_tmp(tier) -> bool` liest die `/tmp`-Kopie beim Start, bevor die Quelle erreichbar ist.
  - `export_store.start_polling(tier, minutes)` startet einen Daemon-Thread; bei `minutes == 0` passiert nichts.
  - Lifespan in der Rolle `partner` oder `public`:
    - Es wird kein `store.load()` aufgerufen; `truth.json` wird nicht gelesen, die Datensätze bleiben leer.
    - Zuerst kommt `load_tmp`, dann `load_remote`, dann `start_polling`.
    - Geladen werden die Stufen der Rolle: Partner 0 und 1, Öffentlich 0.
    - Ohne `QE_EXPORT_SOURCE` baut die Instanz die Exporte einmal aus der lokalen `truth.json` und verwirft danach die Datensätze (`_DATA["records"] = []`). Das ist ein Übergang, bis Etappe 3 die Daten aus dem Image nimmt; es gibt eine Warnung im Log.
  - `/api/health`:
    - In der Rolle `team` wie heute.
    - Sonst bei vorhandenem Export der höchsten Stufe der Rolle `{"status": "ok", "records": len(items), "role": …}`.
    - Ohne Export 503 mit `{"status": "starting"}`.

- [ ] **Step 1: Failing tests**, mit Export-Dateien aus Task 2 im `tmp_path`:
  - `test_load_from_file_source`: `QE_EXPORT_SOURCE=<tmp>/stufe{tier}.json` → `load_remote(0)` ist `True` und `current(0)["tier"] == 0`.
  - `test_broken_source_keeps_last_good` (Review Focus 1):
    - Erst die gültige Datei laden.
    - Dann die Datei mit abgeschnittenem JSON überschreiben, dann mit `tier: 1` in `stufe0.json`: `load_remote(0)` ist `False`, `current(0)` ist unverändert, und im `caplog` steht eine Warnung.
  - `test_http_source_etag_304(monkeypatch)`:
    - `urllib.request.urlopen` wird durch eine Fake-Funktion ersetzt, die den `If-None-Match`-Header prüft und `HTTPError` 304 wirft.
    - Ergebnis: `True` und Dokument unverändert.
  - `test_tmp_copy_used_on_start(tmp_path, monkeypatch)`: `/tmp`-Pfad über `export_store.TMP_DIR` (monkeypatchbar) → nach `load_remote` existiert die Kopie, und `load_tmp(0)` stellt sie in einem frischen Zustand wieder her.
  - `test_public_app_serves_only_export(monkeypatch, tmp_path)`:
    - Mit `QE_ROLE=public` und Export-Dateien wird ein frisches `TestClient(app)` gestartet; Lifespan läuft.
    - `/api/health` liefert 200 mit `role == "public"`, `/api/sources?tier=2` liefert `tier == 0`, `store._DATA["records"] == []`.
    - Die fünf Team-Routen liefern 404 (Review Focus 3).
  - `test_public_health_503_without_export`: Bei `QE_ROLE=public`, Quelle zeigt ins Leere, keine `/tmp`-Kopie, und `truth.json` darf nicht als Fallback dienen (Quelle ist gesetzt): `/api/health` liefert 503.
  - `test_partner_without_source_builds_from_truth`: Ohne `QE_EXPORT_SOURCE` ist Stufe 1 vorhanden, die Datensätze sind leer, und eine Warnung wurde geloggt.
- [ ] **Step 2:** Run `python -m pytest tests/test_export_store.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Der Lifespan muss den Rollenwert *beim Start* lesen (`config.role()`), damit Tests die App mit gesetzter Umgebung frisch starten können. Den Poll-Thread nach dem Vorbild von `refresh.start_scheduler` als Daemon bauen.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: Partner und Öffentlich laden nur ihren Export (Datei/URL, ETag, letzter gültiger Stand)`

### Task 6: Frontend, Doku, Abschlussprüfung

**Files:**
- Modify: `frontend/src/app/app.component.ts` (Statusfilter in `@if ((options?.erschliessung ?? []).length) { … }` einschließen); Test in der vorhandenen Spec-Datei der Komponente, falls eine existiert, sonst Ruling
- Modify: `README.md` (Rollen-Tabelle, Variablen `QE_ROLE`, `QE_EXPORT_SOURCE`, `QE_EXPORT_POLL_MINUTES`, Hinweis Alias `QE_PUBLIC_ONLY`), `docs/datenaufbereitung.md` (Schritt ④ Exporte im Prozessbild), `Dockerfile`-Kommentar (Rollen statt `QE_PUBLIC_ONLY`)

- [ ] **Step 1:** Frontend-Änderung, danach `cd frontend && npm test -- --watch=false`. Expected: grün.
- [ ] **Step 2:** Doku wie oben.
- [ ] **Step 3: Volle Prüfung.**
  - `cd backend && python -m ruff check . && python -m pytest -q`, Expected: grün.
  - Docker-Image bauen (wie in Etappe 1; in der Cloud mit Proxy-CA über eine Scratch-Kopie).
  - Zwei Container starten:
    - Team: `QE_ROLE=team`.
    - Öffentlich: `QE_ROLE=public` mit `QE_EXPORT_SOURCE=http://<team>:8080/internal/exports/stufe{tier}.json` im selben Docker-Netz.
  - Prüfen: Die öffentliche `/api/health` liefert ok, `/api/sources?tier=2` liefert `tier: 0`, und `/api/protokoll.md` liefert 404.
- [ ] **Step 4: Commit und Push** `docs: Rollen und Exporte dokumentiert`; PR-Beschreibung um Etappe 2 ergänzen.
- [ ] **Step 5: Abschlussreview** über die ganze Etappe mit frischem Reviewer, Befundbehebung per Test, Bericht an Jan.
