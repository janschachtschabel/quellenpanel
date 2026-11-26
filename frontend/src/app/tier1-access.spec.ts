import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { credentialsInterceptor } from './credentials.interceptor';
import { SourcesService } from './sources.service';
import { TierService } from './tier.service';

/** Partner instances gate tier 1 behind QE_TIER1_PASSWORD; the UI must be able to send it. */
describe('tier-1 password', () => {
  let api: SourcesService;
  let tiers: TierService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([credentialsInterceptor])), provideHttpClientTesting()],
    });
    api = TestBed.inject(SourcesService);
    tiers = TestBed.inject(TierService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('sends no tier-1 header by default', () => {
    TestBed.inject(HttpClient).get('/api/stats').subscribe();
    expect(httpMock.expectOne('/api/stats').request.headers.has('X-Tier1-Password')).toBe(false);
  });

  it('attaches the tier-1 password to every API request once set', () => {
    api.setTier1Password('geheim');
    api.stats().subscribe();
    expect(httpMock.expectOne('/api/stats').request.headers.get('X-Tier1-Password')).toBe('geheim');
  });

  it('tier1Login switches to tier 1 when the backend grants it', () => {
    let ok: boolean | undefined;
    tiers.tier1Login('geheim').subscribe((r) => (ok = r));
    const req = httpMock.expectOne('/api/capabilities');
    expect(req.request.headers.get('X-Tier1-Password')).toBe('geheim');
    req.flush({ maxTier: 1, publicOnly: false, tier1Gated: true, teamAvailable: false, repoUrl: '', role: 'partner' });
    expect(ok).toBe(true);
    expect(tiers.tier()).toBe(1);
    expect(tiers.maxTier()).toBe(1);
  });

  it('tier1Login forgets a wrong password', () => {
    let ok: boolean | undefined;
    tiers.tier1Login('falsch').subscribe((r) => (ok = r));
    httpMock.expectOne('/api/capabilities')
      .flush({ maxTier: 0, publicOnly: false, tier1Gated: true, teamAvailable: false, repoUrl: '', role: 'partner' });
    expect(ok).toBe(false);
    expect(tiers.tier()).toBe(0);
    api.stats().subscribe();
    expect(httpMock.expectOne('/api/stats').request.headers.has('X-Tier1-Password')).toBe(false);
  });
});
