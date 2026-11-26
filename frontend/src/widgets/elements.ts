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
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) {
  display: block; box-sizing: border-box; max-width: 100%;
  font: 400 15px/1.45 var(--wq-font, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif);
  color: var(--wq-text, #1d2433); text-align: left; letter-spacing: normal; text-transform: none;
  background: var(--wq-bg, #fff); border: 1px solid var(--wq-border, #dfe3ea); border-radius: var(--wq-radius, 10px);
  padding: 14px 16px;
}
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) * { box-sizing: border-box; }
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik).wq-schlicht {
  background: transparent; border: 0; padding: 0;
}
:is(wlo-quellen-liste, wlo-quellen-top) :is(ul, ol) { list-style: none; margin: 0; padding: 0; }
:is(wlo-quellen-liste, wlo-quellen-top) li {
  display: flex; gap: 10px; align-items: baseline; padding: 8px 0; margin: 0;
  border-bottom: 1px solid var(--wq-line, #eef0f4);
}
:is(wlo-quellen-liste, wlo-quellen-top) li:last-child { border-bottom: 0; }
:is(wlo-quellen-liste, wlo-quellen-top) .wq-main { flex: 1 1 auto; min-width: 0; }
:is(wlo-quellen-liste, wlo-quellen-top) .wq-meta { display: block; color: var(--wq-muted, #5b6475); font-size: 13px; }
:is(wlo-quellen-liste, wlo-quellen-top) .wq-num { color: var(--wq-muted, #5b6475); font-size: 13px; white-space: nowrap; }
wlo-quellen-top .wq-rang {
  flex: 0 0 1.8em; font-weight: 700; color: var(--wq-accent, #003b7c); text-align: right;
}
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) a.wq-link {
  color: var(--wq-link, #003b7c); font-weight: 600; text-decoration: none; background: none;
}
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) a.wq-link:hover { text-decoration: underline; }
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) a.wq-link:focus-visible {
  outline: 2px solid var(--wq-accent, #003b7c); outline-offset: 2px;
}
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) .wq-sr {
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip: rect(0 0 0 0); border: 0;
}
wlo-quellen-liste input.wq-suche {
  display: block; width: 100%; margin: 0 0 8px; padding: 8px 10px; font: inherit; color: inherit;
  background: var(--wq-input-bg, #fff); border: 1px solid var(--wq-border, #c9cfd9); border-radius: 6px;
}
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) .wq-status { color: var(--wq-muted, #5b6475); margin: 4px 0; }
:is(wlo-quellen-liste, wlo-quellen-top, wlo-quellen-zahl, wlo-quelle, wlo-quellen-statistik) .wq-titel { font-size: 16px; font-weight: 700; margin: 0 0 8px; }
wlo-quellen-zahl .wq-gross { font-size: 26px; font-weight: 700; color: var(--wq-accent, #003b7c); }
wlo-quelle .wq-beschreibung { margin: 6px 0; }
wlo-quelle .wq-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; padding: 0; list-style: none; }
wlo-quelle .wq-chips li { background: var(--wq-chip, #eef2f8); border-radius: 12px; padding: 2px 10px; font-size: 13px; }
wlo-quellen-statistik .wq-zeile { display: grid; grid-template-columns: minmax(6em, 40%) 1fr auto; gap: 8px; align-items: center; margin: 4px 0; font-size: 14px; }
wlo-quellen-statistik .wq-bar { height: 10px; background: var(--wq-accent, #003b7c); border-radius: 5px; min-width: 2px; }
`;

let _scriptSrc = '';

abstract class WqElement extends HTMLElement {
  static get observedAttributes(): string[] {
    return ['api-base', 'fach', 'bildungsstufe', 'suche', 'max', 'sprache', 'nur-oer', 'variante', 'quelle'];
  }
  private _laufend = 0;
  private _verbunden = false;

  protected get api(): string { return apiBaseFor(_scriptSrc, this.getAttribute('api-base')); }
  protected get s(): Sprache { return sprache(this); }

  connectedCallback(): void {
    styles('wq-basis', CSS);
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
  protected async aktualisieren(): Promise<void> {
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
  private _liste: HTMLElement | null = null;
  private _timer: ReturnType<typeof setTimeout> | null = null;

  protected override laden(): Promise<unknown> {
    const q = queryFromAttributes(this, 10);
    if (this._suchbegriff !== null) {
      if (this._suchbegriff) q.set('q', this._suchbegriff); else q.delete('q');
    }
    return holeJson(`${this.api}/sources?${q}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const mitSuche = (this.getAttribute('suche') ?? '').toLowerCase() !== 'aus';
    if (mitSuche && !this._feld) {
      const label = el('label', 'wq-sr', t.suche);
      const input = el('input', 'wq-suche');
      input.type = 'search';
      input.placeholder = t.suchePh;
      input.id = `wq-suche-${Math.random().toString(36).slice(2, 8)}`;
      label.htmlFor = input.id;
      input.value = this.getAttribute('suche') ?? '';
      input.addEventListener('input', () => {
        if (this._timer) clearTimeout(this._timer);
        this._timer = setTimeout(() => { this._suchbegriff = input.value.trim(); this.aktualisieren(); }, 300);
      });
      this._feld = input;
      this.replaceChildren(label, input);
    } else if (!mitSuche) {
      this._feld = null;
      this.replaceChildren();
    }
    this._liste?.remove();
    const items = ((daten as { items?: Karte[] }).items ?? []);
    const box = el('div', 'wq-ergebnis');
    box.setAttribute('aria-live', 'polite');
    if (!items.length) {
      box.append(el('p', 'wq-status', t.keine));
    } else {
      const ul = el('ul');
      for (const k of items) {
        const li = el('li');
        const main = el('span', 'wq-main');
        main.append(externerLink(k.url || k.searchUrl, k.name, this.s), el('span', 'wq-meta', zeileMeta(k, this.s)));
        li.append(main, el('span', 'wq-num', `${formatZahl(k.contentCount, this.s)} ${t.inhalte}`));
        ul.append(li);
      }
      box.append(ul);
    }
    this._liste = box;
    this.append(box);
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
    this.replaceChildren(p, externerLink(new URL(ziel, location.href).href, t.mehr, this.s));
  }
}

class EineQuelle extends WqElement {
  protected override laden(): Promise<unknown> {
    const id = (this.getAttribute('quelle') ?? '').trim();
    if (!id) return Promise.reject(new Error('quelle fehlt'));
    return holeJson(`${this.api}/sources/${encodeURIComponent(id)}`);
  }

  protected override zeichnen(daten: unknown): void {
    const t = texte(this.s);
    const k = daten as Karte;
    const teile: HTMLElement[] = [el('p', 'wq-titel', k.name)];
    if (k.description) teile.push(el('p', 'wq-beschreibung', k.description));
    const chips = el('ul', 'wq-chips');
    for (const v of [...(k.subjects ?? []).slice(0, 6), ...(k.educationalContext ?? []).slice(0, 4)]) chips.append(el('li', '', v));
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
    const max = Math.min(parseInt(this.getAttribute('max') ?? '', 10) || 8, 30);
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

/** Tiles / whole app: load the Angular element bundle once, when such an element appears. */
function schwereNachladen(): void {
  const gefunden = document.querySelectorAll<HTMLElement>(SCHWER.join(','));
  if (!gefunden.length || _bundleGeladen) return;
  _bundleGeladen = true;
  const api = apiBaseFor(_scriptSrc, null);
  gefunden.forEach(e => { if (!e.hasAttribute('api-base') && _scriptSrc) e.setAttribute('api-base', api); });
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

/** Register all light elements (idempotent) and watch for the heavy ones. */
export function definiereElemente(scriptSrc: string): void {
  _scriptSrc = scriptSrc;
  const defs: [string, CustomElementConstructor][] = [
    ['wlo-quellen-liste', QuellenListe], ['wlo-quellen-top', QuellenTop], ['wlo-quellen-zahl', QuellenZahl],
    ['wlo-quelle', EineQuelle], ['wlo-quellen-statistik', QuellenStatistik],
  ];
  for (const [name, cls] of defs) if (!customElements.get(name)) customElements.define(name, cls);
  schwereNachladen();
  if (!_bundleGeladen && typeof MutationObserver !== 'undefined') {
    try {
      const mo = new MutationObserver(() => { schwereNachladen(); if (_bundleGeladen) mo.disconnect(); });
      mo.observe(document.documentElement, { childList: true, subtree: true });
    } catch { /* environment without MutationObserver: heavy elements present at load still work */ }
  }
}
