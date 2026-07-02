/**
 * Builder for the multi-source "Quellensteckbrief" PDF: one branded page per source with the same
 * field sections as the Quellensteckbriefe app. Pure (given the jsPDF/autotable entry points, the
 * data, preloaded thumbnails and the repo URL) so it can be unit-tested without a download; the
 * PdfService owns the fetch + save orchestration.
 */
import type { jsPDF } from 'jspdf';

import { SourceDetail } from './models';
import { arr, AutoTable, BAR, clip, clipLong, httpUrl, M, MUTED, NAVY, num, TEXT } from './pdf-brand';

/** Minimal shape of the autotable cell-hook data we use (typed locally to avoid the verbose lib
 * types). textColor must accept the lib's `Color` (string | number[]) so the hook stays assignable. */
interface AutoTableCell {
  section: string;
  column: { index: number };
  row: { index: number };
  cell: { x: number; y: number; width: number; height: number; styles: { textColor: unknown } };
}

/** A clickable value cell: row index in the body → URL (column 1). */
type CellLinks = Record<number, string>;

/** Download file name for the export: a single source keeps its (sanitised) name, several are counted. */
export function steckbriefFileName(items: SourceDetail[]): string {
  if (items.length === 1) {
    return `Steckbrief_${(items[0].name || 'quelle').replace(/[^\w]+/g, '_').slice(0, 40)}.pdf`;
  }
  return `Quellensteckbriefe_${items.length}.pdf`;
}

/** Build the multi-source Steckbrief document (one page per source). Returns the jsPDF doc; the
 * caller triggers the download. `repoUrl` is the configured edu-sharing repo (for the node link). */
export function buildSteckbriefDoc(
  JsPDF: typeof jsPDF,
  autoTable: AutoTable,
  items: SourceDetail[],
  thumbs: Record<string, string>,
  repoUrl: string,
): jsPDF {
  const doc = new JsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  const CW = W - 2 * M;
  let page = 0;

  const header = () => {
    const sw = W / BAR.length;
    BAR.forEach((c, i) => { doc.setFillColor(...c); doc.rect(i * sw, 0, sw + 1, 7, 'F'); });
    doc.setFontSize(12); doc.setFont('helvetica', 'bold'); doc.setTextColor(...NAVY);
    doc.text('WissenLebt', W - 52, 15);
    const w = doc.getTextWidth('WissenLebt');
    doc.setTextColor(236, 74, 112); doc.text('Online', W - 52 + w + 1, 15);
    doc.setFontSize(8); doc.setTextColor(...MUTED); doc.setFont('helvetica', 'normal');
    doc.text(`Quellensteckbrief · Seite ${page}`, M, 15);
  };
  const footer = () => {
    doc.setDrawColor(...MUTED); doc.setLineWidth(0.3); doc.line(M, H - 16, W - M, H - 16);
    doc.setFontSize(6.5); doc.setTextColor(...MUTED);
    doc.text('Gefördert vom Bundesministerium für Bildung und Forschung · Finanziert von der Europäischen Union', M, H - 11);
    doc.text(new Date().toLocaleDateString('de-DE'), W - M - 22, H - 11);
  };
  const section = (title: string, y: number): number => {
    doc.setFillColor(...NAVY); doc.rect(M, y, CW, 6.5, 'F');
    doc.setFontSize(9); doc.setTextColor(255, 255, 255); doc.setFont('helvetica', 'bold');
    doc.text(title, M + 2, y + 4.6);
    return y + 8.5;
  };
  const table = (y: number, body: string[][], head?: string[][], links?: CellLinks): number => {
    autoTable(doc, {
      startY: y, head, body, theme: head ? 'grid' : 'plain',
      headStyles: { fillColor: NAVY, textColor: [255, 255, 255], fontSize: 7 },
      styles: { fontSize: head ? 6.5 : 8, cellPadding: head ? 1.4 : 2, overflow: 'linebreak' },
      columnStyles: head
        ? {}
        : { 0: { fontStyle: 'bold', cellWidth: 46, textColor: MUTED }, 1: { cellWidth: 'auto', textColor: TEXT } },
      alternateRowStyles: { fillColor: [248, 250, 252] },
      rowPageBreak: 'avoid', margin: { left: M, right: M },
      // Value cells listed in `links` get the link colour + a clickable annotation.
      didParseCell: links ? (d: AutoTableCell) => {
        if (d.section === 'body' && d.column.index === 1 && links[d.row.index]) d.cell.styles.textColor = NAVY;
      } : undefined,
      didDrawCell: links ? (d: AutoTableCell) => {
        if (d.section === 'body' && d.column.index === 1 && links[d.row.index]) {
          doc.link(d.cell.x, d.cell.y, d.cell.width, d.cell.height, { url: links[d.row.index] });
        }
      } : undefined,
    });
    return (doc as unknown as { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 4;
  };
  const pageBreak = (y: number): number => {
    if (y > H - 46) { footer(); doc.addPage(); page++; header(); return 24; }
    return y;
  };

  items.forEach((r, idx) => {
    if (idx > 0) doc.addPage();
    page++; header();
    writeSource(r, thumbs[r.id], { doc, CW, section, table, pageBreak }, repoUrl);
    footer();
  });
  return doc;
}

/** Render one source's page body (header block + field sections). Separate from buildSteckbriefDoc
 * so the document scaffolding (paging, brand chrome) stays apart from the per-source content. */
function writeSource(
  r: SourceDetail,
  thumb: string | undefined,
  ctx: {
    doc: jsPDF; CW: number;
    section: (t: string, y: number) => number;
    table: (y: number, body: string[][], head?: string[][], links?: CellLinks) => number;
    pageBreak: (y: number) => number;
  },
  repoUrl: string,
): void {
  const { doc, CW, section, table, pageBreak } = ctx;
  const slotW = 38, maxH = 34, topY = 22;

  // Preview image left (aspect-ratio preserved, capped height), title/meta/description right.
  let dw = 0, dh = 0;
  if (thumb) {
    let ratio = 0.72, fmt = 'JPEG';
    try {
      const pr = doc.getImageProperties(thumb);
      if (pr?.width && pr?.height) ratio = pr.height / pr.width;
      if (pr?.fileType) fmt = pr.fileType;
    } catch { /* fall back to defaults */ }
    dw = slotW; dh = dw * ratio;
    if (dh > maxH) { dh = maxH; dw = dh / ratio; }
    try { doc.addImage(thumb, fmt, M, topY, dw, dh); } catch { dw = dh = 0; }
  }

  const tx = thumb ? M + slotW + 5 : M;
  const tw = thumb ? CW - slotW - 5 : CW;
  doc.setFontSize(15); doc.setFont('helvetica', 'bold'); doc.setTextColor(...NAVY);
  const titleLines = doc.splitTextToSize(r.name || '-', tw);
  titleLines.slice(0, 3).forEach((ln: string, i: number) => doc.text(ln, tx, topY + 5 + i * 6));
  let ty = topY + 5 + Math.min(3, titleLines.length) * 6 + 1;
  // Under the title: ONLY the Bezugsquelle (publisher). Count / status move to Allgemeine Infos.
  if (r.bezugsquelle) {
    doc.setFontSize(8.5); doc.setFont('helvetica', 'normal'); doc.setTextColor(...MUTED);
    doc.text(doc.splitTextToSize('Bezugsquelle: ' + r.bezugsquelle, tw).slice(0, 2), tx, ty);
    ty += 5;
  }
  if (r.description) {
    doc.setTextColor(...TEXT);
    const dl = doc.splitTextToSize(r.description, tw);
    dl.slice(0, thumb ? 3 : 4).forEach((ln: string, i: number) => doc.text(ln, tx, ty + i * 4));
    ty += Math.min(thumb ? 3 : 4, dl.length) * 4 + 1;
  }
  // Underlined link (clearly clickable); returns the drawn width for inline chaining.
  const drawLink = (text: string, x: number, yy: number, url: string): number => {
    const safe = httpUrl(url);
    if (!safe) { doc.setTextColor(...TEXT); doc.text(text, x, yy); return doc.getTextWidth(text); }
    doc.setTextColor(...NAVY);
    doc.textWithLink(text, x, yy, { url: safe });
    const w = doc.getTextWidth(text);
    doc.setDrawColor(...NAVY); doc.setLineWidth(0.2);
    doc.line(x, yy + 0.7, x + w, yy + 0.7);
    return w;
  };
  // Clickable source URL (self-link) + a short "(In der Suche »)" link — the » cues clickability.
  if (r.url || r.searchUrl) {
    doc.setFontSize(8);
    if (r.url) {
      const w = drawLink(clip(r.url, 78), tx, ty, r.url);
      // A plain (non-linked, non-underlined) gap separates the URL from the search link.
      if (r.searchUrl) drawLink('(In der Suche »)', tx + w + doc.getTextWidth('   '), ty, r.searchUrl);
    } else if (r.searchUrl) {
      drawLink('In der Suche öffnen »', tx, ty, r.searchUrl);
    }
    ty += 5;
  }
  let y = Math.max(ty, topY + dh) + 4;

  // Allgemeine Informationen: count, cataloguing status, source record (linked), spider, repo.
  // node id + spider come from `binding` (available from tier 1); the full prod link is internal (tier 2),
  // else built from the configured repo + node id.
  const nodeId = r.binding?.node || r.internal?.['Node-ID'];
  const nodeLink = r.internal?.['quelldatensatzProd']
    || (nodeId && repoUrl ? `${repoUrl}/edu-sharing/components/render/${nodeId}` : '');
  const spider = r.binding?.spider || r.internal?.['spider'] || r.internal?.['general_identifier'];
  const allg: string[][] = [['Inhaltsanzahl', num(r.contentCount)]];
  if (r.erschliessungsstatus) allg.push(['Erschließung', r.erschliessungsstatus]);
  const links: CellLinks = {};
  if (nodeId) { const nl = httpUrl(nodeLink); if (nl) links[allg.length] = nl; allg.push(['Quelldatensatz (Node-ID)', nodeId]); }
  if (spider) allg.push(['Crawler/Spider', spider]);
  if (repoUrl) allg.push(['Repository', repoUrl.replace(/^https?:\/\//, '')]);
  y = section('Allgemeine Informationen', y);
  y = table(y, allg, undefined, Object.keys(links).length ? links : undefined);

  // Bildung & Einordnung comes BEFORE Lizenz.
  const eduRows: string[][] = [
    ['Fächer', arr(r.subjects)],
    ['Bildungsstufen', arr(r.educationalContext)],
    ['Inhaltstypen', arr(r.contentTypes)],
    ['Zielgruppe', arr(r.targetGroup)],
    ['Alter', r.ageRange || ''],
    ['Sprache', r.language || ''],
    ['Lehrplanbezug', clip(arr(r.curriculum), 120)],
    ['Schlagworte', arr(r.keywords)],
  ].filter((row) => row[1].trim());
  y = section('Bildung & Einordnung', y);
  y = table(y, eduRows);

  y = section('Lizenz', y);
  y = table(y, [
    ['Lizenz', r.license || '-'],
    ['OER', r.oer ? 'ja' : '-'],
    ['Urheber', clip(r.author, 150) || '-'],
  ]);

  const quality = Object.entries(r.quality || {});
  if (quality.length) {
    y = pageBreak(y); y = section('Qualitätsmerkmale', y);
    y = table(y, quality.map(([k, v]) => [k, String(v)]));
  }

  // tier 1 (Details): metadata-generation provenance.
  if (r.fieldGeneration?.length) {
    y = pageBreak(y); y = section('Metadaten-Erzeugung (Crawler-Provenienz)', y);
    y = table(
      y,
      r.fieldGeneration.map((f) => [f.item || '', f.field || '-', f.aktiv ? 'aktiv' : (f.status || '-'), f.how || (f.aktiv ? 'aus Quelldaten' : '')]),
      [['Item', 'Feld', 'Status', 'Erzeugung']],
    );
  }

  // tier 2 (Audit): internal fields + data-problem markers.
  const internal = Object.entries(r.internal || {});
  if (internal.length) {
    y = pageBreak(y); y = section('Interne Infos (Team)', y);
    y = table(y, internal.map(([k, v]) => [k, String(v ?? '-')]));
  }
  if (r.flags?.length) {
    y = pageBreak(y); y = section('Datenproblem-Marker (Team)', y);
    y = table(y, [[r.flags.join(', ')]]);
  }

  // KI-Nutzung & Recht LAST (mirrors the Quellensteckbriefe profile order; long values clipped).
  const ki = Object.entries(r.ki || {}).map(([k, v]) => [k, clipLong(v)]).filter((row) => row[1]);
  if (ki.length) {
    y = pageBreak(y); y = section('KI-Nutzung & Recht', y);
    y = table(y, ki);
  }
}
