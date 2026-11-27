import { describe, it, expect } from 'vitest';
import { istFarbe, wendeBrandingAn } from './branding';

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
    wendeBrandingAn(el, undefined);
    expect(el.style.getPropertyValue('--primary')).toBe('#123456');
  });
});

describe('light brand colours stay readable (review focus)', () => {
  it('uses dark text on a light primary and darker foreground tints', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#7fb2e5' });
    expect(el.style.getPropertyValue('--light-primary-text')).toBe('#1d1d1d');
    expect(el.style.getPropertyValue('--primaryForeground800')).toContain('45%');
    expect(el.style.getPropertyValue('--primaryText')).toContain('45%');
    expect(el.style.getPropertyValue('--focusColor')).toBe('var(--primaryText)');
  });

  it('keeps the defaults for a dark primary', () => {
    const el = document.createElement('div');
    wendeBrandingAn(el, { primary: '#003b7c' });
    expect(el.style.getPropertyValue('--light-primary-text')).toBe('');
  });
});
