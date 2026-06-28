/**
 * Data-problem / origin filter options for tier 2 (team), mirroring the old Quellensteckbriefe
 * team filter. Each option maps to exactly one backend `flag` (see field_policy / the tier-2
 * `GET /api/sources?flag=`). Labels are co-located here in DE/EN — they are domain terms, kept out
 * of the global i18n dictionary to avoid bloating it.
 */
export interface PruefOption { flag: string; de: string; en: string; }
export interface PruefGroup { de: string; en: string; options: PruefOption[]; }

export const PRUEF_GROUPS: PruefGroup[] = [
  {
    de: 'Datenprobleme', en: 'Data problems',
    options: [
      { flag: 'ZWEITDATENSATZ', de: 'Zweit-Datensätze (Dubletten · sonst ausgeblendet)', en: 'Secondary datasets (duplicates · otherwise hidden)' },
      { flag: 'BLACKLIST', de: 'aussortiert · keine echte Quelle (sonst ausgeblendet)', en: 'sorted out · not a real source (otherwise hidden)' },
      { flag: 'BQ_EINZELINHALT', de: 'Bezugsquelle mit nur 1 Inhalt', en: 'Bezugsquelle with a single content item' },
      { flag: 'DUBLETTE_VERDACHT', de: 'Dubletten-Verdacht (gleiche URL/Titel)', en: 'suspected duplicate (same URL/title)' },
      { flag: 'FEHLTAGGING', de: 'Misch-Typen (Quelle + weitere Inhaltstypen)', en: 'mixed content types (source + others)' },
      { flag: 'METADATEN_DUENN', de: 'dünne Metadaten (Kernfelder fehlen)', en: 'thin metadata (core fields missing)' },
      { flag: 'QD_OHNE_BEZUGSQUELLE', de: 'Quelldatensatz ohne Bezugsquelle', en: 'source dataset without a Bezugsquelle' },
      { flag: 'BINDUNG_UNVOLLSTAENDIG', de: 'unvollständige Bindung (Crawler ohne Datensatz)', en: 'incomplete binding (crawler without a dataset)' },
      { flag: 'BQ_OHNE_QD', de: 'Bezugsquelle mit Inhalten, aber ohne Quelldatensatz', en: 'Bezugsquelle with content but no source dataset' },
      { flag: 'BQ_SUBCHANNEL', de: 'Bezugsquelle evtl. Sub-Channel einer Hauptquelle', en: 'Bezugsquelle may be a sub-channel of a parent' },
      { flag: 'TYP_NICHT_QUELLE', de: 'echte Quelle, aber Typ ≠ „Quelle"', en: 'real source, but type ≠ "source"' },
    ],
  },
  {
    de: 'Status / Sichtbarkeit', en: 'Status / visibility',
    options: [
      { flag: 'OHNE_STATUS', de: 'Quelldatensatz ohne Erschließungsstatus', en: 'source dataset without editorial status' },
      { flag: 'STATUS_INKONSISTENT', de: 'voll gefüllt, aber Status < 9', en: 'fully filled, but status < 9' },
      { flag: 'NICHT_PUBLIZIERT', de: 'nicht in der Suche veröffentlicht', en: 'not published in search' },
    ],
  },
  {
    de: 'Herkunft / Bindung', en: 'Origin / binding',
    options: [
      { flag: 'WLO_MIGRATION', de: 'aus Datenübernahme (Migration)', en: 'from data migration' },
      { flag: 'LEGACY_BINDUNG', de: 'über alte Verschlagwortung gebunden', en: 'bound via legacy tagging' },
      { flag: 'SPIDER_UNEINDEUTIG', de: 'Spider-Bindung uneindeutig', en: 'ambiguous spider binding' },
    ],
  },
];
