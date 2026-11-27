import { Injectable, effect, inject } from '@angular/core';
import { MatPaginatorIntl } from '@angular/material/paginator';
import { I18n } from './i18n.service';

const TEXTE = {
  de: { pro: 'Einträge pro Seite', next: 'Nächste Seite', prev: 'Vorherige Seite', first: 'Erste Seite', last: 'Letzte Seite', von: 'von', loc: 'de-DE' },
  en: { pro: 'Items per page', next: 'Next page', prev: 'Previous page', first: 'First page', last: 'Last page', von: 'of', loc: 'en-GB' },
} as const;

/** Beschriftung des Blätterns in der Sprache der App (Material liefert nur Englisch). */
@Injectable()
export class QuellenPaginatorIntl extends MatPaginatorIntl {
  private readonly i18n = inject(I18n);

  constructor() {
    super();
    this.setzen();
    effect(() => { this.i18n.lang(); this.setzen(); this.changes.next(); });
  }

  private setzen(): void {
    const t = TEXTE[this.i18n.lang()] ?? TEXTE.de;
    this.itemsPerPageLabel = t.pro;
    this.nextPageLabel = t.next;
    this.previousPageLabel = t.prev;
    this.firstPageLabel = t.first;
    this.lastPageLabel = t.last;
    this.getRangeLabel = (page: number, size: number, length: number) => {
      const n = (x: number) => x.toLocaleString(t.loc);
      if (!length || !size) return `0 ${t.von} ${n(length)}`;
      const start = page * size;
      const ende = Math.min(start + size, length);
      return `${n(start + 1)}–${n(ende)} ${t.von} ${n(length)}`;
    };
  }
}
