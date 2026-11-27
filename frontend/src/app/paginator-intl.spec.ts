import { describe, it, expect } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { MatPaginatorIntl } from '@angular/material/paginator';
import { appConfig } from './app.config';
import { I18n } from './i18n.service';

describe('Blättern auf Deutsch und Englisch', () => {
  it('nutzt die Sprache der App für Beschriftung und Bereich', () => {
    localStorage.setItem('wlo-lang', 'en');   // an earlier spec may have left English behind (CI order)
    TestBed.configureTestingModule({ providers: appConfig.providers });
    const intl = TestBed.inject(MatPaginatorIntl);
    const i18n = TestBed.inject(I18n);
    i18n.set('de', false);
    TestBed.tick();                       // the stored language starts as English
    expect(intl.itemsPerPageLabel).toBe('Einträge pro Seite');
    expect(intl.getRangeLabel(0, 25, 3721)).toBe('1–25 von 3.721');
    expect(intl.nextPageLabel).toBe('Nächste Seite');
    i18n.set('en', false);
    TestBed.tick();
    expect(intl.itemsPerPageLabel).toBe('Items per page');
    expect(intl.getRangeLabel(1, 25, 30)).toBe('26–30 of 30');
    i18n.set('de', false);
    localStorage.removeItem('wlo-lang');
  });
});
