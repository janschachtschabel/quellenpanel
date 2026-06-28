import { Injectable, inject, signal } from '@angular/core';
import { Observable } from 'rxjs';
import { map, tap } from 'rxjs/operators';

import { SourcesService } from './sources.service';

/**
 * Access-tier state for the UI (mirrors the backend tier model):
 *   0 end user (default) · 1 Steckbrief ("Detailmodus") · 2 team.
 * Holds the current tier + what the backend allows (from /api/capabilities), drives the header
 * controls, and performs the team login. It pushes the active tier into SourcesService so every
 * data request is made at that tier — no circular dependency (SourcesService never imports this).
 */
@Injectable({ providedIn: 'root' })
export class TierService {
  private readonly api = inject(SourcesService);

  readonly tier = signal(0);            // currently viewed tier
  readonly maxTier = signal(0);         // highest tier this client may reach
  readonly tier1Gated = signal(false);  // tier 1 needs a password
  readonly teamAvailable = signal(false);
  readonly publicOnly = signal(false);
  readonly repoUrl = signal('');        // edu-sharing repo the data refers to (for detail + PDF)

  /** Fetch what the backend allows; drop the active tier if it is no longer permitted. */
  loadCapabilities(): void {
    this.api.capabilities().subscribe((c) => {
      this.maxTier.set(c.maxTier);
      this.tier1Gated.set(c.tier1Gated);
      this.teamAvailable.set(c.teamAvailable);
      this.publicOnly.set(c.publicOnly);
      this.repoUrl.set(c.repoUrl || '');
      if (this.tier() > c.maxTier) this.setTier(c.maxTier);
    });
  }

  setTier(t: number): void {
    this.tier.set(t);
    this.api.setTier(t);
  }

  /** Log in with the team password; on success the session cookie unlocks tier 2. */
  teamLogin(pw: string): Observable<boolean> {
    return this.api.login(pw).pipe(
      map((r) => !!r.ok),
      tap((ok) => {
        if (ok) {
          this.maxTier.set(2);
          this.teamAvailable.set(true);
          this.setTier(2);
        }
      }),
    );
  }

  teamLogout(): void {
    this.api.logout().subscribe(() => {
      this.setTier(0);
      this.loadCapabilities();
    });
  }
}
