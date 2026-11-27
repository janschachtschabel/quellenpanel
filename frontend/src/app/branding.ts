/** Brand colours of the profile (/api/capabilities → branding), applied as edu-sharing tokens. */
export interface Branding { primary?: string; accent?: string }

export function istFarbe(v: unknown): v is string {
  return typeof v === 'string' && /^#[0-9a-fA-F]{6}$/.test(v);
}

/** Sets --primary / --accent on the host (SPA: <html>, element: the custom element); invalid values are ignored. */
export function wendeBrandingAn(el: HTMLElement, b: Branding | undefined): void {
  if (!b) return;
  if (istFarbe(b.primary)) el.style.setProperty('--primary', b.primary);
  if (istFarbe(b.accent)) el.style.setProperty('--accent', b.accent);
}
