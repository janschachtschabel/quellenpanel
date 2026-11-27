/**
 * Shared helpers of the light widget script (no framework, no dependencies).
 * Rules: data only via textContent/attributes, links only http(s) in a new tab, no cookies.
 */

export type Sprache = 'de' | 'en';

const TEXTE = {
  de: {
    laden: 'Wird geladen …', fehler: 'Das Quellenverzeichnis ist gerade nicht erreichbar. Bitte versuchen Sie es später erneut.',
    keine: 'Keine Quellen gefunden.', suche: 'Quellen durchsuchen', suchePh: 'Name, Thema …',
    inhalte: 'Inhalte', quellen: 'Quellen', neuerTab: '(öffnet in neuem Tab)', mehr: 'Zum Quellenverzeichnis',
    faecher: 'Fächer', stufen: 'Bildungsstufen', lizenz: 'Lizenz', oer: 'OER', website: 'Zur Website',
    ohneQuelle: 'Keine Quelle angegeben (Attribut quelle).',
  },
  en: {
    laden: 'Loading …', fehler: 'The source directory is not reachable right now. Please try again later.',
    keine: 'No sources found.', suche: 'Search sources', suchePh: 'Name, topic …',
    inhalte: 'contents', quellen: 'sources', neuerTab: '(opens in a new tab)', mehr: 'Open the source directory',
    faecher: 'Subjects', stufen: 'Educational levels', lizenz: 'License', oer: 'OER', website: 'Visit website',
    ohneQuelle: 'No source given (attribute quelle).',
  },
};
export type Texte = typeof TEXTE.de;

export function sprache(el: Element): Sprache {
  return el.getAttribute('sprache') === 'en' ? 'en' : 'de';
}

export function texte(s: Sprache): Texte {
  return TEXTE[s];
}

/** API base: the api-base attribute, else the widget script's origin + /api, else same-origin. */
export function apiBaseFor(scriptSrc: string, attr: string | null): string {
  const a = (attr ?? '').trim();
  if (a) return a.replace(/\/+$/, '');
  try {
    if (scriptSrc) return new URL(scriptSrc).origin + '/api';
  } catch { /* not a URL */ }
  return '/api';
}

function istAn(el: Element, name: string): boolean {
  if (!el.hasAttribute(name)) return false;
  const v = (el.getAttribute(name) ?? '').trim().toLowerCase();
  return v !== 'false' && v !== 'aus' && v !== '0' && v !== 'nein';
}

/** List filters from the shared attributes (fach, bildungsstufe, suche, nur-oer, max). */
export function queryFromAttributes(el: Element, defaultMax: number): URLSearchParams {
  const q = new URLSearchParams({ sort: 'contentCount', order: 'desc' });
  const fach = el.getAttribute('fach')?.trim();
  const stufe = el.getAttribute('bildungsstufe')?.trim();
  const suche = el.getAttribute('suche')?.trim();
  if (fach) q.set('subject', fach);
  if (stufe) q.set('level', stufe);
  if (suche && suche.toLowerCase() !== 'aus') q.set('q', suche);
  if (istAn(el, 'nur-oer')) q.set('oer', 'true');
  const max = parseInt(el.getAttribute('max') ?? '', 10);
  q.set('page_size', String(Number.isFinite(max) && max > 0 ? Math.min(max, 50) : defaultMax));
  return q;
}

export function formatZahl(n: number, s: Sprache): string {
  return new Intl.NumberFormat(s === 'en' ? 'en-US' : 'de-DE').format(n || 0);
}

export function sichererLink(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null;
  } catch {
    return null;
  }
}

/** Element with a class and optional text (always textContent). */
export function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

/** A link opening in a new tab (announced to screen readers); plain text for unsafe URLs. */
export function externerLink(href: string | null | undefined, text: string, s: Sprache, cls = 'wq-link'): HTMLElement {
  const safe = sichererLink(href);
  if (!safe) return el('span', cls, text);
  const a = el('a', cls, text);
  a.href = safe;
  a.target = '_blank';
  a.rel = 'noopener';
  a.title = texte(s).neuerTab;
  a.append(el('span', 'wq-sr', ' ' + texte(s).neuerTab));
  return a;
}

const _geladen = new Set<string>();

/** Add a stylesheet once per key — constructable stylesheet (CSP-friendly), else a <style>. */
export function styles(key: string, css: string): void {
  if (_geladen.has(key)) return;
  _geladen.add(key);
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(css);
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  } catch {
    const st = document.createElement('style');
    st.dataset['wq'] = key;
    st.textContent = css;
    document.head.append(st);
  }
}

/** GET JSON without cookies; rejects on HTTP errors and after 15 s. */
export async function holeJson<T = unknown>(url: string): Promise<T> {
  const ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = ctrl ? setTimeout(() => ctrl.abort(), 15000) : null;
  try {
    const r = await fetch(url, { credentials: 'omit', signal: ctrl?.signal, headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json() as T;
  } finally {
    if (timer) clearTimeout(timer);
  }
}
