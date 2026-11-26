import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { CrawlerVorschau, ImportVorschau, KorrekturFelder, KorrekturStand, VerlaufEintrag, Zuordnung } from './models';
import { SourcesService } from './sources.service';

export type ImportFormat = 'csv' | 'json' | 'xlsx';
export type ImportModus = 'ergaenzen' | 'ersetzen';

const WER_KEY = 'qe.wer';

/** Team API for corrections and the crawler table (/api/team/…, team login required). */
@Injectable({ providedIn: 'root' })
export class KorrekturenService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(SourcesService);

  private url(path: string): string {
    return `${this.api.apiBase()}/team/${path}`;
  }

  /** The editor's initials, kept in this browser so they are asked once. */
  wer(): string {
    try { return localStorage.getItem(WER_KEY) ?? ''; } catch { return ''; }
  }

  setWer(wer: string): void {
    try { localStorage.setItem(WER_KEY, wer.trim()); } catch { /* private mode: keep for the request only */ }
  }

  lesen(): Observable<KorrekturStand> {
    return this.http.get<KorrekturStand>(this.url('korrekturen'));
  }

  anlegen(k: KorrekturFelder, version: string): Observable<KorrekturStand> {
    return this.http.post<KorrekturStand>(this.url('korrekturen'), { korrektur: k, wer: this.wer(), version });
  }

  aendern(id: number, k: KorrekturFelder, version: string): Observable<KorrekturStand> {
    return this.http.put<KorrekturStand>(this.url(`korrekturen/${id}`), { korrektur: k, wer: this.wer(), version });
  }

  loeschen(id: number, version: string): Observable<KorrekturStand> {
    const params = new HttpParams().set('wer', this.wer()).set('version', version);
    return this.http.delete<KorrekturStand>(this.url(`korrekturen/${id}`), { params });
  }

  verlauf(limit = 200): Observable<VerlaufEintrag[]> {
    return this.http.get<VerlaufEintrag[]>(this.url('korrekturen/verlauf'), { params: { limit } });
  }

  exportUrl(): string {
    return this.url('korrekturen.csv');
  }

  private raw(zuordnung: Zuordnung | null): HttpHeaders {
    let h = new HttpHeaders({ 'Content-Type': 'application/octet-stream' });
    if (zuordnung) h = h.set('X-Zuordnung', JSON.stringify(zuordnung));
    return h;
  }

  importVorschau(file: Blob, format: ImportFormat, modus: ImportModus, zuordnung: Zuordnung | null): Observable<ImportVorschau> {
    const params = new HttpParams().set('format', format).set('modus', modus);
    return this.http.post<ImportVorschau>(this.url('korrekturen/import/vorschau'), file,
      { params, headers: this.raw(zuordnung) });
  }

  importieren(file: Blob, format: ImportFormat, modus: ImportModus, zuordnung: Zuordnung | null,
              version: string): Observable<KorrekturStand> {
    const params = new HttpParams().set('format', format).set('modus', modus)
      .set('wer', this.wer()).set('version', version);
    return this.http.post<KorrekturStand>(this.url('korrekturen/import'), file,
      { params, headers: this.raw(zuordnung) });
  }

  crawlerVorschau(file: Blob): Observable<CrawlerVorschau> {
    return this.http.post<CrawlerVorschau>(this.url('crawler/vorschau'), file, { headers: this.raw(null) });
  }

  crawlerErsetzen(file: Blob): Observable<CrawlerVorschau> {
    return this.http.post<CrawlerVorschau>(this.url('crawler'), file,
      { params: { wer: this.wer() }, headers: this.raw(null) });
  }
}
