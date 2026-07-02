import { describe, it, expect } from 'vitest';
import { buildSteckbriefDoc, steckbriefFileName } from './steckbrief-pdf';
import { SourceDetail } from './models';

function fakeSource(over: Partial<SourceDetail> = {}): SourceDetail {
  return {
    id: 'x', name: 'Serlo', contentCount: 5, url: 'https://serlo.org', searchUrl: 'https://suche/x',
    bezugsquelle: 'Serlo', description: 'Mathe', subjects: ['Mathematik'], educationalContext: [],
    contentTypes: [], license: 'CC BY', oer: true, language: 'de', previewUrl: '',
    erschliessungsstatus: 'im Bestand verfuegbar', quality: {},
    keywords: [], author: '', targetGroup: [], curriculum: [], ageRange: '',
    ...over,
  };
}

/** Decode the (uncompressed) PDF content so tests can assert the rendered text is present. */
function pdfText(doc: { output: (t: string) => string }): string {
  return atob(doc.output('datauristring').split(',')[1]);
}

describe('buildSteckbriefDoc', () => {
  it('writes one page per source, with each source name and section titles rendered', async () => {
    const jspdf = await import('jspdf');
    const autotable = await import('jspdf-autotable');
    const items = [fakeSource({ id: 'a', name: 'SerloAlpha' }), fakeSource({ id: 'b', name: 'SerloBeta' })];
    const doc = buildSteckbriefDoc(jspdf.jsPDF, autotable.default, items, {}, 'https://repo.example');
    expect(doc.getNumberOfPages()).toBe(2);
    const text = pdfText(doc);
    expect(text).toContain('SerloAlpha');
    expect(text).toContain('SerloBeta');
    expect(text).toContain('Allgemeine Informationen');   // a section every source page renders
  });
});

describe('steckbriefFileName', () => {
  it('names a single source after it (sanitised)', () => {
    expect(steckbriefFileName([fakeSource({ name: 'Serlo Mathe!' })])).toBe('Steckbrief_Serlo_Mathe_.pdf');
  });

  it('counts multiple sources', () => {
    expect(steckbriefFileName([fakeSource(), fakeSource()])).toBe('Quellensteckbriefe_2.pdf');
  });
});
