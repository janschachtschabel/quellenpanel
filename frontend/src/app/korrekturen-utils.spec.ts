import { describe, it, expect } from 'vitest';
import { AKTIONEN_JE_TYP, aktionsKonflikt, korrekturZeilen, filterKorrekturen } from './korrekturen-utils';
import { Korrektur } from './models';

const k = (id: number, typ: string, schluessel: string, aktion: string, kommentar = '', wert = ''): Korrektur =>
  ({ id, typ, schluessel, aktion, wert, kommentar, geaendert_von: 'JS', geaendert_am: '2026-11-26' });

const LIST = [
  k(0, 'node', '27c77a87-aaaa', 'blacklist', 'Quarks YouTube'),
  k(1, 'node', 'bf727265-bbbb', 'whitelist', 'Subjuntivo'),
  k(2, 'bezugsquelle', 'YouTube', 'beschreibung', '', 'Videos zum Lernen'),
];

describe('filterKorrekturen', () => {
  it('returns all without filter', () => {
    expect(filterKorrekturen(LIST, '', '', '').map(x => x.id)).toEqual([0, 1, 2]);
  });
  it('searches all text columns, case-insensitive', () => {
    expect(filterKorrekturen(LIST, 'youtube', '', '').map(x => x.id)).toEqual([0, 2]);
    expect(filterKorrekturen(LIST, 'LERNEN', '', '').map(x => x.id)).toEqual([2]);
    expect(filterKorrekturen(LIST, 'bf727', '', '').map(x => x.id)).toEqual([1]);
  });
  it('filters by type and action', () => {
    expect(filterKorrekturen(LIST, '', 'node', '').map(x => x.id)).toEqual([0, 1]);
    expect(filterKorrekturen(LIST, '', '', 'whitelist').map(x => x.id)).toEqual([1]);
    expect(filterKorrekturen(LIST, 'youtube', 'node', 'blacklist').map(x => x.id)).toEqual([0]);
  });
});

describe('AKTIONEN_JE_TYP', () => {
  it('matches the backend rules', () => {
    expect(AKTIONEN_JE_TYP['node']).toContain('blacklist');
    expect(AKTIONEN_JE_TYP['node']).not.toContain('beschreibung');
    expect(AKTIONEN_JE_TYP['bezugsquelle']).toEqual(['beschreibung', 'vorschaubild']);
  });
});

describe('korrekturZeilen (several actions for one key)', () => {
  it('expands one key into one row per action, trimming the key and sharing the comment', () => {
    const rows = korrekturZeilen({ typ: 'node', schluessel: ' abc ', kommentar: 'Serlo' },
      [{ aktion: 'whitelist', wert: '' }, { aktion: 'spider_setzen', wert: 'serlo_spider' }]);
    expect(rows).toEqual([
      { typ: 'node', schluessel: 'abc', aktion: 'whitelist', wert: '', kommentar: 'Serlo' },
      { typ: 'node', schluessel: 'abc', aktion: 'spider_setzen', wert: 'serlo_spider', kommentar: 'Serlo' },
    ]);
  });
});

describe('aktionsKonflikt', () => {
  it('accepts different actions', () => {
    expect(aktionsKonflikt(['whitelist', 'bezugsquelle_setzen', 'spider_setzen'])).toBe('');
  });
  it('rejects the same action twice', () => {
    expect(aktionsKonflikt(['vermerk', 'vermerk'])).toBe('doppelt');
  });
  it('rejects blacklist together with whitelist', () => {
    expect(aktionsKonflikt(['blacklist', 'whitelist'])).toBe('liste');
  });
});
