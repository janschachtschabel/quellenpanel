import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map, shareReplay } from 'rxjs/operators';

import { Capabilities, ExportRow, FilterOptions, FullStats, RefreshStatus, SourceContents, SourceDetail, SourcesPage, Stats, TeamStats } from './models';

@Injectable({ providedIn: 'root' })
export class SourcesService {
  private readonly http = inject(HttpClient);
  private base = '/api';
  private tier = 0;  // access tier sent with list/detail requests; set by TierService
  private creds = false;  // send the session cookie cross-origin (team login on a trusted host)

  /**
   * Repoint the API base. Used when the app runs as an embedded custom element on a different
   * origin than the backend, where the default same-origin '/api' would not resolve. Empty or
   * whitespace input is ignored so a missing attribute keeps the same-origin default.
   */
  setBase(url: string): void {
    const trimmed = (url ?? '').trim();
    if (trimmed) this.base = trimmed.replace(/\/+$/, '');
  }

  /** Access tier sent with subsequent list/detail requests (set by TierService). */
  setTier(tier: number): void {
    this.tier = tier;
  }

  /**
   * Opt into credentialed (cookie) requests, needed only when the panel is embedded on a DIFFERENT
   * origin than the backend AND a team login should work there. Off by default: same-origin cookies
   * are sent regardless, and a wildcard-CORS public embed must NOT use credentials. The backend
   * must list this origin in QE_ALLOWED_ORIGINS. Read by the credentials HTTP interceptor.
   */
  setCredentials(on: boolean): void {
    this.creds = on;
  }

  useCredentials(): boolean {
    return this.creds;
  }

  sources(query: Record<string, string | number | boolean>): Observable<SourcesPage> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== null && value !== undefined) {
        params = params.set(key, String(value));
      }
    }
    params = params.set('tier', String(this.tier));
    return this.http.get<SourcesPage>(`${this.base}/sources`, { params });
  }

  detail(id: string): Observable<SourceDetail> {
    const params = new HttpParams().set('tier', String(this.tier));
    return this.http.get<SourceDetail>(`${this.base}/sources/${encodeURIComponent(id)}`, { params });
  }

  contents(id: string, maxItems = 12, skip = 0): Observable<SourceContents> {
    const params = new HttpParams().set('max_items', String(maxItems)).set('skip', String(skip));
    return this.http.get<SourceContents>(`${this.base}/sources/${encodeURIComponent(id)}/contents`, { params });
  }

  private readonly previewCache = new Map<string, Observable<string>>();

  /**
   * One representative preview image for a source, used to backfill tiles / list rows of
   * node-less sources (YouTube, Bayerischer Rundfunk, bare Bezugsquellen) that carry no own
   * preview. Cached per id via shareReplay, so concurrent tiles and revisited pages reuse the
   * single request; resolves to '' when there is no image (and on error — best-effort, never
   * breaks the card).
   */
  cardPreview(id: string): Observable<string> {
    let obs = this.previewCache.get(id);
    if (!obs) {
      obs = this.contents(id, 1).pipe(
        map((c) => c.nodes?.[0]?.previewUrl ?? ''),
        catchError(() => of('')),
        shareReplay(1),
      );
      this.previewCache.set(id, obs);
    }
    return obs;
  }

  filterOptions(): Observable<FilterOptions> {
    return this.http.get<FilterOptions>(`${this.base}/meta/filters`);
  }

  /** Tier-0 end-user statistics overview. */
  stats(): Observable<Stats> {
    return this.http.get<Stats>(`${this.base}/stats`);
  }

  /** Extended statistics overview (tier >= 1); the tier param caps it server-side. */
  fullStats(): Observable<FullStats> {
    const params = new HttpParams().set('tier', String(this.tier));
    return this.http.get<FullStats>(`${this.base}/stats`, { params });
  }

  /** Team data-problem addendum (tier 2, team login required). */
  teamStats(): Observable<TeamStats> {
    return this.http.get<TeamStats>(`${this.base}/stats/team`);
  }

  /** Tier capabilities for this client (drives the header tier controls). */
  capabilities(): Observable<Capabilities> {
    return this.http.get<Capabilities>(`${this.base}/capabilities`);
  }

  /** Team login — password via header (not the URL); backend replies with an httpOnly cookie. */
  login(pw: string): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/auth`, null, { headers: { 'X-Team-Password': pw } });
  }

  logout(): Observable<{ ok: boolean }> {
    return this.http.post<{ ok: boolean }>(`${this.base}/logout`, null);
  }

  /** Several records at the current tier — feeds the client-side multi-source PDF export. */
  batch(ids: string[]): Observable<{ items: SourceDetail[] }> {
    const params = new HttpParams().set('tier', String(this.tier));
    return this.http.post<{ items: SourceDetail[] }>(`${this.base}/sources/batch`, { ids }, { params });
  }

  /** Same-origin proxy URL for a repository preview image (lets jsPDF embed it without CORS taint). */
  thumbUrl(previewUrl: string): string {
    return `${this.base}/thumb?url=${encodeURIComponent(previewUrl)}`;
  }

  /** Download URL for the leak-safe flat export (tier 1+), carrying the current filters + tier so the
   * file matches the on-screen list. */
  exportUrl(format: 'csv' | 'json', query: Record<string, string | number | boolean>): string {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== null && value !== undefined) params = params.set(key, String(value));
    }
    params = params.set('tier', String(this.tier));
    return `${this.base}/export.${format}?${params.toString()}`;
  }

  /** The flat filtered records as JSON (tier 1+), carrying the current filters + tier — feeds the
   * client-side "print table" PDF so it matches the on-screen list. */
  exportRecords(query: Record<string, string | number | boolean>): Observable<ExportRow[]> {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== '' && value !== null && value !== undefined) params = params.set(key, String(value));
    }
    params = params.set('tier', String(this.tier));
    return this.http.get<ExportRow[]>(`${this.base}/export.json`, { params });
  }

  /** The data-problem audit protocol as Markdown text (team only) — fetched for the in-app viewer. */
  protokoll(): Observable<string> {
    return this.http.get(`${this.base}/protokoll.md`, { responseType: 'text' });
  }

  /** Trigger the live data rebuild (team only) — the same job the nightly scheduler runs. */
  refreshStart(): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.base}/jobs/refresh`, null);
  }

  /** Current progress of the live rebuild job (public status), polled while a refresh runs. */
  refreshStatus(): Observable<RefreshStatus> {
    return this.http.get<RefreshStatus>(`${this.base}/jobs/latest`);
  }
}
