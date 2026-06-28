import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import type { jsPDF } from 'jspdf';

import { ExportRow, SourceDetail } from './models';
import { SourcesService } from './sources.service';
import { TierService } from './tier.service';

/** autotable's functional entry point, resolved from the lazy import. */
type AutoTable = typeof import('jspdf-autotable')['default'];

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

// WissenLebtOnline brand palette (RGB), mirrored from the Quellensteckbriefe PDF.
const NAVY: [number, number, number] = [0, 59, 124];
const MUTED: [number, number, number] = [91, 107, 134];
const TEXT: [number, number, number] = [40, 50, 70];
// Top brand bar: blue → light blue → slate → lime → pink.
const BAR: Array<[number, number, number]> = [
  [0, 59, 124], [46, 108, 168], [123, 160, 201], [163, 206, 60], [236, 74, 112],
];
const M = 14; // page margin (mm)

const num = (n: number): string => (n || 0).toLocaleString('de-DE');
const arr = (x: unknown): string => (Array.isArray(x) ? x.join(', ') : String(x ?? ''));
/** Collapse whitespace and cap length (… ellipsis) — keeps table cells from overflowing. */
const clip = (v: unknown, n: number): string => {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n) + '…' : s;
};
/** Legal/AI fields can be huge (a whole robots.txt). Truncate long ones, drop the very long. */
const clipLong = (v: unknown): string => {
  const s = String(v ?? '').replace(/\s+/g, ' ').trim();
  if (s.length > 400) return '';
  return s.length > 200 ? s.slice(0, 200) + '…' : s;
};
/** Only http(s) URLs become clickable links in the PDF — never javascript:/data:/file: etc., even
 * if a record carried a malformed value. Returns the safe URL, or '' so the caller skips the link. */
const httpUrl = (u: unknown): string => {
  const s = String(u ?? '').trim();
  return /^https?:\/\//i.test(s) ? s : '';
};

/**
 * Client-side multi-source PDF export ("Sammel-PDF"), available from the Details tier (tier 1+). Builds one
 * Quellensteckbrief page per selected source — branding, preview image, and the same field
 * sections as the Quellensteckbriefe app — then triggers a download. The data is fetched at the
 * caller's current tier via /api/sources/batch, so tier-1/2 sections (legal, field generation,
 * internal) only appear when the user is actually authorised for them.
 *
 * jsPDF and jspdf-autotable are imported lazily: the public tier-0 bundle never pays for them,
 * the ~400 KB library loads only on the first export.
 */
@Injectable({ providedIn: 'root' })
export class PdfService {
  private readonly api = inject(SourcesService);
  private readonly tiers = inject(TierService);

  /** Fetch the selected sources, render the PDF, and download it. Returns the page (source)
   * count written — 0 when nothing came back, so the caller can show an appropriate message. */
  async generate(ids: string[]): Promise<number> {
    if (!ids.length) return 0;
    const { items } = await firstValueFrom(this.api.batch(ids));
    if (!items.length) return 0;

    const [jspdf, autotable] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
    const thumbs = await this.loadThumbs(items);
    this.buildDoc(jspdf.jsPDF, autotable.default, items, thumbs).save(this.fileName(items));
    return items.length;
  }

  /** "Print table": the current filtered list as a landscape A4 PDF table — mirrors the
   * Quellensteckbriefe "Tabelle drucken" (8 public columns, WLO header, capped at 1500 rows).
   * Fetches the flat export at the caller's tier (tier 1+); returns the row count + whether the
   * output was capped, so the caller can show a message. */
  async tablePdf(query: Record<string, string | number | boolean>): Promise<{ total: number; capped: boolean }> {
    const rows = await firstValueFrom(this.api.exportRecords(query));
    if (!rows.length) return { total: 0, capped: false };
    const CAP = 1500;
    const total = rows.length;
    const capped = total > CAP;
    const body = capped ? rows.slice(0, CAP) : rows;

    const [jspdf, autotable] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
    const doc = new jspdf.jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const W = doc.internal.pageSize.getWidth();

    // Top brand bar + title + stamp (count · generation date).
    const sw = W / BAR.length;
    BAR.forEach((c, i) => { doc.setFillColor(...c); doc.rect(i * sw, 0, sw + 1, 6, 'F'); });
    doc.setFontSize(14); doc.setFont('helvetica', 'bold'); doc.setTextColor(...NAVY);
    doc.text('WissenLebtOnline · Quellenübersicht', M, 16);
    doc.setFontSize(9); doc.setFont('helvetica', 'normal'); doc.setTextColor(...MUTED);
    doc.text(`${num(total)} Quellen${capped ? ` (gekürzt auf ${num(CAP)})` : ''} · erstellt ${new Date().toLocaleDateString('de-DE')}`, M, 22);

    const KN: Record<string, string> = { crawler: 'Crawler', manuell: 'manuell', bezugsquelle: 'Bezugsquelle' };
    const pipe = (v: unknown): string => String(v ?? '').replace(/ \| /g, ', ');
    autotable.default(doc, {
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
    doc.save('WLO-Quellenuebersicht.pdf');
    return { total, capped };
  }

  private fileName(items: SourceDetail[]): string {
    if (items.length === 1) {
      return `Steckbrief_${(items[0].name || 'quelle').replace(/[^\w]+/g, '_').slice(0, 40)}.pdf`;
    }
    return `Quellensteckbriefe_${items.length}.pdf`;
  }

  // ---- image preload (server proxy → DataURL, CORS-free for jsPDF) -----------------------------

  private async loadThumbs(items: SourceDetail[]): Promise<Record<string, string>> {
    const out: Record<string, string> = {};
    await Promise.all(
      items.map(async (r) => {
        if (!r.previewUrl) return;
        const data = await this.loadThumb(r.previewUrl);
        if (data) out[r.id] = data;
      }),
    );
    return out;
  }

  private async loadThumb(previewUrl: string): Promise<string | null> {
    try {
      const res = await fetch(this.api.thumbUrl(previewUrl));
      if (!res.ok) return null;
      const blob = await res.blob();
      return await new Promise<string | null>((resolve) => {
        const fr = new FileReader();
        fr.onloadend = () => resolve(fr.result as string);
        fr.onerror = () => resolve(null);
        fr.readAsDataURL(blob);
      });
    } catch {
      return null; // best-effort: a missing image must never abort the whole export
    }
  }

  // ---- document rendering ---------------------------------------------------------------------

  private buildDoc(
    JsPDF: typeof jsPDF,
    autoTable: AutoTable,
    items: SourceDetail[],
    thumbs: Record<string, string>,
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
      this.writeSource(r, thumbs[r.id], { doc, CW, section, table, pageBreak });
      footer();
    });
    return doc;
  }

  /** Render one source's page body (header block + field sections). Split out from buildDoc so the
   * document scaffolding (paging, brand chrome) stays separate from per-source content. */
  private writeSource(
    r: SourceDetail,
    thumb: string | undefined,
    ctx: {
      doc: jsPDF; CW: number;
      section: (t: string, y: number) => number;
      table: (y: number, body: string[][], head?: string[][], links?: CellLinks) => number;
      pageBreak: (y: number) => number;
    },
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
    const repoUrl = this.tiers.repoUrl();
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
}
