import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withXhr } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { KorrekturenService } from './korrekturen.service';
import { SourcesService } from './sources.service';

const K = { typ: 'node', schluessel: '27c77a87-8250-4a26-9d95-3b24cd162539', aktion: 'blacklist', wert: '', kommentar: '' };

describe('KorrekturenService', () => {
  let svc: KorrekturenService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.removeItem('qe.wer');
    TestBed.configureTestingModule({ providers: [provideHttpClient(withXhr()), provideHttpClientTesting()] });
    svc = TestBed.inject(KorrekturenService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('reads the corrections from the team API', () => {
    svc.lesen().subscribe();
    http.expectOne('/api/team/korrekturen').flush({ version: 'v', eintraege: [], fehler: [], warnungen: [] });
  });

  it('follows the API base of SourcesService (embedded use)', () => {
    TestBed.inject(SourcesService).setBase('https://b.example/api');
    svc.lesen().subscribe();
    http.expectOne('https://b.example/api/team/korrekturen').flush({});
  });

  it('remembers the initials in localStorage', () => {
    expect(svc.wer()).toBe('');
    svc.setWer('  JS ');
    expect(svc.wer()).toBe('JS');
    expect(localStorage.getItem('qe.wer')).toBe('JS');
  });

  it('creates, changes and deletes with initials and version', () => {
    svc.setWer('JS');
    svc.anlegen(K, 'v1').subscribe();
    const post = http.expectOne('/api/team/korrekturen');
    expect(post.request.method).toBe('POST');
    expect(post.request.body).toEqual({ korrektur: K, wer: 'JS', version: 'v1' });
    post.flush({});
    svc.aendern(3, K, 'v2').subscribe();
    const put = http.expectOne('/api/team/korrekturen/3');
    expect(put.request.method).toBe('PUT');
    expect(put.request.body.version).toBe('v2');
    put.flush({});
    svc.loeschen(3, 'v3').subscribe();
    const del = http.expectOne(r => r.url === '/api/team/korrekturen/3');
    expect(del.request.method).toBe('DELETE');
    expect(del.request.params.get('wer')).toBe('JS');
    expect(del.request.params.get('version')).toBe('v3');
    del.flush({});
  });

  it('sends imports as raw bytes with format, mode and mapping', () => {
    svc.setWer('JS');
    const blob = new Blob(['a;b']);
    svc.importVorschau(blob, 'csv', 'ersetzen', { schluessel: 'a', aktion: 'b' }).subscribe();
    const req = http.expectOne(r => r.url === '/api/team/korrekturen/import/vorschau');
    expect(req.request.body).toBe(blob);
    expect(req.request.headers.get('Content-Type')).toBe('application/octet-stream');
    expect(req.request.params.get('format')).toBe('csv');
    expect(req.request.params.get('modus')).toBe('ersetzen');
    expect(JSON.parse(req.request.headers.get('X-Zuordnung')!)).toEqual({ schluessel: 'a', aktion: 'b' });
    req.flush({});
    svc.importieren(blob, 'csv', 'ersetzen', null, 'v9').subscribe();
    const imp = http.expectOne(r => r.url === '/api/team/korrekturen/import');
    expect(imp.request.params.get('version')).toBe('v9');
    expect(imp.request.params.get('wer')).toBe('JS');
    expect(imp.request.headers.has('X-Zuordnung')).toBe(false);
    imp.flush({});
  });

  it('keeps the mapping header ASCII-only (column names with dashes or quotes)', () => {
    svc.importVorschau(new Blob(['x']), 'csv', 'ergaenzen', { kommentar: 'Kommentar – „intern“' }).subscribe();
    const req = http.expectOne(r => r.url === '/api/team/korrekturen/import/vorschau');
    const h = req.request.headers.get('X-Zuordnung')!;
    expect(/^[\x20-\x7e]*$/.test(h)).toBe(true);
    expect(JSON.parse(h)).toEqual({ kommentar: 'Kommentar – „intern“' });
    req.flush({});
  });

  it('uploads the crawler table', () => {
    svc.setWer('JS');
    const blob = new Blob(['x']);
    svc.crawlerVorschau(blob).subscribe();
    http.expectOne('/api/team/crawler/vorschau').flush({});
    svc.crawlerErsetzen(blob).subscribe();
    const req = http.expectOne(r => r.url === '/api/team/crawler');
    expect(req.request.params.get('wer')).toBe('JS');
    req.flush({});
  });

  it('builds the export and history URLs', () => {
    expect(svc.exportUrl()).toBe('/api/team/korrekturen.csv');
    svc.verlauf().subscribe();
    http.expectOne(r => r.url === '/api/team/korrekturen/verlauf').flush([]);
  });

  it('saves several rows one after another, each with the version of the previous answer', () => {
    svc.setWer('JS');
    const K2 = { ...K, aktion: 'vermerk', wert: 'Hinweis' };
    let ende: unknown;
    svc.anlegenAlle([K, K2], 'v1').subscribe(s => (ende = s));
    const a = http.expectOne('/api/team/korrekturen');
    expect(a.request.body).toEqual({ korrektur: K, wer: 'JS', version: 'v1' });
    a.flush({ version: 'v2' });
    const b = http.expectOne('/api/team/korrekturen');
    expect(b.request.body).toEqual({ korrektur: K2, wer: 'JS', version: 'v2' });
    b.flush({ version: 'v3' });
    expect(ende).toEqual({ version: 'v3' });
  });
});
