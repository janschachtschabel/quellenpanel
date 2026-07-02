import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { SourceDetail } from './models';
import { SourcesService } from './sources.service';
import { TierService } from './tier.service';
import { buildSteckbriefDoc, steckbriefFileName } from './steckbrief-pdf';
import { buildTableDoc } from './table-pdf';

/**
 * Client-side PDF exports (tier 1+). This service only ORCHESTRATES: fetch the data, preload the
 * preview images through the same-origin proxy, then hand off to the pure document builders
 * (steckbrief-pdf / table-pdf, which are unit-tested) and trigger the download. jsPDF and
 * jspdf-autotable are imported lazily, so the public tier-0 bundle never pays for them (~400 KB).
 */
@Injectable({ providedIn: 'root' })
export class PdfService {
  private readonly api = inject(SourcesService);
  private readonly tiers = inject(TierService);

  /** Fetch the selected sources, render the multi-source Steckbrief PDF, and download it. Returns
   * the page (source) count written — 0 when nothing came back, so the caller can show a message. */
  async generate(ids: string[]): Promise<number> {
    if (!ids.length) return 0;
    const { items } = await firstValueFrom(this.api.batch(ids));
    if (!items.length) return 0;
    const [jspdf, autotable] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
    const thumbs = await this.loadThumbs(items);
    buildSteckbriefDoc(jspdf.jsPDF, autotable.default, items, thumbs, this.tiers.repoUrl())
      .save(steckbriefFileName(items));
    return items.length;
  }

  /** "Print table": the current filtered list as a landscape A4 table PDF (capped at 1500 rows).
   * Returns the row count + whether the output was capped, so the caller can show a message. */
  async tablePdf(query: Record<string, string | number | boolean>): Promise<{ total: number; capped: boolean }> {
    const rows = await firstValueFrom(this.api.exportRecords(query));
    if (!rows.length) return { total: 0, capped: false };
    const cap = 1500;
    const total = rows.length;
    const capped = total > cap;
    const body = capped ? rows.slice(0, cap) : rows;
    const [jspdf, autotable] = await Promise.all([import('jspdf'), import('jspdf-autotable')]);
    buildTableDoc(jspdf.jsPDF, autotable.default,
      { body, total, capped, cap, date: new Date().toLocaleDateString('de-DE') })
      .save('WLO-Quellenuebersicht.pdf');
    return { total, capped };
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
}
