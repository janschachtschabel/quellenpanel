import { describe, expect, it } from 'vitest';
import { leseEinbettung, wendeHintergrundAn, EINBETT_STANDARD } from './einbettung';

describe('Einbettungsoptionen', () => {
  it('ohne Angaben: alles sichtbar, keine Farben, keine feste Ansicht', () => {
    expect(leseEinbettung({})).toEqual(EINBETT_STANDARD);
    expect(EINBETT_STANDARD).toEqual({ kopf: true, fuss: true, filter: true, rahmen: true, ansicht: null, hintergrund: null, farbe: null });
  });

  it('kopf, fuss, filter, rahmen lassen sich mit "aus" ausblenden', () => {
    const o = leseEinbettung({ kopf: 'aus', fuss: 'aus', filter: 'aus', rahmen: 'aus' });
    expect([o.kopf, o.fuss, o.filter, o.rahmen]).toEqual([false, false, false, false]);
  });

  it('akzeptiert auch off/false/0/nein und ignoriert Groß-/Kleinschreibung', () => {
    for (const v of ['off', 'FALSE', '0', 'Nein', ' aus ']) expect(leseEinbettung({ kopf: v }).kopf).toBe(false);
    for (const v of ['an', 'on', '', 'quatsch']) expect(leseEinbettung({ kopf: v }).kopf).toBe(true);
  });

  it('ansicht: kacheln/liste (auch tiles/list), sonst keine Vorgabe', () => {
    expect(leseEinbettung({ ansicht: 'liste' }).ansicht).toBe('list');
    expect(leseEinbettung({ ansicht: 'list' }).ansicht).toBe('list');
    expect(leseEinbettung({ ansicht: 'Kacheln' }).ansicht).toBe('tile');
    expect(leseEinbettung({ ansicht: 'statistik' }).ansicht).toBeNull();
  });

  it('Farben nur als #rrggbb (auch ohne #), alles andere wird verworfen', () => {
    expect(leseEinbettung({ hintergrund: '#ffffff', farbe: '1a73e8' })).toMatchObject({ hintergrund: '#ffffff', farbe: '#1a73e8' });
    for (const bad of ['red', '#fff', 'url(x)', '#ffffff;color:red', 'transparent']) {
      expect(leseEinbettung({ hintergrund: bad, farbe: bad })).toMatchObject({ hintergrund: null, farbe: null });
    }
  });

  it('liest dieselben Optionen aus einem Query-String (App-Link, iframe)', () => {
    const o = leseEinbettung(new URLSearchParams('?kopf=aus&fuss=aus&ansicht=liste&hintergrund=%23ffffff'));
    expect(o).toMatchObject({ kopf: false, fuss: false, ansicht: 'list', hintergrund: '#ffffff' });
  });

  it('wendeHintergrundAn setzt die Flächen-Tokens am Element und entfernt sie wieder', () => {
    const el = document.createElement('div');
    wendeHintergrundAn(el, '#ffffff');
    expect(el.style.getPropertyValue('--backgroundColor')).toBe('#ffffff');
    expect(el.style.getPropertyValue('--wlo-bg')).toBe('#ffffff');
    wendeHintergrundAn(el, null);
    expect(el.style.getPropertyValue('--backgroundColor')).toBe('');
  });
});
