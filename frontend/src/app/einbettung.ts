/**
 * Einbettungsoptionen für eine schlanke Einbindung in fremde Seiten. Dieselben Namen gelten als
 * Attribute am Element (`<wlo-quellen-kacheln kopf="aus">`), als Query-Parameter der App
 * (`/?kopf=aus&ansicht=liste`) und der iframe-Seiten (`/embed/quellen-kacheln?…`).
 *
 *   kopf, fuss, filter, rahmen   "aus" blendet Kopfzeile, Fußzeile, Filterleiste bzw. Rahmen aus
 *   ansicht                      "kacheln" oder "liste" (fest, wenn der Kopf fehlt)
 *   hintergrund, farbe           Hintergrund- und Markenfarbe als #rrggbb
 */
import { istFarbe } from './branding';

export interface EinbettOptionen {
  kopf: boolean;
  fuss: boolean;
  filter: boolean;
  rahmen: boolean;
  ansicht: 'tile' | 'list' | null;
  hintergrund: string | null;
  farbe: string | null;
}

export const EINBETT_STANDARD: EinbettOptionen = Object.freeze({
  kopf: true, fuss: true, filter: true, rahmen: true, ansicht: null, hintergrund: null, farbe: null,
}) as EinbettOptionen;

type Quelle = Record<string, string | null | undefined> | URLSearchParams;

const AUS = new Set(['aus', 'off', 'false', '0', 'nein', 'no']);

function wert(q: Quelle, name: string): string | null {
  const v = q instanceof URLSearchParams ? q.get(name) : q[name];
  return v == null ? null : String(v);
}

/** true, solange der Wert nicht ausdrücklich „aus“ sagt (fehlend, leer oder unbekannt = an). */
export function istAn(v: string | null | undefined): boolean {
  return v == null || !AUS.has(String(v).trim().toLowerCase());
}

/** #rrggbb (auch ohne #) oder null — nichts anderes erreicht je ein style-Attribut. */
export function farbeOderNull(v: string | null | undefined): string | null {
  if (v == null) return null;
  const s = String(v).trim();
  const mitRaute = s.startsWith('#') ? s : '#' + s;
  return istFarbe(mitRaute) ? mitRaute.toLowerCase() : null;
}

export function ansichtOderNull(v: string | null | undefined): 'tile' | 'list' | null {
  const s = (v ?? '').trim().toLowerCase();
  if (s === 'kacheln' || s === 'tiles' || s === 'tile') return 'tile';
  if (s === 'liste' || s === 'list') return 'list';
  return null;
}

export function leseEinbettung(q: Quelle): EinbettOptionen {
  return {
    kopf: istAn(wert(q, 'kopf')),
    fuss: istAn(wert(q, 'fuss')),
    filter: istAn(wert(q, 'filter')),
    rahmen: istAn(wert(q, 'rahmen')),
    ansicht: ansichtOderNull(wert(q, 'ansicht')),
    hintergrund: farbeOderNull(wert(q, 'hintergrund')),
    farbe: farbeOderNull(wert(q, 'farbe')),
  };
}

const FLAECHEN = ['--backgroundColor', '--wlo-bg'];

/** Hintergrund der Seite um Kacheln und Liste (Karten bleiben weiß). null entfernt die Vorgabe. */
export function wendeHintergrundAn(el: HTMLElement, farbe: string | null): void {
  for (const t of FLAECHEN) {
    if (farbe) el.style.setProperty(t, farbe);
    else el.style.removeProperty(t);
  }
}
