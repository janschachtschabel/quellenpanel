import { describe, it, expect, vi, afterEach } from 'vitest';
import { apiBaseFor, externerLink, formatZahl, holeJson, queryFromAttributes, sichererLink, texte } from './core';

function element(attrs: Record<string, string>): HTMLElement {
  const e = document.createElement('div');
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}

describe('apiBaseFor', () => {
  it('prefers the api-base attribute, without trailing slash', () => {
    expect(apiBaseFor('https://q.example/widgets/quellenpanel-widgets.js', 'https://b.example/api/')).toBe('https://b.example/api');
  });
  it('falls back to the script origin + /api', () => {
    expect(apiBaseFor('https://q.example/widgets/quellenpanel-widgets.js', null)).toBe('https://q.example/api');
  });
  it('falls back to same-origin /api without a script URL', () => {
    expect(apiBaseFor('', null)).toBe('/api');
  });
});

describe('queryFromAttributes', () => {
  it('maps widget attributes to the API filters', () => {
    const q = queryFromAttributes(element({ fach: 'Mathematik', bildungsstufe: 'Primarstufe', suche: 'Bruch', 'nur-oer': '', max: '7' }), 10);
    expect(q.get('subject')).toBe('Mathematik');
    expect(q.get('level')).toBe('Primarstufe');
    expect(q.get('q')).toBe('Bruch');
    expect(q.get('oer')).toBe('true');
    expect(q.get('page_size')).toBe('7');
    expect(q.get('sort')).toBe('contentCount');
    expect(q.get('order')).toBe('desc');
  });
  it('uses the default size, caps max at 50 and ignores suche="aus"', () => {
    const q = queryFromAttributes(element({ max: '999', suche: 'aus' }), 10);
    expect(q.get('page_size')).toBe('50');
    expect(q.has('q')).toBe(false);
    expect(queryFromAttributes(element({ max: 'x' }), 10).get('page_size')).toBe('10');
    expect(queryFromAttributes(element({ 'nur-oer': 'false' }), 10).has('oer')).toBe(false);
  });
});

describe('formatZahl / texte', () => {
  it('formats per language', () => {
    expect(formatZahl(62867, 'de')).toBe('62.867');
    expect(formatZahl(62867, 'en')).toBe('62,867');
  });
  it('has German and English texts', () => {
    expect(texte('de').neuerTab).toContain('neuem Tab');
    expect(texte('en').neuerTab).toContain('new tab');
  });
});

describe('sichererLink / externerLink', () => {
  it('allows only http(s)', () => {
    expect(sichererLink('https://x.example/a')).toBe('https://x.example/a');
    expect(sichererLink('javascript:alert(1)')).toBeNull();
    expect(sichererLink('data:text/html,x')).toBeNull();
    expect(sichererLink('')).toBeNull();
  });
  it('builds a new-tab link with text only', () => {
    const a = externerLink('https://x.example', '<b>Name</b>', 'de');
    expect(a.getAttribute('target')).toBe('_blank');
    expect(a.getAttribute('rel')).toBe('noopener');
    expect(a.textContent).toContain('<b>Name</b>');
    expect(a.querySelector('b')).toBeNull();
  });
  it('renders plain text for unsafe URLs', () => {
    const n = externerLink('javascript:alert(1)', 'X', 'de');
    expect(n.tagName).toBe('SPAN');
  });
});

describe('holeJson', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('never sends cookies and throws on HTTP errors', async () => {
    const f = vi.fn().mockResolvedValue(new Response('{"a":1}', { status: 200 }));
    vi.stubGlobal('fetch', f);
    expect(await holeJson('/api/x')).toEqual({ a: 1 });
    expect(f.mock.calls[0][1].credentials).toBe('omit');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('no', { status: 500 })));
    await expect(holeJson('/api/x')).rejects.toThrow();
  });
});
