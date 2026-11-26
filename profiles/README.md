# Repository-Profile

Der Kern von Quellenpanel (Abruf, Merge, Auslieferung) kennt keine Eigenheiten eines bestimmten
edu-sharing-Repositorys. Alles Repository-Spezifische steht in einem **Profil**:

```
profiles/<id>/
  profil.toml          Properties, Vokabular, Sonderfälle, Spalten der Crawler-Tabelle, Branding
  daten/
    crawler.csv        Crawler-Tabelle (vom Datenteam gepflegt, unregelmäßig aktualisiert)
    korrekturen.csv    kuratierte Korrekturen (Langformat, siehe unten)
```

Welches Profil aktiv ist, steuert `QE_PROFILE` (Standard `wlo`); `QE_PROFILES_DIR` zeigt auf einen
anderen Profilordner. Die Dateien unter `daten/` sind **Startdaten**: Liegt eine gleichnamige Datei
im Datenverzeichnis (`QE_DATA_DIR`, z. B. ein Volume), gewinnt diese. So kann das Team Korrekturen
und eine neue Crawler-Tabelle ablegen, ohne das Image neu zu bauen.

Vorhandene Profile:

| Profil | Zweck |
|---|---|
| `wlo` | WirLernenOnline (Produktion, Metadatensatz `mds_oeh`) |
| `beispiel` | minimales Fremdprofil mit Standard-Properties; Vorlage und Test, dass der Kern neutral ist |

## profil.toml

Fehlt ein Pflichtschlüssel, bricht der Start mit einer Meldung ab, die Datei und fehlende Schlüssel
nennt.

| Abschnitt | Inhalt |
|---|---|
| `id`, `name` | Kennung und Anzeigename (erscheint z. B. im Audit-Protokoll) |
| `[repository]` | `url`, `search_url`, `mds`, `vocab_sources_url`; `quelle_property` + `quelle_werte` bestimmen, welche Datensätze als Quelldatensatz gelten |
| `[felder]` | logischer Feldname → edu-sharing-Property (26 Pflichtfelder, z. B. `publisher`, `lrt`, `wf_status`). Nicht vorhandene Felder auf eine nie belegte Property setzen (z. B. `ccm:none`) |
| `[qualitaet]` | `felder = [["Label", "property"], …]` — Qualitätskriterien für Tier 1; darf leer sein |
| `[spider]` | `kennung_enthaelt` (Teilstring, an dem ein Spider im `general_identifier` erkannt wird), `ignorieren`, `migration` + `migration_quelle` (Altbestand), `platzhalter_bezugsquellen`, `lrt_quelle_stichwort`, `publiziert_wf_status` |
| `[crawler_tabelle]` | `spider_spalte`, `quelldatensatz_spalte` und `.spalten` (Spaltenüberschrift → interner Schlüssel). Spalten der Form `<Item> - <Feld> – Status` werden zusätzlich als Feld-Erzeugung gelesen |
| `[branding]` | Farben u. Ä. für die Oberfläche (wird geladen; die Oberfläche nutzt es ab einer späteren Etappe) |

`QE_REPO_URL` und `QE_SEARCH_URL` überschreiben `url` und `search_url` des Profils.

## korrekturen.csv (Langformat)

Eine Zeile je Korrektur, Semikolon-getrennt:

```
Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am
```

| Typ | Schlüssel | Aktion | Wert | Wirkung |
|---|---|---|---|---|
| `node` | Node-ID (UUID) | `blacklist` | – | Quelldatensatz wird in der Standardansicht ausgeblendet (keine Quelle / Dublette) |
| `node` | Node-ID | `whitelist` | – | als echte Quelle bestätigt |
| `node` | Node-ID | `vermerk` | – | nur Notiz, ohne Wirkung auf die Daten |
| `node` | Node-ID | `bezugsquelle_setzen` | Bezugsquelle | Bezugsquelle des Datensatzes überschreiben |
| `node` | Node-ID | `spider_setzen` | Spider | Spider-Zuordnung überschreiben |
| `bezugsquelle` | Name der Bezugsquelle | `beschreibung` | Text | Beschreibung für node-lose Quellen (füllt nur leere Felder) |
| `bezugsquelle` | Name der Bezugsquelle | `vorschaubild` | Bild-URL | Vorschaubild für node-lose Quellen (füllt nur leere Felder) |

Beispiele:

```
Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am
node;4da2afa6-f7db-4c8a-91f0-56472fc05133;whitelist;;4teachers;team;2026-11-26
node;4da2afa6-f7db-4c8a-91f0-56472fc05133;bezugsquelle_setzen;4teachers;Publisher fehlte;team;2026-11-26
bezugsquelle;YouTube;vorschaubild;https://example.org/youtube.png;;team;2026-11-26
```

Regeln:

- `Typ` und `Aktion` sind unabhängig von Groß-/Kleinschreibung; der Bezugsquellen-Name wird ohne
  Beachtung der Groß-/Kleinschreibung zugeordnet.
- Listen-Aktionen und Overrides gibt es nur für `node`, `beschreibung`/`vorschaubild` nur für
  `bezugsquelle`.
- Stehen für denselben Node `blacklist` und `whitelist`, gilt die **spätere Zeile**; das wird als
  Warnung gemeldet.
- Ungültige Zeilen (unbekannter Typ/Aktion, fehlender Schlüssel, keine gültige Node-ID) werden
  übersprungen und mit Zeilennummer gemeldet (Kopfzeile = Zeile 1). Eine fehlerhafte Zeile legt die
  Auslieferung also nie lahm.
- `Kommentar`, `Geändert von` und `Geändert am` sind frei und dienen der Nachvollziehbarkeit.

### Pflege in Excel

Die Datei wird als UTF-8 **mit BOM**, Semikolon und CRLF geschrieben; Excel öffnet sie per
Doppelklick mit korrekten Umlauten in Spalten. Beim Speichern „CSV UTF-8 (durch Trennzeichen
getrennt)“ wählen. Gelesen wird tolerant: BOM optional, Komma als Trennzeichen wird erkannt, leere
Zusatzspalten am Zeilenende werden ignoriert.

### Herkunft

`korrekturen.csv` des WLO-Profils wurde einmalig aus der früheren Korrekturliste
(`quellen_korrektur.csv`) und dem Overlay (`source_supplements.json`) erzeugt:
`cd backend && python -m tools.migrate_korrekturen --help`. Der Migrationsbericht
(`daten/migration-bericht.md`, nicht im Image) listet Dubletten und verrutschte Zeilen.

## Neues Profil anlegen

1. `profiles/beispiel/` kopieren und in `profil.toml` `id`, `name` und `[repository]` anpassen.
2. Unter `[felder]` die Properties des eigenen Metadatensatzes eintragen.
3. Crawler-Tabelle und Korrekturen unter `daten/` ablegen (beide dürfen fehlen).
4. Mit `QE_PROFILE=<id>` starten.
