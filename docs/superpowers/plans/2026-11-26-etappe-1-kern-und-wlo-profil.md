# Etappe 1 – Kern und WLO-Profil – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den Datenkern repository-neutral machen: Alles WLO-Spezifische (Property-Namen, URIs, Sonderfall-Spider, Crawler-Spalten, Korrekturen) kommt aus `profiles/wlo/`, die Korrekturen liegen in einer einzigen Semikolon-CSV im Langformat, und aus denselben Eingaben entsteht exakt dieselbe Datenwahrheit wie vorher.

**Architecture:** Ein neues Modul `profile.py` lädt `profiles/<id>/profil.toml` in eine unveränderliche `Profile`-Dataclass. Ein neues Modul `korrekturen.py` liest und schreibt die Korrektur-CSV und liefert die beiden Formen, die der bestehende Code heute nutzt (Node-Korrekturen und Supplements). Die Module `truth_*`, `fetcher`, `wlo_content`, `filtering`, `stats_team`, `protokoll`, `enduser` und `config` lesen Konstanten nur noch aus dem Profil. Ein Golden-Test, der *vor* dem Umbau aufgenommen wird, sichert, dass `truth.build()` byte-gleich bleibt.

**Tech Stack:** Python 3.12 (`tomllib`, `csv`, `dataclasses`), FastAPI, pytest. Keine neuen Abhängigkeiten.

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` (Abschnitte 6.3, 6.4, 8 Etappe 1, 9)

## Global Constraints

- Keine neue Laufzeit-Abhängigkeit. TOML über `tomllib` aus der Standardbibliothek.
- Korrektur-CSV: UTF-8 **mit BOM**, Trennzeichen `;`, Kopfzeile genau `Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am`.
- `Typ` ∈ {`node`, `spider`, `bezugsquelle`}. `Aktion` ∈ {`blacklist`, `whitelist`, `vermerk`, `bezugsquelle_setzen`, `spider_setzen`, `beschreibung`, `vorschaubild`}.
- `QE_PROFILE` (Standard `wlo`) wählt das Profil, `QE_PROFILES_DIR` (Standard `<repo>/profiles`) den Ordner. `QE_DATA_DIR` (Standard `backend/data`) ist der Datenordner, Roh-Caches liegen in `<QE_DATA_DIR>/raw`.
- Env-Variablen `QE_REPO_URL` und `QE_SEARCH_URL` bleiben gültig und haben Vorrang vor dem Profil.
- Golden-Gleichheit: `truth.build()` auf dem Golden-Fixture liefert nach jeder Task dasselbe JSON wie vor Task 1 (`json.dumps(..., sort_keys=True, ensure_ascii=False)` gleich).
- Neutralität: In `backend/*.py` (ohne `tests/`) kommen die Zeichenketten `ccm:oeh_`, `wirlernenonline`, `mds_oeh` und `openeduhub` nicht mehr vor.
- `field_policy.py` bleibt die einzige Stelle, die öffentlich und intern trennt. Das Profil liefert nur die Zuordnung von CSV-Spaltennamen zu Schlüsseln.
- Die gebündelte `backend/data/truth.json` wird in dieser Etappe **nicht** neu erzeugt.
- Nicht in dieser Etappe: Daten aus dem Image entfernen, Rollen, Ports, Logs und UI. Das kommt in Etappe 2 bis 6.

## Review Focus

1. **Korrektur-CSV aus Excel gespeichert** (BOM, CRLF, leere Spalten am Ende, manchmal `,` statt `;`) → wird gelesen wie heute (Trennzeichen erkennen). Test in Task 3.
2. **Fehlerhafte Zeile** (unbekannte Aktion, ungültige UUID bei `Typ=node`, leerer Schlüssel) → Zeile wird übersprungen und in `KorrekturSet.fehler` mit Zeilennummer festgehalten, nichts stürzt ab. Test in Task 3.
3. **Widersprüchliche Zeilen** (dieselbe Node erst `whitelist`, dann `blacklist`) → die letzte Zeile gewinnt wie heute, und in `KorrekturSet.warnungen` steht ein Eintrag. Test in Task 3.
4. **Fehlende Dateien** (kein `crawler.csv`, kein `korrekturen.csv`, keine Roh-Caches außer `quellen_nodes.json`) → `build()` läuft mit leeren Profilen und Korrekturen weiter wie heute. Test in Task 5.
5. **Unbekanntes Profil** (`QE_PROFILE=gibtsnicht`) → `ProfileError` mit dem gesuchten Pfad im Text, kein `KeyError` irgendwo tief im Merge. Test in Task 2.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `profiles/wlo/profil.toml` | WLO-Werte: Repository, Property-Namen, Qualitätsfelder, Sonderfall-Spider, Crawler-Spalten, Branding |
| `profiles/wlo/daten/crawler.csv` | verschoben von `backend/data/inputs/datencrawler.csv` (Inhalt unverändert) |
| `profiles/wlo/daten/korrekturen.csv` | migriert aus `quellen_korrektur.csv` + `source_supplements.json` |
| `profiles/beispiel/profil.toml` | minimales Fremdprofil (nur Standard-edu-sharing-Properties) als Neutralitätsbeweis |
| `backend/profile.py` | `Profile`, `ProfileError`, `load_profile`, `get`, `reset` |
| `backend/korrekturen.py` | `Korrektur`, `KorrekturSet`, `load_korrekturen`, `write_korrekturen` |
| `backend/tools/migrate_korrekturen.py` | einmalige Migration alt → Langformat, mit Bericht |
| `backend/config.py` | Datenpfade (`DATA_DIR`, `RAW_DIR`, `crawler_csv_path()`, `korrekturen_csv_path()`), URLs aus dem Profil |
| `backend/truth_loaders.py`, `truth_text.py`, `truth_record.py`, `truth.py` | lesen Konstanten aus `profile.get()` |
| `backend/fetcher.py`, `wlo_content.py`, `app.py` | Endpunkte und Properties aus dem Profil |
| `backend/filtering.py`, `stats_team.py`, `protokoll.py`, `enduser.py` | Sonderfall-Spider, Property-Namen und Supplements aus Profil bzw. Korrekturen |
| `backend/tests/fixtures/golden/…` | synthetischer Roh-Datensatz + erwartete Ausgabe |
| `backend/tests/test_golden.py`, `test_profile.py`, `test_korrekturen.py`, `test_migration.py`, `test_neutral.py` | Tests |
| entfernt: `backend/data/inputs/`, `backend/data/source_supplements.json` | ersetzt durch das Profil |

---

### Task 1: Golden-Fixture und Referenzausgabe (vor jedem Umbau)

**Files:**
- Create: `backend/tests/fixtures/golden/raw/quellen_nodes.json`, `extra_nodes.json`, `cache_facet_bezugsquellen.json`, `cache_facet_spider.json`, `vocab_sources.json`, `bq_previews.json`, `cache_meta.json`, `replication_publisher_gap.csv`
- Create: `backend/tests/fixtures/golden/alt/datencrawler.csv`, `alt/quellen_korrektur.csv`, `alt/source_supplements.json`
- Create: `backend/tests/fixtures/golden/expected_records.json`, `expected_cards.json`
- Create: `backend/tests/fixtures/golden/regenerate.py`
- Test: `backend/tests/test_golden.py`

**Interfaces:**
- Produces: `tests/test_golden.py::build_golden(monkeypatch) -> list[dict]`. Nach Task 5 wird nur der Rumpf dieses Helfers ausgetauscht, die erwarteten Dateien bleiben unverändert.
- Produces: Fixture-Layout `raw/` (Roh-Caches, auch `replication_publisher_gap.csv`) und `alt/` (Kuratierdateien im alten Format).

- [ ] **Step 1: Fixture-Daten schreiben.** Kleine handgeschriebene JSON- und CSV-Dateien im Format der echten Caches (Form von `fetcher.refresh_all`, Felder wie in `truth_loaders._parse_node`). Jede Zeile der Tabelle muss durch mindestens einen Datensatz abgedeckt sein:

| Fall | Erwartete Wirkung |
|---|---|
| Crawler-Spider mit Node über `ccm:general_identifier` | Datensatz `crawler:<spider>` mit Node |
| Crawler ohne suchbaren Node, Node-ID über die Spalte `Quelldatensatz (Prod)` in `extra_nodes.json` | Node wird angehängt |
| Crawler, dessen dominanter Publisher (`replication_publisher_gap.csv`) in der BQ-Facette steht | BQ = Top-Publisher |
| Crawler mit BQ `0` in der CSV | Junk-BQ wird ignoriert |
| zwei manuelle Nodes mit demselben Publisher, einer davon mit repräsentativem Titel | einer primär, der andere `ZWEITDATENSATZ` |
| manueller Node, kein Titel repräsentiert die BQ | Name wird zur BQ (Umbenennung, Variante A) |
| BQ-Facette ohne Node, zusätzlich Schreibvariante `Klicksafe`/`klicksafe` | zwei Datensätze `bq:klicksafe` und `bq:klicksafe#2` |
| Publisher `WirLernenOnline` (Platzhalter) | wird nicht als BQ benutzt |
| Node mit `ccm:replicationsource=wirlernenonline_spider` | Flag `WLO_MIGRATION`, kein Crawler-Anker |
| Node mit Legacy-URI `…/vocabs/sources/<uuid>` als replicationsource | `LEGACY_BINDUNG`, Vokabelname aufgelöst |
| Node mit zwei LRT-Werten | `FEHLTAGGING` |
| Node mit Spider-Bindung, LRT ohne „Quelle“ | `TYP_NICHT_QUELLE` |
| Korrektur `blacklist` / `whitelist` / leere Liste / doppelte Node-ID | Flags `BLACKLIST`/`WHITELIST`, intern `Korrekturliste` = `—` bei leerer Liste, letzte Zeile gewinnt |
| verrutschte Korrekturzeile (Spalte `Liste` leer, `blacklist` in Spalte `Spider`) | wirkt heute nicht (Liste leer) |
| `wf_status` außerhalb von `150_PUBLISH_IN_SEARCH`/`155_ELEMENT_UNLOCK_BUFFET` | `NICHT_PUBLIZIERT` |
| BQ `YouTube - Kanal X` neben BQ `YouTube` | `BQ_SUBCHANNEL` |
| Qualitätsfelder (mindestens drei, eines mit `★`) und Altersbereich 6–10 | `quality` gefüllt, `Alter` = `6–10 Jahre` |
| Supplement für eine node-lose BQ mit leerer Beschreibung | Karte zeigt die Supplement-Beschreibung |

- [ ] **Step 2: `regenerate.py` schreiben.** Das Skript nimmt den Fixture-Ordner als Argument, setzt `truth_loaders.RAW = raw/`, `DATENCRAWLER = alt/datencrawler.csv`, `KORREKTUR = alt/quellen_korrektur.csv`, `truth_loaders.ROOT` auf einen temporären Ordner, in den es `raw/replication_publisher_gap.csv` nach `quellen-analyse/data/replication_publisher_gap.csv` kopiert (so liest der alte Loader die Datei), und `enduser._SUPPLEMENTS` aus `alt/source_supplements.json`. Dann ruft es `truth.build()` auf und schreibt `expected_records.json` (`sort_keys=True`, `indent=1`, `ensure_ascii=False`) sowie `expected_cards.json` = `[enduser.card(r) for r in records]`. Kopf des Skripts: „Nur einmal vor Etappe 1 ausführen; danach ist die Ausgabe die Referenz.“

- [ ] **Step 3: Referenz erzeugen.** Run: `cd backend && python tests/fixtures/golden/regenerate.py tests/fixtures/golden`. Expected: beide Dateien entstehen, `expected_records.json` enthält jeden Fall aus der Tabelle (von Hand prüfen: `grep -c ZWEITDATENSATZ`, `BQ_SUBCHANNEL`, `bq:klicksafe#2`).

- [ ] **Step 4: Test schreiben.**

```python
def test_truth_build_matches_golden(monkeypatch):
    records = build_golden(monkeypatch)
    expected = json.loads((FIX / "expected_records.json").read_text(encoding="utf-8"))
    assert _canon(records) == _canon(expected)

def test_cards_match_golden(monkeypatch):
    records = build_golden(monkeypatch)
    expected = json.loads((FIX / "expected_cards.json").read_text(encoding="utf-8"))
    assert _canon([enduser.card(r) for r in records]) == _canon(expected)
```

`_canon(x) = json.dumps(x, sort_keys=True, ensure_ascii=False)`. `build_golden` verwendet dieselbe Patch-Logik wie `regenerate.py`, über `monkeypatch.setattr`.

- [ ] **Step 5: Run.** `cd backend && python -m pytest tests/test_golden.py -v`. Expected: 2 passed. Danach die ganze Suite: `python -m pytest -q`, Expected: 46 passed.

- [ ] **Step 6: Commit.** `git add backend/tests/fixtures/golden backend/tests/test_golden.py && git commit -m "test: Golden-Fixture der Datenwahrheit vor dem Profil-Umbau"`

---

### Task 2: Profil-Lader und WLO-Profil

**Files:**
- Create: `backend/profile.py`, `profiles/wlo/profil.toml`
- Test: `backend/tests/test_profile.py`

**Interfaces:**
- Produces:
  - `class ProfileError(Exception)`
  - `@dataclass(frozen=True) class Profile` mit den Feldern `id: str`, `name: str`, `root: Path`, `repo_url: str`, `search_url: str`, `mds: str`, `vocab_sources_url: str`, `quelle_property: str`, `quelle_werte: tuple[str, ...]`, `felder: Mapping[str, str]`, `qualitaet: tuple[tuple[str, str], ...]`, `spider_kennung: str`, `ignore_spiders: frozenset[str]`, `migration_spiders: frozenset[str]`, `migration_quelle: str`, `platzhalter_bq: frozenset[str]`, `lrt_quelle_stichwort: str`, `publiziert_wf: tuple[str, ...]`, `crawler_spalten: Mapping[str, str]`, `crawler_spider_spalte: str`, `crawler_quelldatensatz_spalte: str`, `branding: Mapping[str, str]`, plus die Property `daten_dir -> Path` (= `root / "daten"`)
  - `load_profile(profile_id: str, profiles_dir: Path) -> Profile`
  - `get() -> Profile`: gecacht, liest `QE_PROFILE` (Standard `wlo`) und `QE_PROFILES_DIR` (Standard `Path(__file__).parent.parent / "profiles"`)
  - `reset() -> None`: leert den Cache (für Tests)
  - `REQUIRED_FELDER: tuple[str, ...]`: die Schlüssel aus `[felder]` unten

- [ ] **Step 1: `profiles/wlo/profil.toml` schreiben.** Die Werte sind exakt aus dem heutigen Code übernommen:

```toml
id = "wlo"
name = "WirLernenOnline"

[repository]
url = "https://redaktion.openeduhub.net"
search_url = "https://suche.wirlernenonline.de"
mds = "mds_oeh"
vocab_sources_url = "https://vocabs.openeduhub.de/w3id.org/openeduhub/vocabs/sources/index.json"
quelle_property = "ccm:oeh_lrt_aggregated"
quelle_werte = ["http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/2e678af3-1026-4171-b88e-3b3a915d1673"]

[felder]
node_uuid = "sys:node-uuid"
title = "cclom:title"
www_url = "ccm:wwwurl"
description = "cclom:general_description"
publisher = "ccm:oeh_publisher_combined"
license = "ccm:commonlicense_key"
license_oer = "ccm:license_oer"
subjects = "ccm:taxonid_DISPLAYNAME"
subjects_entry = "ccm:taxonentry_DISPLAYNAME"
educational_context = "ccm:educationalcontext_DISPLAYNAME"
lrt = "ccm:oeh_lrt_aggregated_DISPLAYNAME"
language = "cclom:general_language_DISPLAYNAME"
language_fallback = "cclom:general_language"
keywords = "cclom:general_keyword"
author = "ccm:author_freetext"
target_group = "ccm:educationalintendedenduserrole_DISPLAYNAME"
language_level = "ccm:oeh_languageLevel_DISPLAYNAME"
language_target = "ccm:oeh_languageTarget"
curriculum = "ccm:curriculum_DISPLAYNAME"
fsk = "ccm:fskRating_DISPLAYNAME"
age_from = "ccm:educationaltypicalagerange_from"
age_to = "ccm:educationaltypicalagerange_to"
replication_source = "ccm:replicationsource"
general_identifier = "ccm:general_identifier"
editorial_status = "ccm:editorial_checklist_DISPLAYNAME"
wf_status = "ccm:wf_status"

# Reihenfolge = Anzeige-Reihenfolge (18 Einträge aus truth_loaders.QUALITY_FIELDS)
qualitaet = [
  ["Sachrichtigkeit", "ccm:oeh_quality_correctness_DISPLAYNAME"],
  ["Aktualität", "ccm:oeh_quality_currentness_DISPLAYNAME"],
  ["Neutralität", "ccm:oeh_quality_neutralness_DISPLAYNAME"],
  ["Sprachl. Angemessenheit", "ccm:oeh_quality_language_DISPLAYNAME"],
  ["Medial passend", "ccm:oeh_quality_medial_DISPLAYNAME"],
  ["Didaktik/Methodik", "ccm:oeh_quality_didactics_DISPLAYNAME"],
  ["Transparenz", "ccm:oeh_quality_transparentness_DISPLAYNAME"],
  ["Für Bildung geeignet", "ccm:oeh_quality_relevancy_for_education_DISPLAYNAME"],
  ["Jugendschutz", "ccm:oeh_quality_protection_of_minors_DISPLAYNAME"],
  ["Datenschutz (rechtl.)", "ccm:oeh_quality_data_privacy_DISPLAYNAME"],
  ["Persönlichkeitsrechte", "ccm:oeh_quality_personal_law_DISPLAYNAME"],
  ["Strafrecht", "ccm:oeh_quality_criminal_law_DISPLAYNAME"],
  ["Urheberrecht", "ccm:oeh_quality_copyright_law_DISPLAYNAME"],
  ["Login", "ccm:conditionsOfAccess_DISPLAYNAME"],
  ["Kosten", "ccm:price_DISPLAYNAME"],
  ["Werbung", "ccm:containsAdvertisement_DISPLAYNAME"],
  ["DSGVO", "ccm:dataProtectionConformity_DISPLAYNAME"],
  ["Barrierefreiheit", "ccm:accessibilitySummary_DISPLAYNAME"],
]

[spider]
kennung_enthaelt = "spider"              # general_identifier gilt als Spider, wenn er das enthält
ignorieren = ["wirlernenonline_spider"]  # truth_text.IGNORE_SPIDERS
migration = ["wirlernenonline_spider", "wirlernenonline_gsheet_spider"]  # config.WLO_SPIDERS
migration_quelle = "wirlernenonline_spider"  # replicationsource → Flag WLO_MIGRATION
platzhalter_bezugsquellen = ["wirlernenonline"]  # normalisiert (truth_text.PLACEHOLDER_BQ)
lrt_quelle_stichwort = "quelle"
publiziert_wf_status = ["150_PUBLISH_IN_SEARCH", "155_ELEMENT_UNLOCK_BUFFET"]

[crawler_tabelle]
spider_spalte = "Crawler (Spider)"
quelldatensatz_spalte = "Quelldatensatz (Prod)"

[crawler_tabelle.spalten]   # CSV-Spalte → Schlüssel (Schlüssel müssen in field_policy stehen)
"Titel" = "titel"
"Url" = "url"
"Bezugsquelle" = "bezugsquelle"
"Urheber" = "urheber"
"robots.txt" = "robotsTxt"
"TDM Hinweis ( §44b)" = "tdmHinweis"
"AGB / Nutzungsbedingungen" = "agb"
"Lizenz Check" = "lizenzCheck"
"API Nutzungsbedingungen" = "apiNutzung"
"Crawler (Spider)" = "spider"
"Prio" = "prio"
"Crawler-Type" = "crawlerType"
"Zustand" = "zustand"
"Spider Bemerkungen" = "spiderBemerkungen"
"Einschätzung KI & Erschließung" = "kiEinschaetzung"
"Bemerkung/Status" = "bemerkungStatus"
"Prod letzter Crawl" = "prodLetzterCrawl"
"Staging letzter Crawl" = "stagingLetzterCrawl"
"Häufigkeit" = "haeufigkeit"
"Anzahl Prod" = "anzahlProd"
"Anzahl Staging" = "anzahlStaging"
"Quelldatensatz (Prod)" = "quelldatensatzProd"
"Hinweis zu Quellendatensatz" = "hinweisQuelldatensatz"
"Export to OER Berlin" = "exportOerBerlin"
"GitHub" = "github"
"Vereinb. neu" = "Vertrag/Vereinbarung"
"Vereinb. alt" = "Vereinbarung (alt)"

[branding]
primary = "#003b7c"
accent = "#e4f700"
logo = "wlo-logo.svg"
```

- [ ] **Step 2: Failing Tests schreiben** (`tests/test_profile.py`):

```python
def test_wlo_profile_values():
    p = profile.load_profile("wlo", PROFILES)
    assert p.repo_url == "https://redaktion.openeduhub.net"
    assert p.felder["publisher"] == "ccm:oeh_publisher_combined"
    assert len(p.qualitaet) == 18 and p.qualitaet[0] == ("Sachrichtigkeit", "ccm:oeh_quality_correctness_DISPLAYNAME")
    assert p.ignore_spiders == frozenset({"wirlernenonline_spider"})
    assert p.publiziert_wf == ("150_PUBLISH_IN_SEARCH", "155_ELEMENT_UNLOCK_BUFFET")
    assert p.daten_dir == PROFILES / "wlo" / "daten"

def test_unknown_profile_names_path(tmp_path):
    with pytest.raises(profile.ProfileError, match=str(tmp_path / "gibtsnicht")):
        profile.load_profile("gibtsnicht", tmp_path)

def test_missing_required_feld_is_named(tmp_path):
    # Kopie des WLO-Profils ohne felder.publisher
    ...
    with pytest.raises(profile.ProfileError, match="publisher"):
        profile.load_profile("kaputt", tmp_path)

def test_get_reads_env(monkeypatch):
    monkeypatch.setenv("QE_PROFILE", "wlo"); profile.reset()
    assert profile.get().id == "wlo"

def test_crawler_keys_are_in_field_policy():
    p = profile.load_profile("wlo", PROFILES)
    known = set(fp.CRAWLER_PUBLIC_KEYS) | set(fp.CRAWLER_INTERNAL_KEYS)
    assert set(p.crawler_spalten.values()) <= known
```

- [ ] **Step 3: Run.** `python -m pytest tests/test_profile.py -v`. Expected: FAIL (`No module named 'profile'`, bzw. weil `CRAWLER_PUBLIC_KEYS` fehlt).

- [ ] **Step 4: Implementieren.** `profile.py` wie in den Interfaces beschrieben. Der Loader prüft `REQUIRED_FELDER` und die Pflichtschlüssel in `[repository]`, `[spider]` und `[crawler_tabelle]`; was fehlt, steht in der `ProfileError`-Meldung, ebenso der Dateipfad. In `field_policy.py` kommen `CRAWLER_PUBLIC_KEYS = frozenset(CRAWLER_PUBLIC_BASE.values())` und `CRAWLER_INTERNAL_KEYS = frozenset(CRAWLER_INTERNAL_BASE.values())` dazu. Die bestehenden Dicts bleiben vorerst, bis Task 5 sie ablöst.

- [ ] **Step 5: Run.** `python -m pytest tests/test_profile.py -v`, Expected: 5 passed. Dann `python -m pytest -q`, Expected: alles grün.

- [ ] **Step 6: Commit.** `git add profiles/wlo/profil.toml backend/profile.py backend/field_policy.py backend/tests/test_profile.py && git commit -m "feat: Profil-Lader und WLO-Profil"`

---

### Task 3: Korrekturen-Modul (Langformat)

**Files:**
- Create: `backend/korrekturen.py`
- Test: `backend/tests/test_korrekturen.py`

**Interfaces:**
- Produces:
  - `HEADER = ("Typ", "Schlüssel", "Aktion", "Wert", "Kommentar", "Geändert von", "Geändert am")`, `TYPEN`, `AKTIONEN` (Werte aus den Global Constraints)
  - `@dataclass(frozen=True) class Korrektur`: `typ, schluessel, aktion, wert, kommentar, geaendert_von, geaendert_am: str`
  - `@dataclass(frozen=True) class Meldung`: `zeile: int, text: str`
  - `@dataclass class KorrekturSet`: `eintraege: list[Korrektur]`, `fehler: list[Meldung]`, `warnungen: list[Meldung]`, dazu
    - `als_node_dict() -> dict[str, dict[str, str]]`: genau die Form des alten `truth_loaders.load_korrektur()`, also `{nodeId: {"liste": str, "bezugsquelle": str, "spider": str}}`. `blacklist`/`whitelist` setzen `liste`, `vermerk` legt den Eintrag mit `liste=""` an, `bezugsquelle_setzen` und `spider_setzen` setzen das jeweilige Feld. Die letzte `liste`-Zeile je Node gewinnt.
    - `supplements() -> dict[str, dict[str, str]]`: `{schluessel.lower(): {"description": …, "previewUrl": …}}` aus den Zeilen `Typ=bezugsquelle` mit `beschreibung`/`vorschaubild`. Nur Schlüssel, deren Wert gesetzt ist.
  - `load_korrekturen(path: Path | None) -> KorrekturSet`: `None` oder fehlende Datei ergibt ein leeres Set
  - `write_korrekturen(path: Path, eintraege: Iterable[Korrektur]) -> None`: atomar (temp + `os.replace`), UTF-8 mit BOM, `;`, Zeilenende `\r\n`

- [ ] **Step 1: Failing Tests schreiben:**

```python
def test_roundtrip(tmp_path):
    rows = [K("node", NID, "blacklist", "", "Titel X", "jan", "2026-11-26"),
            K("bezugsquelle", "YouTube", "beschreibung", "Videos; mit Semikolon", "", "", "")]
    write_korrekturen(tmp_path / "k.csv", rows)
    raw = (tmp_path / "k.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and b"Typ;Schl\xc3\xbcssel;Aktion" in raw
    assert load_korrekturen(tmp_path / "k.csv").eintraege == rows

def test_excel_variants(tmp_path):            # Review Focus 1
    # BOM + CRLF + zwei leere Spalten am Ende + Komma-Trenner als zweite Datei
    ...
    assert [e.aktion for e in s.eintraege] == ["whitelist"]

def test_invalid_rows_are_reported(tmp_path):  # Review Focus 2
    # Zeile 2: Aktion "löschen"; Zeile 3: Typ node, Schlüssel "abc"; Zeile 4: leerer Schlüssel
    s = load_korrekturen(p)
    assert s.eintraege == [] and [m.zeile for m in s.fehler] == [2, 3, 4]

def test_contradiction_last_wins_with_warning(tmp_path):  # Review Focus 3
    s = load_korrekturen(p)   # NID whitelist, dann NID blacklist
    assert s.als_node_dict()[NID]["liste"] == "blacklist"
    assert len(s.warnungen) == 1 and NID in s.warnungen[0].text

def test_vermerk_creates_empty_list_entry(tmp_path):
    assert s.als_node_dict()[NID] == {"liste": "", "bezugsquelle": "", "spider": ""}

def test_supplements_lowercase_keys(tmp_path):
    assert s.supplements() == {"youtube": {"description": "Videos", "previewUrl": "https://x/p.png"}}

def test_missing_file_is_empty(tmp_path):
    s = load_korrekturen(tmp_path / "fehlt.csv")
    assert s.eintraege == [] and s.fehler == []
```

- [ ] **Step 2: Run.** `python -m pytest tests/test_korrekturen.py -v`. Expected: FAIL (`No module named 'korrekturen'`).

- [ ] **Step 3: Implementieren.** Das Trennzeichen wird wie im alten Loader erkannt (mehr `;` als `,` in der Kopfzeile ergibt `;`). Die Spaltennamen werden mit `truth_text._norm` verglichen, Groß- und Kleinschreibung sowie Umlaute spielen also keine Rolle. `Typ=node` verlangt eine UUID nach `truth_text._UUID_RE` (vollständig). Zeilennummern sind 1-basiert inklusive Kopfzeile, wie Excel sie zeigt.

- [ ] **Step 4: Run.** `python -m pytest tests/test_korrekturen.py -v`, Expected: 7 passed.

- [ ] **Step 5: Commit.** `git commit -m "feat: Korrekturen im Langformat (Semikolon-CSV) lesen und schreiben"`

---

### Task 4: Migration der WLO-Korrekturen und Umzug der Crawler-Tabelle

**Files:**
- Create: `backend/tools/__init__.py`, `backend/tools/migrate_korrekturen.py`
- Create (erzeugt): `profiles/wlo/daten/korrekturen.csv`, `profiles/wlo/daten/migration-bericht.md`
- Move: `backend/data/inputs/datencrawler.csv` → `profiles/wlo/daten/crawler.csv` (mit `git mv`)
- Create (erzeugt): `backend/tests/fixtures/golden/neu/korrekturen.csv`, `neu/crawler.csv` (Kopie von `alt/datencrawler.csv`)
- Test: `backend/tests/test_migration.py`

**Interfaces:**
- Consumes: `korrekturen.Korrektur`, `write_korrekturen`, `load_korrekturen`
- Produces: `migrate(korrektur_csv: Path, supplements_json: Path, heute: str) -> tuple[list[Korrektur], list[str]]` (Einträge und Berichtszeilen); CLI `python -m tools.migrate_korrekturen <korrektur.csv> <supplements.json> <ziel.csv> [--bericht <md>]`

Regeln je alter Zeile (Reihenfolge der Datei bleibt erhalten):
- `Liste` = `blacklist`/`whitelist` → `node;<id>;<liste>`
- `Liste` leer → `node;<id>;vermerk` (erhält das heutige Verhalten: intern „Korrekturliste —“)
- `Bezugsquelle` gesetzt → zusätzlich `node;<id>;bezugsquelle_setzen;<wert>`; `Spider` gesetzt und ∉ {`blacklist`,`whitelist`} → zusätzlich `node;<id>;spider_setzen;<wert>`
- `Liste` leer und `Spider` ∈ {`blacklist`,`whitelist`} → **verrutschte Zeile**: nur `vermerk`, Kommentar `Verdacht: Spalten verschoben, gemeint wohl <wert>`, und eine Berichtszeile
- `Kommentar` = `Titel` (Mojibake reparieren: `s.encode("latin-1").decode("utf-8")`, wenn das ohne Fehler geht), dahinter ` | ` und `Url`, wenn gesetzt; `Geändert von` = `migration`; `Geändert am` = `heute`
- Supplements: je Schlüssel (ohne `_provenance`) `bezugsquelle;<schlüssel>;beschreibung;<description>` und `…;vorschaubild;<previewUrl>`, soweit gesetzt

- [ ] **Step 1: Failing Tests schreiben:**

```python
def test_migration_equals_old_loader(monkeypatch):
    rows, _ = migrate(FIX / "alt/quellen_korrektur.csv", FIX / "alt/source_supplements.json", "2026-11-26")
    s = KorrekturSet(eintraege=rows, fehler=[], warnungen=[])
    monkeypatch.setattr(truth_loaders, "KORREKTUR", FIX / "alt/quellen_korrektur.csv")
    assert s.als_node_dict() == truth_loaders.load_korrektur()
    sup = json.loads((FIX / "alt/source_supplements.json").read_text(encoding="utf-8"))
    sup.pop("_provenance", None)
    assert s.supplements() == {k: {kk: vv for kk, vv in v.items() if vv} for k, v in sup.items()}

def test_shifted_row_is_reported():
    rows, bericht = migrate(...)
    assert any("verschoben" in r.kommentar for r in rows) and any("verschoben" in b for b in bericht)

def test_real_wlo_files_migrate_without_errors(tmp_path):
    # echte Dateien aus dem Repo-Stand vor dem Umzug (Pfade aus git, siehe Step 3)
    rows, bericht = migrate(...)
    write_korrekturen(tmp_path / "k.csv", rows)
    s = load_korrekturen(tmp_path / "k.csv")
    assert s.fehler == []
```

Der dritte Test liest die echte Korrekturliste und die Supplements aus `profiles/wlo/daten/korrekturen.csv`, sobald diese erzeugt ist. Er prüft dann `load_korrekturen(...).fehler == []` und dass `als_node_dict()` genau 440 Node-IDs enthält. Das ist die Zahl der eindeutigen Node-IDs in der heutigen `quellen_korrektur.csv`, nachgezählt am 26.11.2026.

- [ ] **Step 2: Run.** Expected: FAIL (`No module named 'tools'`).

- [ ] **Step 3: Implementieren und echte Daten migrieren.**
  Run: `cd backend && python -m tools.migrate_korrekturen data/inputs/quellen_korrektur.csv data/source_supplements.json ../profiles/wlo/daten/korrekturen.csv --bericht ../profiles/wlo/daten/migration-bericht.md`
  Expected: Datei mit 444 + n Zeilen; der Bericht listet die verrutschten Zeilen (heute 80) und die doppelten Node-IDs (heute 4).
  Dann `python -m tools.migrate_korrekturen tests/fixtures/golden/alt/quellen_korrektur.csv tests/fixtures/golden/alt/source_supplements.json tests/fixtures/golden/neu/korrekturen.csv` und `cp tests/fixtures/golden/alt/datencrawler.csv tests/fixtures/golden/neu/crawler.csv`.
  Dann `git mv backend/data/inputs/datencrawler.csv profiles/wlo/daten/crawler.csv`. `quellen_korrektur.csv` und `source_supplements.json` bleiben bis Task 5 liegen, weil die alten Loader sie noch lesen.

- [ ] **Step 4: Run.** `python -m pytest tests/test_migration.py -v`, Expected: 3 passed. `python -m pytest -q`: alles grün. Der Golden-Test liest noch `alt/`.

- [ ] **Step 5: Commit.** `git commit -m "feat: WLO-Korrekturen ins Langformat migriert, Crawler-Tabelle ins Profil"`

---

### Task 5: Merge-Kern auf Profil und Korrekturen umstellen

**Files:**
- Modify: `backend/config.py` (Pfade und URLs), `backend/truth_text.py`, `backend/truth_loaders.py`, `backend/truth_record.py`, `backend/truth.py`, `backend/field_policy.py`
- Modify: `backend/tests/test_golden.py` (nur `build_golden`)
- Delete: `backend/data/inputs/quellen_korrektur.csv`, `backend/data/inputs/` (leer)
- Test: `backend/tests/test_golden.py`, `backend/tests/test_store.py` (bestehend)

**Interfaces:**
- Consumes: `profile.get()`, `korrekturen.load_korrekturen`, `KorrekturSet.als_node_dict()`
- Produces in `config.py`:
  - `DATA_DIR: Path` = `Path(env QE_DATA_DIR)` oder `HERE / "data"`; `TRUTH = DATA_DIR / "truth.json"`; `RAW_DIR = DATA_DIR / "raw"`
  - `crawler_csv_path() -> Path | None`: `DATA_DIR / "crawler.csv"`, falls vorhanden, sonst `profile.get().daten_dir / "crawler.csv"`, falls vorhanden, sonst `None`
  - `korrekturen_csv_path() -> Path | None`: analog mit `korrekturen.csv`
  - `REPO_URL`, `SEARCH_URL`: aus der Env, sonst aus `profile.get()`
- Produces in `truth_loaders.py`: `load_korrektur() -> dict` bleibt mit derselben Signatur und Form erhalten (intern `load_korrekturen(config.korrekturen_csv_path()).als_node_dict()`); `RAW`, `DATENCRAWLER`, `KORREKTUR` und `ROOT` entfallen als Modulkonstanten. Alle Loader lesen bei jedem Aufruf `config.RAW_DIR` bzw. `config.crawler_csv_path()`, damit Tests per Env umschalten können. `load_spider_top_publisher` liest `config.RAW_DIR / "replication_publisher_gap.csv"`.
- Produces in `truth_text.py`: `IGNORE_SPIDERS` und `PLACEHOLDER_BQ` entfallen; Aufrufer nehmen `profile.get().ignore_spiders` bzw. `.platzhalter_bq`. `_age(props)` liest `felder["age_from"]`/`["age_to"]`.
- Produces in `field_policy.py`: `CRAWLER_PUBLIC_BASE`/`CRAWLER_INTERNAL_BASE` entfallen; es bleiben `CRAWLER_PUBLIC_KEYS` und `CRAWLER_INTERNAL_KEYS` (Schlüssel). `load_crawler_profiles` teilt die Spalten aus `profile.crawler_spalten` danach in öffentlich und intern auf.

- [ ] **Step 1: Golden-Helfer auf den neuen Mechanismus umstellen** (das ist der Failing Test). `build_golden(monkeypatch)` legt in `tmp_path` an: `raw/` (Kopie von `fixtures/golden/raw`), `crawler.csv` und `korrekturen.csv` (aus `fixtures/golden/neu/`). Dann setzt er `QE_DATA_DIR=tmp_path`, `QE_PROFILE=wlo`, ruft `profile.reset()`, lädt `config`, `truth_loaders` und `enduser` per `importlib.reload` neu und ruft `truth.build()` auf. Die erwarteten Dateien bleiben **unverändert**.

- [ ] **Step 2: Run.** `python -m pytest tests/test_golden.py -v`. Expected: FAIL, weil die Loader noch die alten Pfade lesen.

- [ ] **Step 3: Umstellen.** `_parse_node` liest jede Property über `f = profile.get().felder`, die Qualitätsfelder über `profile.get().qualitaet` und den Spider-Filter über `spider_kennung`. `truth_record._record_flags` vergleicht mit `migration_quelle` und `lrt_quelle_stichwort`, `make_record` mit `ignore_spiders`. `truth._mark_data_problems` liest `publiziert_wf` statt `_PUBLISHED_WF`, `truth.py` liest `platzhalter_bq`. `truth.main()` schreibt nach `config.TRUTH` und liest `cache_meta.json` aus `config.RAW_DIR`. Die Suche nach Pfaden außerhalb des Repos (`_find`, `Wissen/…`, `Quellen-Steckbriefe-2026/…`) entfällt ersatzlos. `store.py` liest `config.TRUTH`.

- [ ] **Step 4: Test für fehlende Dateien hinzufügen** (Review Focus 4):

```python
def test_build_without_crawler_and_korrekturen(monkeypatch, tmp_path):
    shutil.copytree(FIX / "raw", tmp_path / "raw")
    _use_data_dir(monkeypatch, tmp_path)          # ohne crawler.csv/korrekturen.csv
    monkeypatch.setenv("QE_PROFILES_DIR", str(tmp_path / "leer"))  # Profil-daten fehlen auch
    ...                                            # Kopie von profil.toml ohne daten/
    records = truth.build()
    assert records and not any(r["kind"] == "crawler" and r["fieldGeneration"] for r in records)
```

- [ ] **Step 5: Run.** `python -m pytest -q`. Expected: alles grün, auch `test_golden` (2) und die bestehenden `test_store`/`test_routes`. Für die Routen-Tests lädt `store` weiterhin die gebündelte `backend/data/truth.json`.

- [ ] **Step 6: Commit.** `git rm -r backend/data/inputs && git commit -m "refactor: Merge-Kern liest Felder, Sonderfälle und Korrekturen aus dem Profil"`

---

### Task 6: Live-Abruf und Beispielinhalte auf das Profil umstellen

**Files:**
- Modify: `backend/fetcher.py`, `backend/wlo_content.py`, `backend/app.py:221-243`
- Test: `backend/tests/test_fetcher_profile.py`

**Interfaces:**
- Consumes: `profile.get()`, `config.REPO_URL`, `config.RAW_DIR`
- Produces:
  - `fetcher.ngsearch_url() -> str` = `f"{config.REPO_URL}/edu-sharing/rest/search/v1/queries/-home-/{p.mds}/ngsearch"`
  - `fetcher.refresh_all` schreibt alle Caches nach `config.RAW_DIR`, auch `replication_publisher_gap.csv`. Das Kriterium „ist Quelle“ heißt `{"property": p.quelle_property, "values": list(p.quelle_werte)}`, die Facetten heißen `p.felder["publisher"]` und `p.felder["replication_source"]`, die Vokabular-URL ist `p.vocab_sources_url`.
  - `wlo_content.fetch_contents(prop, value, max_items, skip)` bleibt, URL aus `p.mds`; Fächer über `felder["subjects_entry"]`.
  - `app.source_contents` wählt `prop` aus `felder["replication_source"]` bzw. `felder["publisher"]`.

- [ ] **Step 1: Failing Tests schreiben:**

```python
def test_fetch_quellen_uses_profile_criterion(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(fetcher.requests, "post", _fake_post(sent, pages=[[NODE]]))
    fetcher._fetch_quellen(lambda d, t: None)
    assert sent[0]["url"].startswith("https://redaktion.openeduhub.net/edu-sharing/rest/search/v1/queries/-home-/mds_oeh/ngsearch")
    assert sent[0]["json"]["criteria"] == [{"property": "ccm:oeh_lrt_aggregated",
        "values": ["http://w3id.org/openeduhub/vocabs/new_lrt_aggregated/2e678af3-1026-4171-b88e-3b3a915d1673"]}]

def test_other_profile_changes_mds(monkeypatch):
    _use_profile(monkeypatch, "beispiel")   # benötigt Task 8 nicht: tmp-Profil mit mds="mds_test"
    assert "/-home-/mds_test/ngsearch" in fetcher.ngsearch_url()

def test_refresh_writes_into_raw_dir(monkeypatch, tmp_path):
    # alle HTTP-Aufrufe gefälscht; danach liegen die 8 Cache-Dateien in tmp_path/raw
    ...
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Umstellen**, wie in den Interfaces beschrieben. `fetcher.ROOT` und `DATADIR` entfallen.
- [ ] **Step 4: Run.** `python -m pytest -q`, Expected: alles grün.
- [ ] **Step 5: Commit.** `git commit -m "refactor: Live-Abruf und Beispielinhalte aus dem Profil konfiguriert"`

---

### Task 7: Filter, Statistik, Audit-Texte und Supplements auf das Profil umstellen

**Files:**
- Modify: `backend/filtering.py`, `backend/stats_team.py`, `backend/protokoll.py`, `backend/enduser.py`, `backend/config.py` (`WLO_SPIDERS` entfällt)
- Delete: `backend/data/source_supplements.json`
- Create: `backend/tests/test_neutral.py`

**Interfaces:**
- Consumes: `profile.get().migration_spiders`, `.migration_quelle`, `.felder["publisher"]`; `korrekturen.load_korrekturen(config.korrekturen_csv_path()).supplements()`
- Produces: `enduser.reload_supplements() -> None`. Liest die Supplements aus der Korrektur-CSV neu, Etappe 4 ruft das nach jeder Änderung auf. Beim Import wird es einmal aufgerufen.

- [ ] **Step 1: Failing Test schreiben** (`tests/test_neutral.py`):

```python
FORBIDDEN = ("ccm:oeh_", "wirlernenonline", "mds_oeh", "openeduhub")

def test_core_has_no_wlo_specifics():
    hits = [(p.name, s) for p in BACKEND.glob("*.py") for s in FORBIDDEN
            if s in p.read_text(encoding="utf-8")]
    assert hits == []
```

- [ ] **Step 2: Run.** Expected: FAIL. Die Trefferliste zeigt, was noch zu tun ist.
- [ ] **Step 3: Umstellen.** In `filtering.py` und `stats_team.py` wird `"wirlernenonline_spider"` zu `p.migration_quelle`, `WLO_SPIDERS` zu `p.migration_spiders`. In `protokoll.py` wird der Property-Name im Hinweistext per f-String aus `p.felder["publisher"]` gebildet, und „WirLernenOnline-Migrations-Platzhalter“ wird zu „Migrations-Platzhalter des Repositorys“. In `enduser.py` ersetzt `reload_supplements()` die JSON-Datei. Kommentare und Docstrings mit WLO-Bezug werden ebenfalls neutral formuliert.
- [ ] **Step 4: Run.** `python -m pytest -q`, Expected: alles grün, `test_neutral` eingeschlossen; `test_cards_match_golden` belegt, dass die Supplements weiter wirken.
- [ ] **Step 5: Commit.** `git commit -m "refactor: Filter, Statistik, Audit und Supplements ohne WLO-Konstanten"`

---

### Task 8: Zweites Profil als Neutralitätsbeweis

**Files:**
- Create: `profiles/beispiel/profil.toml`, `backend/tests/fixtures/beispiel/raw/…` (3 Nodes, 2 Facetten)
- Test: `backend/tests/test_beispiel_profil.py`

**Interfaces:**
- Consumes: alles aus Task 2 bis 7

`profiles/beispiel/profil.toml`: `id = "beispiel"`, `repository.url = "https://repo.example.org"`, `mds = "mds"`, `quelle_property = "ccm:objecttype"`, `quelle_werte = ["SOURCE"]`, dieselben `felder` wie WLO, aber `publisher = "ccm:publisher"` und `lrt = "ccm:educationallearningresourcetype_DISPLAYNAME"`, `language_level`/`language_target` auf nicht existierende Properties (`"ccm:none"`), `qualitaet = []`, `spider.ignorieren = []`, `migration = []`, `migration_quelle = ""`, `platzhalter_bezugsquellen = []`, Crawler-Spalten nur `Titel`, `Url`, `Crawler (Spider)`.

- [ ] **Step 1: Failing Test schreiben:**

```python
def test_build_with_foreign_profile(monkeypatch, tmp_path):
    _use(monkeypatch, profile="beispiel", data=FIX_BEISPIEL)
    records = truth.build()
    assert {r["kind"] for r in records} == {"manuell", "bezugsquelle"}
    assert all("WLO_MIGRATION" not in r["flags"] for r in records)
    assert records[0]["public"]["Bezugsquelle"]          # aus ccm:publisher
```

- [ ] **Step 2: Run.** Expected: FAIL (Profil fehlt).
- [ ] **Step 3: Profil und Fixture anlegen.** Wenn der Test mit einem `KeyError` oder `TypeError` scheitert, ist das ein Neutralitätsfehler im Kern: Dann wird der Kern repariert und nicht das Profil verbogen.
- [ ] **Step 4: Run.** `python -m pytest -q`, Expected: alles grün.
- [ ] **Step 5: Commit.** `git commit -m "test: Fremdprofil beweist Repository-Neutralität des Kerns"`

---

### Task 9: Image, Doku und Abschlussprüfung

**Files:**
- Modify: `Dockerfile` (zusätzlich `COPY profiles/ /app/quellenpanel/profiles/`; die Daten bleiben in dieser Etappe noch im Image, das Entfernen folgt in Etappe 3), `.dockerignore` (`profiles/*/daten/migration-bericht.md`), `.gitignore` (`backend/data/raw/`)
- Modify: `README.md` (Abschnitte „Architecture“, „Configuration“, „Repository neutrality“), `docs/datenaufbereitung.md` (Eingangstabelle, Overlay-Tabelle, Prozessbild: neue Pfade und das Langformat)
- Create: `profiles/README.md` (Aufbau eines Profils, Spalten und Aktionen der Korrektur-CSV mit Beispielen, Pflege in Excel)

- [ ] **Step 1: Dockerfile anpassen und lokal bauen.** Run: `docker build -t quellenpanel:etappe1 .` und danach `docker run --rm -e QE_TEAM_PASSWORD=x quellenpanel:etappe1 python -c "import profile,config; print(profile.get().id, config.crawler_csv_path())"`. Expected: `wlo /app/quellenpanel/profiles/wlo/daten/crawler.csv`. Steht in der Umgebung kein Docker zur Verfügung, stattdessen `cd backend && QE_DATA_DIR=$(mktemp -d) python -c "…"` ausführen und das im PR vermerken.
- [ ] **Step 2: Doku aktualisieren**, wie unter Files beschrieben. In `docs/datenaufbereitung.md` die Zeilen zu `quellen_korrektur.csv` und `source_supplements.json` durch `korrekturen.csv` (Langformat) ersetzen.
- [ ] **Step 3: Volle Prüfung.** Run: `cd backend && ruff check . && python -m pytest -q`. Expected: ruff ohne Befund, alle Tests grün (heute 44, danach mindestens 44 + die neuen). Frontend unverändert: `cd frontend && npm test` grün.
- [ ] **Step 4: Optionaler Vollvergleich mit echten Daten** (nur mit Netzzugang zum Repository, z. B. auf Jans Rechner): `git stash`/`checkout backup/vor-umbau-2026-11-26`, Live-Abruf und `truth.main()` laufen lassen, `truth.json` sichern; dann auf dem Etappen-Branch mit denselben Roh-Caches `QE_DATA_DIR=… python truth.py`; dann `python -c "import json,sys; a,b=(json.load(open(f)) for f in sys.argv[1:]); print(a['records']==b['records'])" alt.json neu.json`. Expected: `True`. Ergebnis im PR festhalten.
- [ ] **Step 5: Commit und Push.** `git commit -m "docs: Profil-Aufbau und neue Datenpfade dokumentiert"`, dann `git push`, PR-Beschreibung um Etappe 1 ergänzen.
