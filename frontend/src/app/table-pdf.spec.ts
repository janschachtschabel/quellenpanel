import { describe, it, expect } from 'vitest';
import { buildTableDoc } from './table-pdf';
import { ExportRow } from './models';

const row = (over: Partial<ExportRow> = {}): ExportRow => ({
  name: 'Serlo', kind: 'manuell', contentCount: 5, Lizenz: 'CC BY', OER: 'ja',
  Bildungsstufen: 'Sekundarstufe I', Faecher: 'Mathematik', erschliessung: 'im Bestand', ...over,
});

/** Decode the (uncompressed) PDF content so tests can assert the rendered text is present. */
function pdfText(doc: { output: (t: string) => string }): string {
  return atob(doc.output('datauristring').split(',')[1]);
}

describe('buildTableDoc', () => {
  it('renders a single-page landscape table with the header and row values', async () => {
    const jspdf = await import('jspdf');
    const autotable = await import('jspdf-autotable');
    const doc = buildTableDoc(jspdf.jsPDF, autotable.default,
      { body: [row({ name: 'SerloRow' }), row({ name: 'ZumRow' })], total: 2, capped: false, cap: 1500, date: '01.01.2026' });
    expect(doc.getNumberOfPages()).toBe(1);
    const text = pdfText(doc);
    expect(text).toContain('WissenLebtOnline');   // title (ASCII prefix of the header)
    expect(text).toContain('SerloRow');
    expect(text).toContain('ZumRow');
  });
});
