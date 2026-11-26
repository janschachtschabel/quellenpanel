# Datenaufbereitung — WLO Quellenpanel (kompakt)

Wie aus WLO-Live-Daten + kuratierten Dateien die eine „Datenwahrheit" (`truth.json`) wird und was
beim Ausliefern darübergelegt wird. Erzeuger: `fetcher.py` (Abruf) + `truth*.py` (Merge). Auslieferung:
`store/filtering/enduser/serialize`.

## Prozess

```
① LIVE-ABRUF  (fetcher.py, nächtlich/manuell)        ② KURATIERTE DATEIEN  (Datenverzeichnis, sonst Profil)
   edu-sharing REST + NGSearch-Facetten                 $QE_DATA_DIR/ → profiles/<id>/daten/
   → $QE_DATA_DIR/raw/*.json,*.csv  (Roh-Caches)         crawler.csv · korrekturen.csv (Langformat)
                     │                                                  │
                     └───────────────────────┬──────────────────────────┘
                                             ▼
              ③ MERGE / „Datenwahrheit"  (truth.py, offline)
                 Join-Präzedenz:  Spider → Bezugsquelle (publisher_combined) → Node-ID/Korrektur
                 A) Crawler-Records   B) Quelldatensätze   C) Bezugsquelle-only
                 + per-Feld-Provenienz  + Flags (Datenprobleme, Blacklist/Whitelist, Provenienz)
                                             ▼
              ④ SNAPSHOT  backend/data/truth.json   (im Docker-Image gebündelt = Basis)
                                             ▼
              ⑤ SERVE  (im RAM, pro Request)
                 Hide (Blacklist/Zweitdatensatz) → Filter → Overlay (korrekturen.csv: bezugsquelle) → Tier 0/1/2
                                             ▼
              ⑥ LIVE pro Request (NICHT im Snapshot):
                 /api/sources/{id}/contents (Beispiel-Inhalte)  ·  /api/thumb (Vorschau-Proxy)
```

## ① + ② Eingänge — was live, was aus Dateien

| Eingang | Datei / Endpoint | live / Datei | Rolle |
|---|---|---|---|
| Quelldatensätze (suchbar) | `raw/quellen_nodes.json` | **live** (NGSearch `LRT=Quelle`) | Kern-Metadaten je Quelldatensatz |
| Quelldatensätze (such-unsichtbar) | `raw/extra_nodes.json` | **live** (Node-API; ID aus CSV) | z. B. bpb — per Node-ID nachgeladen |
| Bezugsquelle-Facette | `raw/cache_facet_bezugsquellen.json` | **live** (Facette) | Bezugsquelle → Inhaltsanzahl |
| Spider-Facette | `raw/cache_facet_spider.json` | **live** (Facette) | Spider → Inhaltsanzahl |
| Dominanter Publisher je Spider | `raw/…/replication_publisher_gap.csv` | **live** (beim Abruf erzeugt) | echte Bezugsquelle des Crawler-Inhalts |
| Vorschaubilder je Bezugsquelle | `raw/bq_previews.json` | **live** (1 Beispiel-Item) | Fallback-Vorschau für node-lose BQ |
| Vokabular (Skohub sources) | `raw/vocab_sources.json` | **live** | Spider-/Legacy-Bindungsnamen |
| Prod-Total + Zeitstempel | `raw/cache_meta.json` | **live** | `wloProdContent`, `generatedAt` |
| **Crawler-Profile** | `crawler.csv` (Datenverzeichnis, sonst `profiles/<id>/daten/`) | **Datei** (kuratiert, vom Datenteam hochgeladen) | Spider, Rechts-/KI-Felder, interne Notizen, Feld-Erzeugung |
| **Korrekturen** | `korrekturen.csv` (Datenverzeichnis, sonst `profiles/<id>/daten/`) | **Datei** (kuratiert, Langformat) | eine Zeile je Korrektur: `node` → blacklist/whitelist/vermerk, Bezugsquelle-/Spider-Override; `bezugsquelle` → Beschreibung + Vorschau für node-lose Quellen (nur beim **Ausliefern**). Aufbau: [`profiles/README.md`](../profiles/README.md) |

> Roh-Caches (`$QE_DATA_DIR/raw/`, Standard `backend/data/raw/`) sind **nicht** im Repo — sie entstehen beim
> Live-Abruf. Im Image gebündelt sind nur `truth.json` (Basis-Snapshot) + `profiles/` (Profil + Startdaten).

## ③ Merge (truth.py) → drei Record-Arten

| Schritt | Anker | Bezugsquelle-Präzedenz | Inhaltsanzahl |
|---|---|---|---|
| **A) Crawler** | Spider (aus `crawler.csv`) | dominanter Publisher → CSV-Bezugsquelle → Node-Publisher → … | Spider-Facette |
| **B) Quelldatensatz** | Node ohne Crawler-Profil | eigener Publisher; pro Bezugsquelle **ein** repräsentierender Primär-Datensatz | Bezugsquelle-Facette (0 bei Zweit-Datensatz) |
| **C) Bezugsquelle-only** | Facette ohne Quelldatensatz | die Facette selbst | Facetten-Count |

- **Join-Präzedenz gesamt:** Spider (`general_identifier`/`replicationsource` ↔ CSV ↔ Vokabular) → `ccm:oeh_publisher_combined` → Node-ID/Korrektur.
- **Per-Feld-Provenienz:** jedes Feld trägt seine Herkunft (`WLO-API` · `datencrawler.csv` · `WLO-API (Facette)`; die Labels sind Teil des Datenformats und bleiben unverändert).
- **Confidence:** high (Node + Spider/BQ) · medium · low (nur Facette).

## Was am Ende drübergelegt wird (Flags + Overlay)

| Overlay | Quelle | Wirkung |
|---|---|---|
| **Blacklist / Whitelist** | `korrekturen.csv` Aktion `blacklist`/`whitelist` → Flag `BLACKLIST`/`WHITELIST` | Blacklist wird in der Standardansicht **ausgeblendet** (aussortierte Nicht-Quelle/Dublette) |
| **Zweit-Datensatz** | Merge B (mehrere Datensätze je Bezugsquelle) → `ZWEITDATENSATZ` | in der Standard-/Tag-Ansicht **ausgeblendet** (Inhalte zählen am Primär-Datensatz); im Quelldatensatz-View sichtbar |
| **Datenproblem-Marker** (Team) | `_mark_data_problems` | `METADATEN_DUENN, BQ_EINZELINHALT, BINDUNG_UNVOLLSTAENDIG, QD_OHNE_BEZUGSQUELLE, DUBLETTE_VERDACHT, OHNE_STATUS, STATUS_INKONSISTENT, NICHT_PUBLIZIERT, SPIDER_UNEINDEUTIG, BQ_OHNE_QD, BQ_SUBCHANNEL` |
| **Provenienz-Marker** (öffentlich) | `_record_flags` | `WLO_MIGRATION, LEGACY_BINDUNG, TYP_NICHT_QUELLE, FEHLTAGGING, OER, FACETS_ONLY` |
| **Supplement-Overlay** | `korrekturen.csv` Typ `bezugsquelle`, Aktion `beschreibung`/`vorschaubild` (Serve-Zeit) | füllt **nur leere** Beschreibung/Vorschau node-loser Quellen (YouTube, BR, OER Commons …) |
| **Tier-Schichtung** | `serialize.py` | Tier 0 öffentlich · Tier 1 + KI/Recht · Tier 2 + intern/Flags/Provenienz/Verwandte |

Die Hide-Regel ist zentral (`filtering.is_hidden_by_default`): **Blacklist immer**, **Zweit-Datensatz außer im Quelldatensatz-View**.

## ⑤/⑥ Live vs. Snapshot beim Betrieb

| Aspekt | Woher | Wann |
|---|---|---|
| Liste, Metadaten, Flags, Statistik, Audit-Protokoll | `truth.json` (RAM) | Snapshot; ändert sich nur bei Rebuild |
| Beispiel-Inhalte einer Quelle (`/api/sources/{id}/contents`) | WLO NGSearch | **live pro Request** |
| Vorschaubild-Proxy (`/api/thumb`) | Repo-Host | **live pro Request** (host-beschränkt) |
| Kompletter Rebuild (`fetcher` + `truth.main` → neues `truth.json`) | WLO-Abruf | nächtlich (`QE_AUTO_REFRESH_HOUR`) **oder** manuell im Audit-Level (ephemer im Container) |

*Beispiel-Meta eines Snapshots (ändert sich je Rebuild):* `records 4219 · crawler 55 / manuell 1279 / bezugsquelle 2885 · totalContents 304.800 · wloProdContent 318.650`.
