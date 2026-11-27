import { Korrektur, KorrekturFelder } from './models';

/** Valid actions per type — mirrors korrekturen._check in the backend. */
export const AKTIONEN_JE_TYP: Record<string, string[]> = {
  node: ['blacklist', 'whitelist', 'vermerk', 'bezugsquelle_setzen', 'spider_setzen'],
  bezugsquelle: ['beschreibung', 'vorschaubild'],
};

export const TYPEN = Object.keys(AKTIONEN_JE_TYP);

/** One action of a new correction (several may share one key). */
export interface AktionWert { aktion: string; wert: string; }

/** One row per action for the same type and key; the comment is shared, the key trimmed. */
export function korrekturZeilen(
  basis: { typ: string; schluessel: string; kommentar: string },
  aktionen: AktionWert[],
): KorrekturFelder[] {
  return aktionen.map(a => ({ typ: basis.typ, schluessel: basis.schluessel.trim(), aktion: a.aktion,
                              wert: a.wert, kommentar: basis.kommentar }));
}

/** Why a set of actions for ONE key cannot be saved together: '' = fine, 'doppelt' = the same
 *  action twice, 'liste' = blacklist and whitelist at once (the later row would override). */
export function aktionsKonflikt(aktionen: string[]): '' | 'doppelt' | 'liste' {
  if (new Set(aktionen).size !== aktionen.length) return 'doppelt';
  if (aktionen.includes('blacklist') && aktionen.includes('whitelist')) return 'liste';
  return '';
}

/** Free-text search over all text columns plus optional type/action filters. */
export function filterKorrekturen(list: Korrektur[], q: string, typ: string, aktion: string): Korrektur[] {
  const needle = q.trim().toLowerCase();
  return list.filter(k =>
    (!typ || k.typ === typ) && (!aktion || k.aktion === aktion) &&
    (!needle || [k.typ, k.schluessel, k.aktion, k.wert, k.kommentar, k.geaendert_von, k.geaendert_am]
      .some(v => (v ?? '').toLowerCase().includes(needle))));
}

export type DateiFormat = 'csv' | 'json' | 'xlsx';

/** Import format from the file name's extension; null for anything else (e.g. old .xls). */
export function formatAusDateiname(name: string): DateiFormat | null {
  const ext = (name.split('.').pop() ?? '').toLowerCase();
  return name.includes('.') && (ext === 'csv' || ext === 'json' || ext === 'xlsx') ? ext : null;
}

/** Template of a correction started from a source's Steckbrief (team tier). */
export function korrekturAusSteckbrief(
  aktion: 'blacklist' | 'beschreibung',
  quelle: { name: string; nodeId?: string; bezugsquelle?: string },
): KorrekturFelder {
  if (aktion === 'blacklist') {
    if (!quelle.nodeId) throw new Error('Ohne Node-ID kann die Quelle nicht auf die Blacklist.');
    return { typ: 'node', schluessel: quelle.nodeId, aktion: 'blacklist', wert: '', kommentar: quelle.name };
  }
  return { typ: 'bezugsquelle', schluessel: quelle.bezugsquelle || quelle.name, aktion: 'beschreibung', wert: '', kommentar: '' };
}
