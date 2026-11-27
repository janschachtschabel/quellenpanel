/** Brand colours of the profile (/api/capabilities → branding), applied as edu-sharing tokens. */
export interface Branding { primary?: string; accent?: string }

export function istFarbe(v: unknown): v is string {
  return typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
}

/** WCAG relative luminance of a #rrggbb colour. */
function luminanz(hex: string): number {
  const k = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
}

/** Sets --primary / --accent on the host (SPA: <html>, element: the custom element); invalid values are
 *  ignored. A light primary (white text below 4.5:1) gets dark text on primary surfaces and darker
 *  foreground tints, so any brand colour stays readable. */
export function wendeBrandingAn(el: HTMLElement, b: Branding | undefined): void {
  if (!b) return;
  if (istFarbe(b.primary)) {
    el.style.setProperty('--primary', b.primary);
    const weissKontrast = 1.05 / (luminanz(b.primary) + 0.05);
    if (weissKontrast < 4.5) {
      el.style.setProperty('--light-primary-text', '#1d1d1d');
      el.style.setProperty('--primaryText', 'color-mix(in srgb, var(--primary) 45%, #000)');
      el.style.setProperty('--focusColor', 'var(--primaryText)');
      el.style.setProperty('--primaryForeground800', 'color-mix(in srgb, var(--primary) 45%, #000)');
      el.style.setProperty('--primaryForeground900', 'color-mix(in srgb, var(--primary) 35%, #000)');
    } else {
      for (const p of ['--light-primary-text', '--primaryText', '--focusColor', '--primaryForeground800', '--primaryForeground900']) el.style.removeProperty(p);
    }
  }
  if (istFarbe(b.accent)) el.style.setProperty('--accent', b.accent);
}
