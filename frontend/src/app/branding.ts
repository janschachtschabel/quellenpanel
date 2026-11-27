/** Brand colours of the profile (/api/capabilities → branding), applied as edu-sharing tokens. */
export interface Branding { primary?: string; accent?: string }

export function istFarbe(v: unknown): v is string {
  return typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
}

const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));

/** Same result as CSS `color-mix(in srgb, a anteil%, b)`. */
export function mische(a: string, b: string, anteil: number): string {
  const x = rgb(a), y = rgb(b), t = anteil / 100;
  return '#' + x.map((v, i) => Math.round(v * t + y[i] * (1 - t)).toString(16).padStart(2, '0')).join('');
}

function luminanz(hex: string): number {
  const k = rgb(hex).map(c => c / 255).map(c => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * k[0] + 0.7152 * k[1] + 0.0722 * k[2];
}

/** WCAG contrast ratio of two #rrggbb colours. */
export function kontrast(a: string, b: string): number {
  const [h, d] = [luminanz(a), luminanz(b)].sort((p, q) => q - p);
  return (h + 0.05) / (d + 0.05);
}

/** Share (%) of the primary colour, mixed with black, that keeps it readable as text: 4.5:1 on the
 *  lightest tint it sits on (--primaryBackground100) and on the page background (#f3f3f3). 100 = as is. */
export function textAnteil(primary: string): number {
  const tint = mische(primary, '#ffffff', 22);
  for (const anteil of [100, 90, 80, 70, 60, 50, 40, 30, 20]) {
    const t = mische(primary, '#000000', anteil);
    if (kontrast(t, tint) >= 4.5 && kontrast(t, '#f3f3f3') >= 4.5) return anteil;
  }
  return 10;
}

const ABGELEITET = ['--primaryText', '--focusColor', '--primaryForeground800', '--primaryForeground900'];

/** Sets --primary / --accent on the host (SPA: <html>, element: the custom element); invalid values are
 *  ignored. If the primary is not readable as text on its own tints, --primaryText (also Material's
 *  primary and the focus colour) and the foreground tints are darkened until they reach 4.5:1. */
export function wendeBrandingAn(el: HTMLElement, b: Branding | undefined): void {
  if (!b) return;
  if (istFarbe(b.primary)) {
    el.style.setProperty('--primary', b.primary);
    const anteil = textAnteil(b.primary);
    if (anteil < 100) {
      el.style.setProperty('--primaryText', `color-mix(in srgb, var(--primary) ${anteil}%, #000)`);
      el.style.setProperty('--focusColor', 'var(--primaryText)');
      el.style.setProperty('--primaryForeground800', `color-mix(in srgb, var(--primary) ${Math.min(anteil, 78)}%, #000)`);
      el.style.setProperty('--primaryForeground900', `color-mix(in srgb, var(--primary) ${Math.min(anteil - 10, 62)}%, #000)`);
    } else {
      for (const p of ABGELEITET) el.style.removeProperty(p);
    }
  }
  if (istFarbe(b.accent)) el.style.setProperty('--accent', b.accent);
}
