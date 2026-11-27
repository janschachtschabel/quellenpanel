import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { definiereElemente, BUNDLE_PFAD } from './elements';
import { hoeheAntworten } from './embed';

const ITEMS = [
  { id: 'a', name: '<img src=x onerror=alert(1)>Serlo', contentCount: 8197, url: 'https://serlo.org', subjects: ['Mathematik'], educationalContext: ['Sekundarstufe I'], oer: true, license: 'CC_BY_SA', description: 'Lernplattform' },
  { id: 'b', name: 'Böse', contentCount: 10, url: 'javascript:alert(1)', subjects: [], educationalContext: [], oer: false, license: '', description: '' },
];

function antwort(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

async function render(html: string): Promise<HTMLElement> {
  const host = document.createElement('div');
  host.innerHTML = html;
  document.body.append(host);
  await new Promise(r => setTimeout(r, 30));
  return host;
}

describe('widget elements', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    definiereElemente('');
    fetchMock = vi.fn((url: string) => {
      if (url.includes('/kennzahl')) return antwort({ quellen: 128, inhalte: 41000 });
      if (url.includes('/stats')) return antwort({ topSubjects: [{ value: 'Mathematik', count: 30 }, { value: 'Chemie', count: 10 }], topLevels: [] });
      if (url.includes('/sources/')) return antwort(ITEMS[0]);
      return antwort({ total: 2, items: ITEMS });
    });
    vi.stubGlobal('fetch', fetchMock);
  });
  afterEach(() => { vi.unstubAllGlobals(); document.body.innerHTML = ''; });

  it('list renders names as text and unsafe links as plain text', async () => {
    const host = await render('<wlo-quellen-liste api-base="/api" fach="Mathematik"></wlo-quellen-liste>');
    expect(host.querySelector('img')).toBeNull();
    expect(host.textContent).toContain('<img src=x onerror=alert(1)>Serlo');
    const links = Array.from(host.querySelectorAll('a')).map(a => a.getAttribute('href'));
    expect(links).toContain('https://serlo.org/');
    expect(links.some(h => h?.startsWith('javascript'))).toBe(false);
    expect(host.querySelector('input[type=search]')).not.toBeNull();
    expect(fetchMock.mock.calls[0][0]).toContain('subject=Mathematik');
  });

  it('list variant "schlicht" without search', async () => {
    const host = await render('<wlo-quellen-liste api-base="/api" variante="schlicht" suche="aus"></wlo-quellen-liste>');
    expect(host.querySelector('wlo-quellen-liste')!.classList.contains('wq-schlicht')).toBe(true);
    expect(host.querySelector('input')).toBeNull();
  });

  it('top list is numbered and limited', async () => {
    const host = await render('<wlo-quellen-top api-base="/api" fach="Mathematik" max="1"></wlo-quellen-top>');
    expect(host.querySelectorAll('ol li').length).toBe(1);
    expect(fetchMock.mock.calls[0][0]).toContain('page_size=1');
  });

  it('key figure is formatted', async () => {
    const host = await render('<wlo-quellen-zahl api-base="/api" fach="Biologie"></wlo-quellen-zahl>');
    expect(host.textContent).toContain('128');
    expect(host.textContent).toContain('41.000');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/kennzahl?');
  });

  it('shows an error state on HTTP errors', async () => {
    fetchMock.mockImplementation(() => antwort({}, 500));
    const host = await render('<wlo-quellen-liste api-base="/api"></wlo-quellen-liste>');
    expect(host.textContent).toContain('nicht erreichbar');
  });

  it('single source and statistics', async () => {
    const host = await render('<wlo-quelle api-base="/api" quelle="crawler:serlo"></wlo-quelle><wlo-quellen-statistik api-base="/api"></wlo-quellen-statistik>');
    expect(fetchMock.mock.calls.some(c => String(c[0]).endsWith('/api/sources/crawler%3Aserlo'))).toBe(true);
    expect(host.textContent).toContain('Lernplattform');
    expect(host.querySelectorAll('wlo-quellen-statistik .wq-bar').length).toBe(2);
  });

  it('keeps the search field after a failed search (review finding)', async () => {
    const host = await render('<wlo-quellen-liste api-base="/api"></wlo-quellen-liste>');
    const input = host.querySelector('input')!;
    fetchMock.mockImplementation(() => antwort({}, 500));
    input.value = 'x';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(host.textContent).toContain('nicht erreichbar');
    expect(host.querySelector('input')).toBe(input);
    fetchMock.mockImplementation(() => antwort({ total: 2, items: ITEMS }));
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(host.querySelector('input')).toBe(input);
    expect(host.querySelectorAll('li').length).toBe(2);
  });

  it('announces results in one persistent live region (review finding)', async () => {
    const host = await render('<wlo-quellen-liste api-base="/api"></wlo-quellen-liste>');
    const live = host.querySelector('[aria-live]');
    expect(live).not.toBeNull();
    expect(live!.textContent).toContain('2 Quellen');
    const input = host.querySelector('input')!;
    input.value = 'y';
    input.dispatchEvent(new Event('input'));
    await new Promise(r => setTimeout(r, 400));
    expect(host.querySelector('[aria-live]')).toBe(live);
  });

  it('single source: shows the license and a clear message without id', async () => {
    const host = await render('<wlo-quelle api-base="/api" quelle="x"></wlo-quelle><wlo-quelle api-base="/api"></wlo-quelle>');
    expect(host.textContent).toContain('CC_BY_SA');
    expect(host.querySelectorAll('wlo-quelle')[1].textContent).toContain('Keine Quelle angegeben');
  });

  it('statistics clamps a negative max', async () => {
    const host = await render('<wlo-quellen-statistik api-base="/api" max="-3"></wlo-quellen-statistik>');
    expect(host.querySelectorAll('wlo-quellen-statistik .wq-bar').length).toBe(2);
  });

  it('widget styles reset host outlines inside the widget (probe finding)', async () => {
    await render('<wlo-quellen-liste api-base="/api"></wlo-quellen-liste>');
    const css = Array.from(document.adoptedStyleSheets ?? []).flatMap(sh => Array.from(sh.cssRules)).map(r => r.cssText).join('\n')
      + Array.from(document.querySelectorAll('style')).map(s => s.textContent).join('\n');
    const reset = css.split('}').find(r => r.includes(':is(p, ul, ol, li, a, span, div, input, label)'));
    expect(reset).toMatch(/outline(-width)?:\s*(0|0px|none)\b/);
  });

  it('heavy elements load the Angular bundle once', async () => {
    await render('<wlo-quellen-kacheln></wlo-quellen-kacheln><wlo-quellenpanel></wlo-quellenpanel>');
    definiereElemente('');   // the script normally runs deferred, after the elements are parsed
    definiereElemente('');
    const scripts = Array.from(document.querySelectorAll('script')).filter(s => s.src.endsWith(BUNDLE_PFAD));
    expect(scripts.length).toBe(1);
    document.querySelectorAll('script[src*="/widgets/element/"]').forEach(s => s.remove());
  });
});

describe('embed height', () => {
  it('answers only the height request, to the asking window', () => {
    const post = vi.fn();
    const src = { postMessage: post } as unknown as Window;
    expect(hoeheAntworten({ data: { type: 'quellenpanel:hoehe?' }, source: src, origin: 'https://gast.example' } as MessageEvent, 321)).toBe(true);
    expect(post).toHaveBeenCalledWith({ type: 'quellenpanel:hoehe', hoehe: 321 }, 'https://gast.example');
    expect(hoeheAntworten({ data: { type: 'anderes' }, source: src, origin: 'x' } as MessageEvent, 1)).toBe(false);
    expect(hoeheAntworten({ data: 'quellenpanel:hoehe?', source: src, origin: 'x' } as MessageEvent, 1)).toBe(false);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('accepts only the parent window and maps an opaque origin to *', () => {
    const post = vi.fn();
    const parent = { postMessage: post } as unknown as Window;
    const fremd = { postMessage: vi.fn() } as unknown as Window;
    expect(hoeheAntworten({ data: { type: 'quellenpanel:hoehe?' }, source: fremd, origin: 'https://x' } as MessageEvent, 5, parent)).toBe(false);
    expect(hoeheAntworten({ data: { type: 'quellenpanel:hoehe?' }, source: parent, origin: 'null' } as MessageEvent, 5, parent)).toBe(true);
    expect(post).toHaveBeenCalledWith({ type: 'quellenpanel:hoehe', hoehe: 5 }, '*');
  });

  it('farbe, hintergrund und rahmen="aus" gestalten das leichte Widget (nur gültige Farben)', async () => {
    const host = await render('<wlo-quellen-liste api-base="/api" farbe="#1a73e8" hintergrund="ffffff" rahmen="aus"></wlo-quellen-liste>');
    const w = host.querySelector('wlo-quellen-liste') as HTMLElement;
    expect(w.style.getPropertyValue('--wq-accent')).toBe('#1a73e8');
    expect(w.style.getPropertyValue('--wq-link')).toBe('#1a73e8');
    expect(w.style.getPropertyValue('--wq-bg')).toBe('#ffffff');
    expect(w.classList.contains('wq-ohne-rahmen')).toBe(true);
    w.setAttribute('farbe', 'red;x:y');
    await new Promise(r => setTimeout(r, 30));
    expect(w.style.getPropertyValue('--wq-accent')).toBe('');
  });
});
