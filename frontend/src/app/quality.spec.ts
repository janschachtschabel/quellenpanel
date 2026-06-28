import { describe, it, expect } from 'vitest';
import { qualityEntries, qualityLevel } from './quality';

describe('qualityLevel', () => {
  it('treats "Nein - unauffällig" (the legal merkmale) as good', () => {
    expect(qualityLevel('Nein - unauffällig')).toBe('good');
  });

  it('treats explicit positive phrases as good', () => {
    expect(qualityLevel('ohne Anmeldung')).toBe('good');
    expect(qualityLevel('ohne Werbung')).toBe('good');
    expect(qualityLevel('nein')).toBe('good');           // Kosten: nein = free
    expect(qualityLevel('Datensparsam')).toBe('good');
    expect(qualityLevel('Ja - geeignet')).toBe('good');
  });

  it('grades the 0–5 scale by leading digit (>=4 good, 3 neutral, <3 bad)', () => {
    expect(qualityLevel('5 - hochaktuell/neuester Wissensstand')).toBe('good');
    expect(qualityLevel('4- aktueller Wissensstand')).toBe('good');
    expect(qualityLevel('3-A zeitlos aktuell')).toBe('neutral');
    expect(qualityLevel('2-A veraltete Darstellung, inhaltlich noch aktuell')).toBe('bad');
  });

  it('treats empty / unchecked values as unknown', () => {
    expect(qualityLevel('')).toBe('unknown');
    expect(qualityLevel('null')).toBe('unknown');
    expect(qualityLevel('Nicht geprüft')).toBe('unknown');
    expect(qualityLevel('Nicht DSGVO geprüft')).toBe('unknown');
  });

  it('treats clearly negative phrases as bad', () => {
    expect(qualityLevel('Anmeldung notwendig')).toBe('bad');
    expect(qualityLevel('enthält störend Werbung')).toBe('bad');
    expect(qualityLevel('ja')).toBe('bad');              // Kosten: ja = paid
  });

  it('falls back to neutral for the in-between cases', () => {
    expect(qualityLevel('Anmeldung erforderlich für erweiterte Funktionen')).toBe('neutral');
    expect(qualityLevel('AA (mittel)')).toBe('neutral');
    expect(qualityLevel('enthält zurückhaltend Werbung')).toBe('neutral');
  });
});

describe('qualityEntries', () => {
  it('returns nothing when the quality dict is missing or empty', () => {
    expect(qualityEntries(undefined, ['Kosten'])).toEqual([]);
    expect(qualityEntries({}, ['Kosten'])).toEqual([]);
  });

  it('keeps only the requested keys that have a value, in order', () => {
    const out = qualityEntries({ Kosten: 'nein', Login: 'ohne Anmeldung' }, ['Kosten', 'Werbung', 'Login']);
    expect(out.map((e) => e.key)).toEqual(['Kosten', 'Login']); // Werbung skipped (absent)
    expect(out[0]).toMatchObject({ key: 'Kosten', labelKey: 'q.kosten', icon: 'euro_symbol', value: 'nein', level: 'good' });
    expect(out[1].labelKey).toBe('q.login');
  });

  it('falls back to the raw key + info icon for an unknown merkmal', () => {
    const out = qualityEntries({ Unbekannt: 'x' }, ['Unbekannt']);
    expect(out[0]).toMatchObject({ key: 'Unbekannt', labelKey: 'Unbekannt', icon: 'info' });
  });
});
