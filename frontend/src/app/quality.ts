/**
 * Quality characteristics of a source (cost, ads, login, data protection, legal cleanliness,
 * editorial quality). The backend delivers a clean labelled dict (e.g. {"Kosten": "nein"});
 * this module maps each key to an icon and each value to a good/neutral/bad/unknown level, and
 * defines which keys appear compactly (tiles/list) vs. grouped (detail).
 */
export type QLevel = 'good' | 'neutral' | 'bad' | 'unknown';

export interface QualityEntry {
  key: string;
  labelKey: string;
  icon: string;
  value: string;
  level: QLevel;
}

const META: Record<string, { icon: string; labelKey: string }> = {
  'Kosten':                  { icon: 'euro_symbol',       labelKey: 'q.kosten' },
  'Werbung':                 { icon: 'campaign',          labelKey: 'q.werbung' },
  'Login':                   { icon: 'login',             labelKey: 'q.login' },
  'DSGVO':                   { icon: 'verified_user',     labelKey: 'q.dsgvo' },
  'Barrierefreiheit':        { icon: 'accessibility_new', labelKey: 'q.barrier' },
  'Jugendschutz':            { icon: 'child_care',        labelKey: 'q.jugend' },
  'Persönlichkeitsrechte':   { icon: 'person',            labelKey: 'q.person' },
  'Strafrecht':              { icon: 'gavel',             labelKey: 'q.straf' },
  'Urheberrecht':            { icon: 'copyright',         labelKey: 'q.urheber' },
  'Datenschutz (rechtl.)':   { icon: 'policy',            labelKey: 'q.dsRecht' },
  'Für Bildung geeignet':    { icon: 'school',            labelKey: 'q.bildung' },
  'Aktualität':              { icon: 'update',            labelKey: 'q.aktuell' },
  'Sachrichtigkeit':         { icon: 'fact_check',        labelKey: 'q.sach' },
  'Neutralität':             { icon: 'balance',           labelKey: 'q.neutral' },
  'Transparenz':             { icon: 'visibility',        labelKey: 'q.transparenz' },
  'Didaktik/Methodik':       { icon: 'menu_book',         labelKey: 'q.didaktik' },
  'Medial passend':          { icon: 'perm_media',        labelKey: 'q.medial' },
  'Sprachl. Angemessenheit': { icon: 'translate',         labelKey: 'q.sprache' },
};

/** Map a labelled quality value to a traffic-light level. */
export function qualityLevel(value: string): QLevel {
  const v = (value || '').trim().toLowerCase();
  if (!v || v === 'null' || v.includes('nicht geprüft') || v.includes('nicht dsgvo')) return 'unknown';
  if (v.startsWith('nein')) return 'good';                       // "Nein - unauffällig" (legal)
  const m = v.match(/^(\d)/);                                    // 0–5 scale ("5-A …", "3-T …")
  if (m) { const n = +m[1]; return n >= 4 ? 'good' : n === 3 ? 'neutral' : 'bad'; }
  if (v.includes('ohne anmeldung') || v.includes('ohne werbung') || v === 'nein'
      || v.includes('datensparsam') || v.includes('geeignet') || v.includes('aaa')) return 'good';
  if (v.includes('notwendig') || v.includes('störend') || v.includes('kaum von werbung') || v === 'ja') return 'bad';
  return 'neutral';                                              // erweiterte Funktionen, zurückhaltend, A/AA/WCAG …
}

/** Keys shown as small icons on tiles + in the list. */
export const COMPACT_KEYS = ['Kosten', 'Werbung', 'Login', 'DSGVO', 'Jugendschutz', 'Barrierefreiheit'];

/** Grouped keys for the detail view. */
export const QUALITY_GROUPS: { titleKey: string; keys: string[] }[] = [
  { titleKey: 'q.group.access', keys: ['Kosten', 'Werbung', 'Login', 'DSGVO', 'Barrierefreiheit'] },
  { titleKey: 'q.group.legal', keys: ['Jugendschutz', 'Persönlichkeitsrechte', 'Strafrecht', 'Urheberrecht', 'Datenschutz (rechtl.)'] },
  { titleKey: 'q.group.content', keys: ['Für Bildung geeignet', 'Aktualität', 'Sachrichtigkeit', 'Neutralität', 'Transparenz', 'Didaktik/Methodik', 'Medial passend', 'Sprachl. Angemessenheit'] },
];

/** Build display entries for the given keys from a source's quality dict (skips missing). */
export function qualityEntries(quality: Record<string, string> | undefined, keys: string[]): QualityEntry[] {
  if (!quality) return [];
  const out: QualityEntry[] = [];
  for (const key of keys) {
    const value = quality[key];
    if (!value) continue;
    const meta = META[key] ?? { icon: 'info', labelKey: key };
    out.push({ key, labelKey: meta.labelKey, icon: meta.icon, value, level: qualityLevel(value) });
  }
  return out;
}
