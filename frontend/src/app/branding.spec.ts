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
