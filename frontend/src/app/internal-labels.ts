/**
 * Editorial labels + ordering for the team-internal fields, ported from the Quellensteckbriefe app
 * (detail.js INT_LABELS / INT_FACTS / INT_REMARKS). Turns the raw `internal` dict into a tidy,
 * ordered "facts" list (rendered as a key/value grid) plus a separate "Bemerkungen" block for the
 * long free-text notes — so the Audit detail reads like the Steckbriefe profile instead of raw keys.
 */

// Factual fields first, in a deliberate reading order (status → binding → crawl → agreements).
const INT_FACTS = [
  'Erschliessungsstatus (genau)', 'Workflow-Status', 'Korrekturliste', 'Node-ID',
  'quelldatensatzProd', 'replicationsource', 'general_identifier', 'spider', 'crawlerType',
  'zustand', 'prio', 'haeufigkeit', 'prodLetzterCrawl', 'stagingLetzterCrawl', 'anzahlProd',
  'anzahlStaging', 'exportOerBerlin', 'github', 'Vertrag/Vereinbarung', 'Vereinbarung (alt)',
  'zuletzt geaendert',
];

// Long free-text notes shown last under a "Bemerkungen" sub-heading.
const INT_REMARKS = ['spiderBemerkungen', 'kiEinschaetzung', 'bemerkungStatus', 'hinweisQuelldatensatz'];

const INT_LABELS: Record<string, string> = {
  'Erschliessungsstatus (genau)': 'Erschließungsstatus',
  'Workflow-Status': 'Redaktions-/Workflow-Status',
  'Korrekturliste': 'Korrekturliste',
  'Node-ID': 'Quelldatensatz (Node-ID)',
  'quelldatensatzProd': 'Quelldatensatz-Link (Prod)',
  'replicationsource': 'replicationsource',
  'general_identifier': 'general_identifier',
  'spider': 'Spider',
  'crawlerType': 'Crawler-Typ',
  'zustand': 'Betriebszustand',
  'prio': 'Priorität',
  'haeufigkeit': 'Crawl-Häufigkeit',
  'prodLetzterCrawl': 'Letzter Crawl (Prod)',
  'stagingLetzterCrawl': 'Letzter Crawl (Staging)',
  'anzahlProd': 'Anzahl Prod (Stand letzter Crawl)',
  'anzahlStaging': 'Anzahl Staging (Stand letzter Crawl)',
  'exportOerBerlin': 'Export OER Berlin',
  'github': 'GitHub',
  'Vertrag/Vereinbarung': 'Vertrag/Vereinbarung',
  'Vereinbarung (alt)': 'Vereinbarung (alt)',
  'zuletzt geaendert': 'zuletzt geändert',
  'spiderBemerkungen': 'Spider-Bemerkungen',
  'kiEinschaetzung': 'KI-/Erschließungs-Einschätzung',
  'bemerkungStatus': 'Bemerkung/Status',
  'hinweisQuelldatensatz': 'Hinweis zum Quelldatensatz',
};

export interface InternalKV {
  label: string;
  value: string;
}

export interface InternalGroups {
  facts: InternalKV[];
  remarks: InternalKV[];
}

/** Split an internal field dict into ordered, German-labelled facts + remarks (skips empty values). */
export function groupInternal(internal: Record<string, string> | undefined): InternalGroups {
  const o = internal ?? {};
  const present = Object.keys(o).filter((k) => o[k] !== '' && o[k] != null);
  const lbl = (k: string): string => INT_LABELS[k] ?? k;
  const kv = (k: string): InternalKV => ({ label: lbl(k), value: String(o[k]) });

  const facts = INT_FACTS.filter((k) => present.includes(k)).map(kv);
  const other = present.filter((k) => !INT_FACTS.includes(k) && !INT_REMARKS.includes(k)).map(kv);
  const remarks = INT_REMARKS.filter((k) => present.includes(k)).map(kv);
  return { facts: [...facts, ...other], remarks };
}
