import { farbeOderNull, istAn } from '../app/einbettung';
import {
  Sprache, apiBaseFor, el, externerLink, formatZahl, holeJson, queryFromAttributes, sprache, styles, texte,
} from './core';

/** Path of the Angular element bundle (tiles view / whole app), relative to the widget host. */
export const BUNDLE_PFAD = '/widgets/element/main.js';
const SCHWER = ['wlo-quellen-kacheln', 'wlo-quellenpanel'];

interface Karte {
  id: string; name: string; contentCount: number; url?: string; searchUrl?: string;
  subjects?: string[]; educationalContext?: string[]; oer?: boolean; license?: string; description?: string;
}

const CSS = `
.wq-w.wq-w {
  display: block; box-sizing: border-box; max-width: 100%;
  font: 400 15px/1.45 var(--wq-font, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif);
  color: var(--wq-text, #1d2433); text-align: left; letter-spacing: normal; text-transform: none;
  background: var(--wq-bg, #fff); border: 1px solid var(--wq-border, #dfe3ea); border-radius: var(--wq-radius, 10px);
  padding: 14px 16px;
}

/* rahmen="aus": nahtlos in die Gastseite. */
.wq-w.wq-w.wq-ohne-rahmen { border: 0; border-radius: 0; padding-left: 0; padding-right: 0; }

/* Reset inside the widgets, stronger than typical CMS theme rules (.entry-content ul …).
   Host rules with !important still win. */
.wq-w.wq-w :is(p, ul, ol, li, a, span, div, input, label) {
  margin: 0; padding: 0; border: 0; outline: 0; background: none; box-shadow: none; float: none;
  font: inherit; color: inherit; line-height: inherit; text-align: inherit; text-transform: none;
  letter-spacing: normal; text-decoration: none; text-indent: 0; list-style: none; min-height: 0; max-width: none;
}
.wq-w.wq-w :is(p, ul, ol, li, a, span, div)::before, .wq-w.wq-w :is(p, ul, ol, li, a, span, div)::after { content: none; }
.wq-w.wq-w * { box-sizing: border-box; }
.wq-w.wq-w.wq-schlicht {
  background: transparent; border: 0; padding: 0;
}
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w :is(ul, ol) { list-style: none; margin: 0; padding: 0; }
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w li {
  display: flex; gap: 10px; align-items: baseline; padding: 8px 0; margin: 0;
  border-bottom: 1px solid var(--wq-line, #eef0f4);
}
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w li:last-child { border-bottom: 0; }
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w .wq-main { flex: 1 1 auto; min-width: 0; }
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w .wq-meta { display: block; color: var(--wq-muted, #5b6475); font-size: 13px; }
:is(wlo-quellen-liste, wlo-quellen-top).wq-w.wq-w .wq-num { color: var(--wq-muted, #5b6475); font-size: 13px; white-space: nowrap; }
wlo-quellen-top.wq-w.wq-w .wq-rang {
  flex: 0 0 1.8em; font-weight: 700; color: var(--wq-accent, #003b7c); text-align: right;
}
.wq-w.wq-w a.wq-link {
  color: var(--wq-link, #003b7c); font-weight: 600; text-decoration: none; background: none;
}
.wq-w.wq-w a.wq-link:hover { text-decoration: underline; }
.wq-w.wq-w a.wq-link:focus-visible {
  outline: 2px solid var(--wq-accent, #003b7c); outline-offset: 2px;
}
.wq-w.wq-w .wq-sr {
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); border: 0;
}
wlo-quellen-liste.wq-w.wq-w input.wq-suche {
  display: block; width: 100%; margin: 0 0 8px; padding: 8px 10px; font: inherit; color: inherit;
  background: var(--wq-input-bg, #fff); border: 1px solid var(--wq-border, #c9cfd9); border-radius: 6px;
}
.wq-w.wq-w .wq-status { color: var(--wq-muted, #5b6475); margin: 4px 0; }
.wq-w.wq-w .wq-titel { font-size: 16px; font-weight: 700; margin: 0 0 8px; }
wlo-quellen-zahl.wq-w.wq-w .wq-gross { font-size: 26px; font-weight: 700; color: var(--wq-accent, #003b7c); }
wlo-quelle.wq-w.wq-w .wq-beschreibung { margin: 6px 0; }
wlo-quelle.wq-w.wq-w .wq-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; padding: 0; list-style: none; }
wlo-quelle.wq-w.wq-w .wq-chips li { background: var(--wq-chip, #eef2f8); border-radius: 12px; padding: 2px 10px; font-size: 13px; }
wlo-quellen-statistik.wq-w.wq-w .wq-zeile { display: grid; grid-template-columns: minmax(6em, 40%) 1fr auto; gap: 8px; align-items: center; margin: 4px 0; font-size: 14px; }
wlo-quellen-statistik.wq-w.wq-w .wq-bar { height: 10px; background: var(--wq-accent, #003b7c); border-radius: 5px; min-width: 2px; }
.wq-w.wq-w input.wq-suche:focus-visible { outline: 2px solid var(--wq-accent, #003b7c); outline-offset: 1px; }
`;

let _scriptSrc = '';

abstract class WqElement extends HTMLElement {
  static get observedAttributes(): string[] {
    return ['api-base', 'fach', 'bildungsstufe', 'suche', 'max', 'sprache', 'nur-oer', 'variante', 'quelle', 'link',
      'farbe', 'hintergrund', 'rahmen'];
  }
  private _laufend = 0;
  private _verbunden = false;

  protected get api(): string { return apiBaseFor(_scriptSrc, this.getAttribute('api-base')); }
  protected get s(): Sprache { return sprache(this); }

  connectedCallback(): void {
    styles('wq-basis', CSS);
    this.classList.add('wq-w');
    this._verbunden = true;
    this.aktualisieren();
  }

  disconnectedCallback(): void { this._verbunden = false; }

  attributeChangedCallback(): void {
    if (this._verbunden) this.aktualisieren();
  }

  protected status(text: string): void {
    this.replaceChildren(el('p', 'wq-status', text));
  }

  /** Load + render; a stale answer (attributes changed meanwhile) is dropped. */
  /** farbe / hintergrund (#rrggbb) und rahmen="aus" — für iframe-Nutzer, die keine CSS-Variablen setzen können. */
  private gestalten(): void {
    const farbe = farbeOderNull(this.getAttribute('farbe'));
    const grund = farbeOderNull(this.getAttribute('hintergrund'));
    for (const v of ['--wq-accent', '--wq-link']) {
      if (farbe) this.style.setProperty(v, farbe); else this.style.removeProperty(v);
    }
    if (grund) this.style.setProperty('--wq-bg', grund); else this.style.removeProperty('--wq-bg');
    this.classList.toggle('wq-ohne-rahmen', !istAn(this.getAttribute('rahmen')));
  }

  protected async aktualisieren(): Promise<void> {
    this.gestalten();
    this.classList.toggle('wq-schlicht', this.getAttribute('variante') === 'schlicht');
    const lauf = ++this._laufend;
    this.setAttribute('aria-busy', 'true');
    if (!this.childElementCount) this.status(texte(this.s).laden);
    try {
      const daten = await this.laden();
      if (lauf === this._laufend) this.zeichnen(daten);
    } catch {
      if (lauf === this._laufend) this.status(texte(this.s).fehler);
    } finally {
      if (lauf === this._laufend) this.removeAttribute('aria-busy');
    }
  }

  protected abstract laden(): Promise<unknown>;
  protected abstract zeichnen(daten: unknown): void;
}

function zeileMeta(k: Karte, s: Sprache): string {
  return (k.subjects ?? []).slice(0, 4).join(', ') || (k.educationalContext ?? []).slice(0, 3).join(', ') || (s === 'en' ? 'Source' : 'Quelle');
}

class QuellenListe extends WqElement {
  private _suchbegriff: string | null = null;
  private _feld: HTMLInputElement | null = null;
  private _ergebnis: HTMLElement | null = null;
  private _ansage: HTMLElement | null = null;
  private _timer: ReturnType<typeof setTimeout> | null = null;

  override disconnectedCallback(): void {
    super.disconnectedCallback();
    this._stoppeTimer();
  }

  private _stoppeTimer(): void {
    if (this._timer) clearTimeout(this._timer);
    this._timer = null;
  }

  /** Persistent skeleton: optional search field, result area, one polite live region for announcements. */
  private _geruest(): HTMLElement {
    const t = texte(this.s);
    const mitSuche = (this.getAttribute('suche') ?? '').toLowerCase() !== 'aus';
    const feldDa = !!this._feld && this.contains(this._feld);
    if (!mitSuche && this._feld) { this._stoppeTimer(); this._feld = null; this._suchbegriff = null; }
    if (!this._ergebnis || !this._ansage || !this.contains(this._ergebnis) || mitSuche !== feldDa) {
      const teile: HTMLElement[] = [];
      if (mitSuche) {
        const input = this._feld ?? this._neuesFeld();
        const label = el('label', 'wq-sr', t.suche);
        label.htmlFor = input.id;
        teile.push(label, input);
      }
      this._ergebnis = el('div', 'wq-ergebnis');
      this._ansage = el('p', 'wq-sr');
      this._ansage.setAttribute('aria-live', 'polite');
      teile.push(this._ergebnis, this._ansage);
      this.replaceChildren(...teile);
    }
    return this._ergebnis;
  }

  private _neuesFeld(): HTMLInputElement {
    const t = texte(this.s);
    const input = el('input', 'wq-suche');
    input.type = 'search';
    input.placeholder = t.suchePh;
    input.id = `wq-suche-${Math.random().toString(36).slice(2, 8)}`;
    input.value = this.getAttribute('suche') ?? '';
    input.addEventListener('input', () => {
      this._stoppeTimer();
      this._timer = setTimeout(() => { this._timer = null; this._suchbegriff = input.value.trim(); this.aktualisieren(); }, 300);
    });
    this._feld = input;
    return input;
  }

  protected override status(text: string): void {
    this._geruest().replaceChildren(el('p', 'wq-status', text));
    if (this._ansage) this._ansage.textContent = text;
  }

  protected override laden(): Promise<unknown> {
    const q = queryFromAttributes(this, 10);
    if (this._suchbegriff !== null) {
      if (this._suchbegriff) q.set('q', this._suchbegriff); else q.delete('q');
    }
    return holeJson(`${this.api}/sources?${q}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const box = this._geruest();
    const d = daten as { items?: Karte[]; total?: number };
    const items = d.items ?? [];
    if (!items.length) {
      box.replaceChildren(el('p', 'wq-status', t.keine));
      this._ansage!.textContent = t.keine;
      return;
    }
    const ul = el('ul');
    for (const k of items) {
      const li = el('li');
      const main = el('span', 'wq-main');
      main.append(externerLink(k.url || k.searchUrl, k.name, this.s), el('span', 'wq-meta', zeileMeta(k, this.s)));
      li.append(main, el('span', 'wq-num', `${formatZahl(k.contentCount, this.s)} ${t.inhalte}`));
      ul.append(li);
    }
    box.replaceChildren(ul);
    this._ansage!.textContent = `${formatZahl(d.total ?? items.length, this.s)} ${t.quellen}`;
  }
}

class QuellenTop extends WqElement {
  protected override laden(): Promise<unknown> {
    const q = queryFromAttributes(this, 10);
    q.delete('q');
    return holeJson(`${this.api}/sources?${q}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const max = Number(queryFromAttributes(this, 10).get('page_size'));
    const items = ((daten as { items?: Karte[] }).items ?? []).slice(0, max);
    const teile: HTMLElement[] = [];
    const fach = this.getAttribute('fach');
    teile.push(el('p', 'wq-titel', this.s === 'en'
      ? `Top ${items.length} sources${fach ? ' – ' + fach : ''}`
      : `Top ${items.length} Quellen${fach ? ' – ' + fach : ''}`));
    if (!items.length) {
      teile.push(el('p', 'wq-status', t.keine));
    } else {
      const ol = el('ol');
      items.forEach((k, i) => {
        const li = el('li');
        const main = el('span', 'wq-main');
        main.append(externerLink(k.url || k.searchUrl, k.name, this.s), el('span', 'wq-meta', `${formatZahl(k.contentCount, this.s)} ${t.inhalte}`));
        li.append(el('span', 'wq-rang', `${i + 1}.`), main);
        ol.append(li);
      });
      teile.push(ol);
    }
    this.replaceChildren(...teile);
  }
}

class QuellenZahl extends WqElement {
  protected override laden(): Promise<unknown> {
    const q = queryFromAttributes(this, 1);
    q.delete('page_size'); q.delete('sort'); q.delete('order');
    return holeJson(`${this.api}/kennzahl?${q}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const d = daten as { quellen: number; inhalte: number };
    const p = el('p', 'wq-zahlen');
    p.append(el('span', 'wq-gross', formatZahl(d.quellen, this.s)), ` ${t.quellen} · `,
      el('span', 'wq-gross', formatZahl(d.inhalte, this.s)), ` ${t.inhalte}`);
    const ziel = this.getAttribute('link') || this.api.replace(/\/api$/, '/');
    let href: string | undefined;
    try { href = new URL(ziel, location.href).href; } catch { href = undefined; }
    this.replaceChildren(p, externerLink(href, t.mehr, this.s));
  }
}

class EineQuelle extends WqElement {
  protected override laden(): Promise<unknown> {
    const id = (this.getAttribute('quelle') ?? '').trim();
    if (!id) return Promise.resolve(null);
    return holeJson(`${this.api}/sources/${encodeURIComponent(id)}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    if (!daten) { this.status(t.ohneQuelle); return; }
    const k = daten as Karte;
    const teile: HTMLElement[] = [el('p', 'wq-titel', k.name)];
    if (k.description) teile.push(el('p', 'wq-beschreibung', k.description));
    const chips = el('ul', 'wq-chips');
    for (const v of [...(k.subjects ?? []).slice(0, 6), ...(k.educationalContext ?? []).slice(0, 4)]) chips.append(el('li', '', v));
    if (k.license) chips.append(el('li', '', `${t.lizenz}: ${k.license}`));
    if (k.oer) chips.append(el('li', '', t.oer));
    if (chips.childElementCount) teile.push(chips);
    teile.push(el('p', 'wq-meta', `${formatZahl(k.contentCount, this.s)} ${t.inhalte}`));
    teile.push(externerLink(k.url || k.searchUrl, t.website, this.s));
    this.replaceChildren(...teile);
  }
}

class QuellenStatistik extends WqElement {
  protected override laden(): Promise<unknown> {
    return holeJson(`${this.api}/stats`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const d = daten as { topSubjects?: { value: string; count: number }[]; topLevels?: { value: string; count: number }[] };
    const roh = parseInt(this.getAttribute('max') ?? '', 10);
    const max = roh > 0 ? Math.min(roh, 30) : 8;
    const teile: HTMLElement[] = [];
    for (const [titel, rows] of [[t.faecher, d.topSubjects ?? []], [t.stufen, d.topLevels ?? []]] as const) {
      if (!rows.length) continue;
      teile.push(el('p', 'wq-titel', titel));
      const top = rows.slice(0, max);
      const groesst = Math.max(...top.map(r => r.count), 1);
      for (const r of top) {
        const z = el('div', 'wq-zeile');
        const bar = el('div', 'wq-bar');
        bar.style.width = `${Math.round((r.count / groesst) * 100)}%`;
        bar.setAttribute('aria-hidden', 'true');
        z.append(el('span', '', r.value), el('div', 'wq-spur'), el('span', 'wq-num', formatZahl(r.count, this.s)));
        (z.children[1] as HTMLElement).append(bar);
        teile.push(z);
      }
    }
    if (!teile.length) teile.push(el('p', 'wq-status', t.keine));
    this.replaceChildren(...teile);
  }
}

function bundleUrl(): string {
  try { if (_scriptSrc) return new URL(BUNDLE_PFAD, _scriptSrc).href; } catch { /* relative */ }
  return BUNDLE_PFAD;
}

let _bundleGeladen = false;

/** Tiles / whole app: load the Angular element bundle once, when such an element appears.
 *  Heavy elements added later still get the api-base of the script's host. */
function schwereNachladen(): void {
  const gefunden = document.querySelectorAll<HTMLElement>(SCHWER.join(','));
  if (!gefunden.length) return;
  const api = apiBaseFor(_scriptSrc, null);
  gefunden.forEach(e => { if (!e.hasAttribute('api-base') && _scriptSrc) e.setAttribute('api-base', api); });
  if (_bundleGeladen) return;
  _bundleGeladen = true;
  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = bundleUrl().replace(/main\.js$/, 'styles.css');
  // zone.js polyfill first, then the app; dynamically inserted scripts keep this order only with async=false.
  const scripts = [bundleUrl().replace(/main\.js$/, 'polyfills.js'), bundleUrl()].map((src) => {
    const s = document.createElement('script');
    s.src = src;
    s.type = 'module';
    s.async = false;
    return s;
  });
  document.head.append(css, ...scripts);
}

let _beobachter = false;

/** Register all light elements (idempotent) and watch for the heavy ones. */
export function definiereElemente(scriptSrc: string): void {
  _scriptSrc = scriptSrc;
  const defs: [string, CustomElementConstructor][] = [
    ['wlo-quellen-liste', QuellenListe], ['wlo-quellen-top', QuellenTop], ['wlo-quellen-zahl', QuellenZahl],
    ['wlo-quelle', EineQuelle], ['wlo-quellen-statistik', QuellenStatistik],
  ];
  for (const [name, cls] of defs) if (!customElements.get(name)) customElements.define(name, cls);
  schwereNachladen();
  if (!_beobachter && typeof MutationObserver !== 'undefined') {
    try {
      const mo = new MutationObserver((records) => {
        if (records.some(r => Array.from(r.addedNodes).some(n => n.nodeType === 1))) schwereNachladen();
      });
      mo.observe(document.documentElement, { childList: true, subtree: true });
      _beobachter = true;
    } catch { /* environment without MutationObserver: heavy elements present at load still work */ }
  }
}
