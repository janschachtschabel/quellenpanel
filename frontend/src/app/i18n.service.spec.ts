import { describe, it, expect, beforeEach } from 'vitest';
import { DICT, I18n } from './i18n.service';

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

  it('embedded preset sets the language without touching the host localStorage (review finding)', () => {
    i18n.set('en', false);
    expect(i18n.lang()).toBe('en');
    expect(localStorage.getItem('wlo-lang')).toBeNull();
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

describe('UI texts (write-copy rules, Etappe 6)', () => {
  const eintraege = Object.entries(DICT);

  it('every key has a German and an English text', () => {
    const leer = eintraege.filter(([, v]) => !v.de?.trim() || !v.en?.trim()).map(([k]) => k);
    expect(leer).toEqual([]);
  });

  it('German texts address the user formally (no du/dein/dich/dir)', () => {
    const du = eintraege.filter(([, v]) => /(^|[^\p{L}])(du|dein\p{L}*|dich|dir)([^\p{L}]|$)/iu.test(v.de)).map(([k]) => k);
    expect(du).toEqual([]);
  });

  it('empty and error texts name a next step', () => {
    const schritt = /(bitte|ändern|entfernen|versuchen|wählen|prüfen|setzen|zurücksetzen|change|remove|try|select|check|reset)/i;
    const keys = ['results.empty', 'export.tableEmpty', 'error.load', 'select.pdfEmpty', 'detail.contentNone', 'export.tableError', 'sync.error', 'select.pdfError'];
    const ohne = keys.filter(k => !schritt.test(DICT[k].de) || !schritt.test(DICT[k].en));
    expect(ohne).toEqual([]);
  });

  it('uses the typographic ellipsis, not three dots', () => {
    expect(eintraege.filter(([, v]) => v.de.includes('...') || v.en.includes('...')).map(([k]) => k)).toEqual([]);
  });
});
