import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { SourcesService } from './sources.service';

/**
 * setBase exists for the embedded custom-element variant, where the backend lives on a different
 * origin than the default same-origin '/api'. These tests pin which URL the next request hits.
 */
describe('SourcesService.setBase', () => {
  let service: SourcesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SourcesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('defaults to the same-origin /api base', () => {
    service.stats().subscribe();
    httpMock.expectOne('/api/stats').flush({});
  });

  it('repoints requests after setBase, trimming a trailing slash', () => {
    service.setBase('https://backend.example/api/');
    service.stats().subscribe();
    httpMock.expectOne('https://backend.example/api/stats').flush({});
  });

  it('ignores empty / whitespace input and keeps the previous base', () => {
    service.setBase('   ');
    service.stats().subscribe();
    httpMock.expectOne('/api/stats').flush({});
  });
});

/**
 * cardPreview backfills the tile/list preview of node-less sources from one representative live
 * content, cached per id so concurrent cards and revisited pages reuse a single request.
 */
describe('SourcesService.cardPreview', () => {
  let service: SourcesService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(SourcesService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('resolves to the first content preview image', () => {
    let result: string | undefined;
    service.cardPreview('s1').subscribe((v) => (result = v));
    httpMock.expectOne('/api/sources/s1/contents?max_items=1&skip=0')
      .flush({ total: 3, nodes: [{ previewUrl: 'https://img/a.jpg' }, { previewUrl: 'https://img/b.jpg' }] });
    expect(result).toBe('https://img/a.jpg');
  });

  it('caches per id: a second subscription reuses the request', () => {
    service.cardPreview('s2').subscribe();
    httpMock.expectOne('/api/sources/s2/contents?max_items=1&skip=0')
      .flush({ total: 1, nodes: [{ previewUrl: 'https://img/c.jpg' }] });
    let replayed: string | undefined;
    service.cardPreview('s2').subscribe((v) => (replayed = v));
    httpMock.expectNone('/api/sources/s2/contents?max_items=1&skip=0'); // served from cache
    expect(replayed).toBe('https://img/c.jpg');
  });

  it('resolves to empty string when the source has no content', () => {
    let result: string | undefined;
    service.cardPreview('s3').subscribe((v) => (result = v));
    httpMock.expectOne('/api/sources/s3/contents?max_items=1&skip=0').flush({ total: 0, nodes: [] });
    expect(result).toBe('');
  });

  it('swallows errors and resolves to empty string (never breaks the card)', () => {
    let result: string | undefined;
    service.cardPreview('s4').subscribe((v) => (result = v));
    httpMock.expectOne('/api/sources/s4/contents?max_items=1&skip=0')
      .flush('upstream down', { status: 502, statusText: 'Bad Gateway' });
    expect(result).toBe('');
  });
});
