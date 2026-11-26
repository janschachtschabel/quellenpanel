import { Korrektur } from './models';

/** Valid actions per type — mirrors korrekturen._check in the backend. */
export const AKTIONEN_JE_TYP: Record<string, string[]> = {
  node: ['blacklist', 'whitelist', 'vermerk', 'bezugsquelle_setzen', 'spider_setzen'],
  bezugsquelle: ['beschreibung', 'vorschaubild'],
};

export const TYPEN = Object.keys(AKTIONEN_JE_TYP);

/** Free-text search over all text columns plus optional type/action filters. */
export function filterKorrekturen(list: Korrektur[], q: string, typ: string, aktion: string): Korrektur[] {
  const needle = q.trim().toLowerCase();
  return list.filter(k =>
    (!typ || k.typ === typ) && (!aktion || k.aktion === aktion) &&
    (!needle || [k.typ, k.schluessel, k.aktion, k.wert, k.kommentar, k.geaendert_von, k.geaendert_am]
      .some(v => (v ?? '').toLowerCase().includes(needle))));
}
