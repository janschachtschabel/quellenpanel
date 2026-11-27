import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { I18n } from './i18n.service';
import { KorrekturenService } from './korrekturen.service';
import { AKTIONEN_JE_TYP, AktionWert, TYPEN, aktionsKonflikt, korrekturZeilen } from './korrekturen-utils';
import { KorrekturHilfeComponent } from './korrektur-hilfe.component';
import { KorrekturFelder } from './models';

export interface KorrekturDialogData { korrektur?: Partial<KorrekturFelder>; neu: boolean; }

/** Create corrections (one or several actions for the same key) or edit one. Asks for the editor's
 *  initials once (kept in this browser). Closes with the rows to save (KorrekturFelder[]; editing:
 *  exactly one), or undefined on cancel. */
@Component({
  selector: 'wlo-korrektur-dialog',
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatIconModule, MatInputModule, MatSelectModule,
            KorrekturHilfeComponent],
  template: `
    <h2 mat-dialog-title>{{ i18n.t(data.neu ? 'korr.dialog.new' : 'korr.dialog.edit') }}</h2>
    <mat-dialog-content class="form">
      <wlo-korrektur-hilfe></wlo-korrektur-hilfe>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.typ') }}</mat-label>
        <mat-select [(ngModel)]="typ" (selectionChange)="typGeaendert()">
          @for (t of typen; track t) { <mat-option [value]="t">{{ t }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.schluessel') }}</mat-label>
        <input matInput [(ngModel)]="schluessel" [placeholder]="typ === 'node' ? 'Node-ID (UUID)' : i18n.t('korr.key.bq')">
      </mat-form-field>
      @for (a of zeilen; track $index; let i = $index) {
        <div class="aktion">
          <div class="aktion-kopf">
            <mat-form-field appearance="outline" subscriptSizing="dynamic" class="grow">
              <mat-label>{{ i18n.t('korr.col.aktion') }}@if (zeilen.length > 1) { {{ i + 1 }}}</mat-label>
              <mat-select [(ngModel)]="a.aktion">
                @for (x of aktionen(); track x) { <mat-option [value]="x">{{ x }}</mat-option> }
              </mat-select>
            </mat-form-field>
            @if (zeilen.length > 1) {
              <button mat-icon-button type="button" (click)="entfernen(i)" [attr.aria-label]="i18n.t('korr.action.remove')"><mat-icon>close</mat-icon></button>
            }
          </div>
          @if (brauchtWert(a.aktion)) {
            <mat-form-field appearance="outline" subscriptSizing="dynamic">
              <mat-label>{{ i18n.t('korr.col.wert') }}</mat-label>
              <textarea matInput [rows]="a.aktion === 'beschreibung' ? 3 : 1" [(ngModel)]="a.wert"></textarea>
            </mat-form-field>
          }
        </div>
      }
      @if (data.neu && naechsteFrei()) {
        <button mat-stroked-button type="button" class="mehr" (click)="hinzufuegen()"><mat-icon>add</mat-icon> {{ i18n.t('korr.action.add') }}</button>
      }
      @if (konflikt(); as kf) { <p class="err" role="alert">{{ i18n.t('korr.conflict.' + kf) }}</p> }
      <mat-form-field appearance="outline" subscriptSizing="dynamic">
        <mat-label>{{ i18n.t('korr.col.kommentar') }}</mat-label>
        <input matInput [(ngModel)]="kommentar">
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
  styles: [`
    .form { display: flex; flex-direction: column; min-width: min(520px, 80vw); gap: 16px; }
    .aktion { display: flex; flex-direction: column; gap: 8px; padding: 12px; border: 1px solid var(--tableSeperatorLineColor); border-radius: 8px; }
    .aktion-kopf { display: flex; align-items: center; gap: 4px; }
    .grow { flex: 1; }
    .mehr { align-self: flex-start; }
    .err { color: var(--warn); margin: 0; }
  `],
})
export class KorrekturDialogComponent {
  readonly i18n = inject(I18n);
  readonly data = inject<KorrekturDialogData>(MAT_DIALOG_DATA);
  private readonly ref = inject(MatDialogRef<KorrekturDialogComponent>);
  private readonly svc = inject(KorrekturenService);
  readonly typen = TYPEN;
  private readonly start = { typ: 'node', schluessel: '', aktion: 'blacklist', wert: '', kommentar: '', ...this.data.korrektur };
  typ = this.start.typ;
  schluessel = this.start.schluessel;
  kommentar = this.start.kommentar;
  zeilen: AktionWert[] = [{ aktion: this.start.aktion, wert: this.start.wert }];
  wer = this.svc.wer();

  aktionen(): string[] { return AKTIONEN_JE_TYP[this.typ] ?? []; }

  /** Blacklist and whitelist need no value; every other action carries one. */
  brauchtWert(aktion: string): boolean { return aktion !== 'blacklist' && aktion !== 'whitelist'; }

  typGeaendert(): void {
    const erlaubt = this.aktionen();
    this.zeilen = this.zeilen.filter(z => erlaubt.includes(z.aktion));
    if (!this.zeilen.length) this.zeilen = [{ aktion: erlaubt[0] ?? '', wert: '' }];
  }

  /** First action that is still free and does not clash (blacklist + whitelist); '' = none left. */
  naechsteFrei(): string {
    const belegt = this.zeilen.map(z => z.aktion);
    return this.aktionen().find(a => !aktionsKonflikt([...belegt, a])) ?? '';
  }

  hinzufuegen(): void {
    const frei = this.naechsteFrei();
    if (frei) this.zeilen = [...this.zeilen, { aktion: frei, wert: '' }];
  }

  entfernen(i: number): void { this.zeilen = this.zeilen.filter((_, j) => j !== i); }

  konflikt(): string { return aktionsKonflikt(this.zeilen.map(z => z.aktion)); }

  gueltig(): boolean {
    return !!this.schluessel.trim() && !!this.wer.trim() && !this.konflikt()
      && this.zeilen.every(z => this.aktionen().includes(z.aktion));
  }

  speichern(): void {
    if (!this.gueltig()) return;
    this.svc.setWer(this.wer);
    const zeilen = this.zeilen.map(z => ({ aktion: z.aktion, wert: this.brauchtWert(z.aktion) ? z.wert : '' }));
    this.ref.close(korrekturZeilen({ typ: this.typ, schluessel: this.schluessel, kommentar: this.kommentar }, zeilen));
  }
}
