export interface SourceCard {
  id: string;
  name: string;
  contentCount: number;
  url: string;
  searchUrl: string;
  bezugsquelle: string;   // publisher (Bezugsquelle); empty for node-only sources
  description: string;
  subjects: string[];
  educationalContext: string[];
  contentTypes: string[];
  license: string;
  oer: boolean;
  language: string;
  previewUrl: string;
  erschliessungsstatus: string;
  quality: Record<string, string>;
  familyCount?: number;        // sibling sources under the same Bezugsquelle family (publisher + sub-channels)
  flags?: string[];            // tier 2 (team) list rows: data-problem flags
  bind?: SourceBinding;        // tier 2 (team) list rows: source-binding badges (node/Bezugsquelle/spider)
}

/** Presence of the three source bindings — drives the Audit-tile status badges. Empty string = absent. */
export interface SourceBinding {
  node: string;          // Quelldatensatz (node id)
  bezugsquelle: string;  // Bezugsquelle (publisher)
  spider: string;        // crawler spider
}

/** One row of the crawler field-generation table: whether/how the crawler fills a metadata field. */
export interface FieldGenItem {
  item?: string;    // LOM container (e.g. LomGeneralItem) — used to group rows
  field?: string;   // the metadata field
  how?: string;     // how it is produced (scraped, hard-coded, mapped …)
  status?: string;  // textual status when not active
  aktiv?: boolean;  // whether the crawler actually fills it
}

export interface SourceDetail extends SourceCard {
  keywords: string[];
  author: string;
  targetGroup: string[];
  curriculum: string[];
  ageRange: string;
  // tier 1 (Steckbrief / "Details") — present only at tier >= 1
  ki?: Record<string, string>;      // AI-usage / legal fields (robots.txt, TDM §44b, AGB, licence check)
  fieldGeneration?: FieldGenItem[];
  fieldActiveCount?: number;
  binding?: { node: string; spider: string };  // public Steckbrief identity (node id + spider)
  // tier 2 (team / "Audit") — present only at tier 2
  internal?: Record<string, string>;
  provenance?: Record<string, string>;  // per-field data source (WLO-API, …), keyed by flat field name + KI key
  // tier 1+ — other sources under the same Bezugsquelle family (publisher + sub-channels, e.g. YouTube)
  related?: RelatedSources;
}

/** Sources sharing a Bezugsquelle family (a publisher and its sub-channels). Display only. */
export interface RelatedSources {
  bezugsquelle: string;   // the family / parent publisher name
  count: number;          // total siblings (may exceed items.length, which is capped)
  items: Array<{ id: string; name: string; contentCount: number; hasNode: boolean }>;
}

export interface ContentItem {
  title: string;
  previewUrl: string;
  url: string;
  description: string;
  subjects: string[];
  keywords: string[];
}

export interface SourceContents {
  total: number;
  nodes: ContentItem[];
}

export interface SourcesPage {
  total: number;
  page: number;
  pageSize: number;
  pages: number;
  items: SourceCard[];
  hidden?: { blacklist: number; mehrfach: number; total: number };  // tier 2: default-hidden breakdown
}

export interface FilterOptions {
  kinds: string[];
  subjects: string[];
  levels: string[];
  licenses: string[];
  languages: string[];
  lrts: string[];
  erschliessung: string[];
}

export interface BarEntry {
  value: string;
  count: number;
}

/** One row of the flat list export (/api/export.json) — the columns the table PDF prints. */
export interface ExportRow {
  name: string;
  kind: string;            // crawler | manuell | bezugsquelle
  contentCount: number;
  Lizenz: string;
  OER: string;             // "ja" | ""
  Bildungsstufen: string;  // pipe-joined ("A | B")
  Faecher: string;         // pipe-joined
  erschliessung: string;
}

export interface Stats {
  total: number;
  totalContents: number;
  withQuelldatensatz: number;
  crawlerCount: number;
  oer: { count: number; percent: number };
  topByContent: BarEntry[];
  topSubjects: BarEntry[];
  topLevels: BarEntry[];
  licenseDistribution: BarEntry[];
  topLanguages: BarEntry[];   // shown in the base view next to the top-sources chart
}

/** Extended statistics overview (tier >= 1) — see backend stats.compute_stats_full. */
export interface FullStats {
  totals: {
    quellenGesamt: number; inhalteGesamt: number; quelldatensaetze: number;
    crawler: number; manuell: number; bezugsquellenOhneQuelle: number;
  };
  oer: { count: number; percent: number };
  quellenverwaltung: { gesamt: number; mitQuelldatensatz: number; mitBezugsquelle: number; ueberschneidung: number };
  contentCoverage: { bezugsquelle: number; crawler: number; quelldatensatz: number; gesamt: number };
  contentBracketsNode: BarEntry[];
  bqSizeBrackets: BarEntry[];
  /** Descriptive-metadata fill over the Quelldatensätze, split into two balanced charts. */
  beschreibendeFelder: {
    basis: number;
    inhalt: Array<{ feld: string; anzahl: number; prozent: number }>;
    einordnung: Array<{ feld: string; anzahl: number; prozent: number }>;
  };
  fieldGeneration: {
    crawlerWithProfile: number; totalActiveFields: number; avgFieldsPerCrawler: number;
    byMethod: BarEntry[];
  };
  crawlerByType: BarEntry[];
  licenseDistribution: BarEntry[];
  topSubjects: BarEntry[];
  topLevels: BarEntry[];
  topLanguages: BarEntry[];
  topByContent: Array<{ name: string; count: number; kind: string }>;
}

/** Duplicate-group summary (team) — see backend stats_team `dup`. */
export interface DupInfo {
  gruppen: number;
  ueberzaehlig: number;
  beispiele: Array<{ wert: string; anzahl: number }>;
}

/** Team data-problem / origin / spider / fill-level addendum (tier 2) — stats_team.compute_stats_team. */
export interface TeamStats {
  herkunft: {
    quelldatensaetzeGesamt: number; nurQuelldatensatz_ohneBezugsquelle: number;
    schnittmenge_QuelldatensatzUndBezugsquelle: number; nurBezugsquelle_ohneQuelldatensatz: number;
    schnittmenge_sauber: number; schnittmenge_zweitDatensatz: number; schnittmenge_blacklist: number;
  };
  spiderBindung: {
    mitGeneralIdentifier: number; mitReplicationsource: number; beide: number;
    nurReplicationsource: number; nurRs_wloMigration: number; nurRs_echterSpider: number;
    nurRs_legacyName: number; echteBindungGesamt: number;
  };
  probleme: Record<string, number> & { doppelteUrl: DupInfo; doppelteTitel: DupInfo };
  feldFuellstand: {
    kiBasis: number;
    ki: Array<{ feld: string; anzahl: number; prozent: number }>;
  };
  /** Example sources per data-problem flag (keyed by flag) — drill-down detail. */
  problemBeispiele: Record<string, Array<{ name: string; inhalte: number }>>;
  /** Distribution: how many sources carry 0 / 1 / 2 / 3+ data defects at once. */
  problemeProQuelle: BarEntry[];
}

/** What the backend allows this client — drives the header tier controls (see /api/capabilities). */
export interface Capabilities {
  maxTier: number;       // highest tier reachable (0 end user, 1 Steckbrief, 2 team)
  publicOnly: boolean;   // QE_PUBLIC_ONLY — everything hard-capped at tier 0
  tier1Gated: boolean;   // tier 1 requires a password
  teamAvailable: boolean;// a team password is configured (tier 2 reachable via login)
  repoUrl: string;       // edu-sharing repo the data refers to (repo-neutral; shown in detail + PDF)
}
