/**
 * Builder for the "Tabelle drucken" PDF: the current filtered list as one landscape A4 table with
 * the WLO header. Pure (given the jsPDF/autotable entry points, the already-capped rows and a
 * pre-formatted date) so it is unit-testable; the PdfService owns the fetch + cap + save.
 */
import type { jsPDF } from 'jspdf';

import { ExportRow } from './models';
import { AutoTable, BAR, clip, M, MUTED, NAVY, num } from './pdf-brand';

export interface TableDocOpts {
  body: ExportRow[];   // rows to render (already capped by the caller)
  total: number;       // full row count before capping (for the header stamp)
  capped: boolean;
  cap: number;
  date: string;        // pre-formatted (de-DE) so the builder stays free of Date.now
}

/** Build the landscape list-table document. Returns the jsPDF doc; the caller triggers download. */
export function buildTableDoc(JsPDF: typeof jsPDF, autoTable: AutoTable, opts: TableDocOpts): jsPDF {
  const { body, total, capped, cap, date } = opts;
  const doc = new JsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const W = doc.internal.pageSize.getWidth();

  // Top brand bar + title + stamp (count · generation date).
  const sw = W / BAR.length;
  BAR.forEach((c, i) => { doc.setFillColor(...c); doc.rect(i * sw, 0, sw + 1, 6, 'F'); });
  doc.setFontSize(14); doc.setFont('helvetica', 'bold'); doc.setTextColor(...NAVY);
  doc.text('WissenLebtOnline · Quellenübersicht', M, 16);
  doc.setFontSize(9); doc.setFont('helvetica', 'normal'); doc.setTextColor(...MUTED);
  doc.text(`${num(total)} Quellen${capped ? ` (gekürzt auf ${num(cap)})` : ''} · erstellt ${date}`, M, 22);

  const KN: Record<string, string> = { crawler: 'Crawler', manuell: 'manuell', bezugsquelle: 'Bezugsquelle' };
  const pipe = (v: unknown): string => String(v ?? '').replace(/ \| /g, ', ');
  autoTable(doc, {
    startY: 26,
    head: [['Name', 'Art', 'Inhalte', 'Lizenz', 'OER', 'Bildungsstufen', 'Fächer', 'Erschließung']],
    body: body.map((r) => [
      clip(r.name, 46), KN[r.kind] || r.kind, num(r.contentCount), clip(r.Lizenz, 16),
      r.OER || '', clip(pipe(r.Bildungsstufen), 34), clip(pipe(r.Faecher), 34), clip(r.erschliessung, 26),
    ]),
    theme: 'striped',
    headStyles: { fillColor: NAVY, textColor: [255, 255, 255], fontSize: 8 },
    styles: { fontSize: 7, cellPadding: 1.6, overflow: 'linebreak' },
    columnStyles: { 0: { cellWidth: 62 }, 2: { halign: 'right', cellWidth: 18 }, 4: { halign: 'center', cellWidth: 12 } },
    margin: { left: M, right: M },
  });
  return doc;
}
