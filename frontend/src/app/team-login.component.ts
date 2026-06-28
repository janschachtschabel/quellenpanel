import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';

import { I18n } from './i18n.service';
import { TierService } from './tier.service';

/** Small Material dialog for the tier-2 (team) password login. Closes with `true` on success. */
@Component({
  selector: 'wlo-team-login',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule],
  template: `
    <h2 mat-dialog-title>{{ i18n.t('team.login.title') }}</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" style="width: 100%;">
        <mat-label>{{ i18n.t('team.login.password') }}</mat-label>
        <input matInput type="password" [(ngModel)]="pw" (keydown.enter)="submit()"
               autocomplete="current-password" autofocus>
      </mat-form-field>
      @if (error()) { <p class="err">{{ i18n.t('team.login.error') }}</p> }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ i18n.t('action.cancel') }}</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="busy()">
        {{ i18n.t('team.login.submit') }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`.err { color: #b00020; font-size: 13px; margin: 4px 0 0; }`],
})
export class TeamLoginComponent {
  private readonly tiers = inject(TierService);
  private readonly ref = inject(MatDialogRef<TeamLoginComponent>);
  readonly i18n = inject(I18n);

  pw = '';
  readonly error = signal(false);
  readonly busy = signal(false);

  submit(): void {
    if (!this.pw || this.busy()) return;
    this.busy.set(true);
    this.error.set(false);
    this.tiers.teamLogin(this.pw).subscribe({
      next: (ok) => {
        this.busy.set(false);
        ok ? this.ref.close(true) : this.error.set(true);
      },
      error: () => {
        this.busy.set(false);
        this.error.set(true);
      },
    });
  }
}
