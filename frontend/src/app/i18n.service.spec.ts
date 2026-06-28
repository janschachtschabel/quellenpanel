import { describe, it, expect, beforeEach } from 'vitest';
import { I18n } from './i18n.service';

describe('I18n', () => {
  let i18n: I18n;

  beforeEach(() => {
    try { localStorage.removeItem('wlo-lang'); } catch { /* ignore */ }
    i18n = new I18n();
  });

  it('defaults to German and translates known keys', () => {
    expect(i18n.lang()).toBe('de');
    expect(i18n.t('view.tiles')).toBe('Kacheln');
    expect(i18n.t('filter.subject')).toBe('Fach');
    expect(i18n.t('q.kosten')).toBe('Kosten');
  });

  it('switches to English on set, and back to German', () => {
    i18n.set('en');
    expect(i18n.lang()).toBe('en');
    expect(i18n.t('view.tiles')).toBe('Tiles');
    expect(i18n.t('q.kosten')).toBe('Cost');
    i18n.set('de');
    expect(i18n.lang()).toBe('de');
  });

  it('falls back to the key itself for unknown translations', () => {
    expect(i18n.t('does.not.exist')).toBe('does.not.exist');
  });

  it('renders quality values: German verbatim, English looked up with fallback', () => {
    expect(i18n.tValue('ohne Anmeldung')).toBe('ohne Anmeldung'); // DE keeps the source value
    i18n.set('en');
    expect(i18n.tValue('ohne Anmeldung')).toBe('no login required');
    expect(i18n.tValue('Datensparsam')).toBe('data-minimising');
    expect(i18n.tValue('Unübersetzt XYZ')).toBe('Unübersetzt XYZ'); // EN falls back to source
  });

  it('persists the choice and a fresh instance reads it back', () => {
    i18n.set('en');
    expect(localStorage.getItem('wlo-lang')).toBe('en');
    expect(new I18n().lang()).toBe('en');
  });
});
