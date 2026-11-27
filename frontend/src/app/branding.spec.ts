import { describe, it, expect } from 'vitest';
import { istFarbe, wendeBrandingAn, textAnteil, kontrast, mische } from './branding';

describe('branding from the profile', () => {
  it('accepts only #rrggbb colours', () => {
    expect(istFarbe('#003b7c')).toBe(true);
    expect(istFarbe('red; background:url(x)')).toBe(false);
    expect(istFarbe('#fff')).toBe(false);
    expect(istFarbe(undefined)).toBe(false);
  });

  it('sets valid colours as tokens on the host and ignores the rest', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#123456', accent: 'url(x)' });
    expect(el.style.getPropertyValue('--primary')).toBe('#123456');
    expect(el.style.getPropertyValue('--accent')).toBe('');
  });

  it('falls back to the defaults when the colour is removed (embed attribute farbe taken away)', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#ffeb3b', accent: '#e4f700' });
    expect(el.style.getPropertyValue('--primaryText')).not.toBe('');
    wendeBrandingAn(el, undefined);
    for (const p of ['--primary', '--accent', '--primaryText', '--focusColor', '--primaryForeground800']) {
      expect(el.style.getPropertyValue(p), p).toBe('');
    }
    wendeBrandingAn(el, { primary: '#123456' });
    wendeBrandingAn(el, { primary: 'kaputt' });
    expect(el.style.getPropertyValue('--primary')).toBe('');
  });
});

describe('light brand colours stay readable (review focus)', () => {
  it('uses dark text on a light primary and darker foreground tints', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#7fb2e5' });
    expect(el.style.getPropertyValue('--primaryForeground800')).toMatch(/var\(--primary\) \d+%, #000/);
    expect(el.style.getPropertyValue('--primaryText')).toMatch(/var\(--primary\) \d+%, #000/);
    expect(el.style.getPropertyValue('--focusColor')).toBe('var(--primaryText)');
  });

  it('keeps the defaults for a dark primary', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#003b7c' });
    expect(el.style.getPropertyValue('--primaryText')).toBe('');
  });
});

describe('mid-tone brand colours (review finding)', () => {
  for (const farbe of ['#1a73e8', '#0072bc', '#d32f2f', '#008080', '#7fb2e5', '#ffff00', '#003b7c']) {
    it(`text colour for ${farbe} reaches 4.5:1 on the light tint and white on it`, () => {
      const anteil = textAnteil(farbe);
      const text = mische(farbe, '#000000', anteil);
      const tint = mische(farbe, '#ffffff', 22);
      expect(kontrast(text, tint)).toBeGreaterThanOrEqual(4.5);
      expect(kontrast(text, '#f3f3f3')).toBeGreaterThanOrEqual(4.5);
      expect(kontrast(text, '#ffffff')).toBeGreaterThanOrEqual(4.5);
    });
  }

  it('sets a darker --primaryText for #1a73e8 and none for WLO blue', () => {
    const a = document.createElement('div');
    wendeBrandingAn(a, { primary: '#1a73e8' });
    expect(a.style.getPropertyValue('--primaryText')).toMatch(/color-mix\(in srgb, var\(--primary\) \d+%, #000\)/);
    const b = document.createElement('div');
    wendeBrandingAn(b, { primary: '#003b7c' });
    expect(b.style.getPropertyValue('--primaryText')).toBe('');
  });
});
