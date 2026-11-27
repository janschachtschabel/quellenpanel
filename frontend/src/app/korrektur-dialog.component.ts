import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { I18n } from './i18n.service';
import { KorrekturenService } from './korrekturen.service';
import { AKTIONEN_JE_TYP, TYPEN } from './korrekturen-utils';
import { KorrekturFelder } from './models';

export interface KorrekturDialogData { korrektur?: Partial<KorrekturFelder>; neu: boolean; }

/** Create / edit one correction. Asks for the editor's initials once (kept in this browser).
 *  Closes with the KorrekturFelder to save, or undefined on cancel. */
@Component({
  selector: 'wlo-korrektur-dialog',
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule],
  template: `
    <h2 mat-dialog-title>{{ i18n.t(data.neu ? 'korr.dialog.new' : 'korr.dialog.edit') }}</h2>
    <mat-dialog-content class="form">
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.typ') }}</mat-label>
        <mat-select [(ngModel)]="k.typ" (selectionChange)="typGeaendert()">
          @for (t of typen; track t) { <mat-option [value]="t">{{ t }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.schluessel') }}</mat-label>
        <input matInput [(ngModel)]="k.schluessel" [placeholder]="k.typ === 'node' ? 'Node-ID (UUID)' : 'Name der Bezugsquelle'">
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.aktion') }}</mat-label>
        <mat-select [(ngModel)]="k.aktion">
          @for (a of aktionen(); track a) { <mat-option [value]="a">{{ a }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.wert') }}</mat-label>
        <textarea matInput rows="3" [(ngModel)]="k.wert"></textarea>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.kommentar') }}</mat-label>
        <input matInput [(ngModel)]="k.kommentar">
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.wer') }}</mat-label>
        <input matInput [(ngModel)]="wer" maxlength="40" required>
        <mat-hint>{{ i18n.t('korr.wer.hint') }}</mat-hint>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ i18n.t('action.cancel') }}</button>
      <button mat-flat-button color="primary" (click)="speichern()" [disabled]="!gueltig()">{{ i18n.t('korr.save') }}</button>
    </mat-dialog-actions>
  `,
  styles: [`.form { display: flex; flex-direction: column; min-width: min(480px, 80vw); gap: 16px; }`],
})
export class KorrekturDialogComponent {
  readonly i18n = inject(I18n);
  readonly data = inject<KorrekturDialogData>(MAT_DIALOG_DATA);
  private readonly ref = inject(MatDialogRef<KorrekturDialogComponent>);
  private readonly svc = inject(KorrekturenService);
  readonly typen = TYPEN;
  k: KorrekturFelder = { typ: 'node', schluessel: '', aktion: 'blacklist', wert: '', kommentar: '', ...this.data.korrektur };
  wer = this.svc.wer();

  aktionen(): string[] { return AKTIONEN_JE_TYP[this.k.typ] ?? []; }

  typGeaendert(): void {
    if (!this.aktionen().includes(this.k.aktion)) this.k.aktion = this.aktionen()[0] ?? '';
  }

  gueltig(): boolean {
    return !!this.k.schluessel.trim() && this.aktionen().includes(this.k.aktion) && !!this.wer.trim();
  }

  speichern(): void {
    if (!this.gueltig()) return;
    this.svc.setWer(this.wer);
    this.ref.close({ ...this.k, schluessel: this.k.schluessel.trim() });
  }
}
