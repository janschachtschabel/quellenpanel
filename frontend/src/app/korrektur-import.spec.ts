import { describe, it, expect } from 'vitest';
import { formatAusDateiname, korrekturAusSteckbrief } from './korrekturen-utils';

describe('formatAusDateiname', () => {
  it('detects the format from the extension', () => {
    expect(formatAusDateiname('korrekturen.csv')).toBe('csv');
    expect(formatAusDateiname('Liste.XLSX')).toBe('xlsx');
    expect(formatAusDateiname('a.b.json')).toBe('json');
  });
  it('returns null for unsupported files', () => {
    expect(formatAusDateiname('x.xls')).toBeNull();
    expect(formatAusDateiname('ohne-endung')).toBeNull();
  });
});

describe('korrekturAusSteckbrief', () => {
  it('blacklists a record by its node id, with the name as comment', () => {
    expect(korrekturAusSteckbrief('blacklist', { name: 'Quarks', nodeId: 'abc' })).toEqual(
      { typ: 'node', schluessel: 'abc', aktion: 'blacklist', wert: '', kommentar: 'Quarks' });
  });
  it('adds a description for the record\'s Bezugsquelle (falls back to the name)', () => {
    expect(korrekturAusSteckbrief('beschreibung', { name: 'Quarks', bezugsquelle: 'YouTube' })).toEqual(
      { typ: 'bezugsquelle', schluessel: 'YouTube', aktion: 'beschreibung', wert: '', kommentar: '' });
    expect(korrekturAusSteckbrief('beschreibung', { name: 'Quarks' }).schluessel).toBe('Quarks');
  });
  it('cannot blacklist without node id', () => {
    expect(() => korrekturAusSteckbrief('blacklist', { name: 'X' })).toThrow();
  });
});
