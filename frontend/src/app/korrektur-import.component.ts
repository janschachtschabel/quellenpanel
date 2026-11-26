import { Component, EventEmitter, Input, Output, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';

import { I18n } from './i18n.service';
import { ImportModus, KorrekturenService } from './korrekturen.service';
import { DateiFormat, formatAusDateiname } from './korrekturen-utils';
import { ImportVorschau, KorrekturFelder, KorrekturStand, Zuordnung } from './models';
import { fehlertext } from './korrekturen-fehler';

const ZIELFELDER = ['typ', 'schluessel', 'aktion', 'wert', 'kommentar'] as const;

/** Import wizard: choose a file (CSV / JSON / XLSX) and a mode, check the column mapping and the
 *  preview (new / changed / faulty / dropped), then apply. Emits the new state after applying. */
@Component({
  selector: 'wlo-korrektur-import',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatButtonToggleModule, MatFormFieldModule, MatIconModule, MatSelectModule],
  template: `
  <div class="step">
    <label class="file">
      <input type="file" accept=".csv,.json,.xlsx" (change)="datei($event)">
    </label>
    <mat-button-toggle-group [(ngModel)]="modus" (change)="vorschauLaden()" [attr.aria-label]="i18n.t('imp.mode')">
      <mat-button-toggle value="ergaenzen">{{ i18n.t('imp.mode.add') }}</mat-button-toggle>
      <mat-button-toggle value="ersetzen">{{ i18n.t('imp.mode.replace') }}</mat-button-toggle>
    </mat-button-toggle-group>
  </div>
  @if (fehler()) { <p class="err" role="alert">{{ fehler() }}</p> }
  @if (vorschau(); as v) {
    <h4>{{ i18n.t('imp.mapping') }}</h4>
    <div class="map">
      @for (f of felder; track f) {
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('korr.col.' + f) }}</mat-label>
          <mat-select [ngModel]="zuordnung[f] ?? ''" (ngModelChange)="zuordnen(f, $event)">
            <mat-option value="">—</mat-option>
            @for (s of v.spalten; track s) { <mat-option [value]="s">{{ s }}</mat-option> }
          </mat-select>
        </mat-form-field>
      }
    </div>
    <p class="sum">
      <b>{{ v.anzahl.neu }}</b> {{ i18n.t('imp.new') }} ·
      <b>{{ v.anzahl.geaendert }}</b> {{ i18n.t('imp.changed') }} ·
      <b>{{ v.anzahl.unveraendert }}</b> {{ i18n.t('imp.same') }} ·
      <b class="err">{{ v.anzahl.fehlerhaft }}</b> {{ i18n.t('imp.faulty') }}
      @if (modus === 'ersetzen') { · <b class="err">{{ v.anzahl.entfallen }}</b> {{ i18n.t('imp.dropped') }} }
    </p>
    @if (v.vorschau.neu.length) { <details><summary>{{ i18n.t('imp.new') }}</summary><ul>@for (k of v.vorschau.neu; track $index) { <li>{{ zeile(k) }}</li> }</ul></details> }
    @if (v.vorschau.geaendert.length) { <details><summary>{{ i18n.t('imp.changed') }}</summary><ul>@for (g of v.vorschau.geaendert; track $index) { <li>{{ zeile(g.alt) }} → {{ zeile(g.neu) }}</li> }</ul></details> }
    @if (v.vorschau.fehlerhaft.length) { <details open><summary>{{ i18n.t('imp.faulty') }}</summary><ul>@for (m of v.vorschau.fehlerhaft; track $index) { <li>{{ i18n.t('korr.line') }} {{ m.zeile }}: {{ m.text }}</li> }</ul></details> }
    @if (v.vorschau.entfallen.length) { <details><summary>{{ i18n.t('imp.dropped') }}</summary><ul>@for (k of v.vorschau.entfallen; track $index) { <li>{{ zeile(k) }}</li> }</ul></details> }
    @if (v.anzahl.neu + v.anzahl.geaendert + v.anzahl.entfallen > 0) {
      <button mat-flat-button color="primary" type="button" [disabled]="busy()" (click)="anwenden()">
        <mat-icon>check</mat-icon> {{ i18n.t('imp.apply') }}
      </button>
    } @else { <p>{{ i18n.t('imp.nothing') }}</p> }
  }
  `,
  styles: [`
    .step { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin: 12px 0; }
    .map { display: flex; flex-wrap: wrap; gap: 8px; }
    .err { color: #b00020; }
    .sum { margin: 8px 0; }
    ul { max-height: 220px; overflow: auto; font-size: 13px; }
  `],
})
export class KorrekturImportComponent {
  @Input() version = '';
  @Output() uebernommen = new EventEmitter<KorrekturStand>();
  /** 409: the corrections changed meanwhile — the parent reloads to get the current version. */
  @Output() konflikt = new EventEmitter<void>();
  readonly i18n = inject(I18n);
  private readonly svc = inject(KorrekturenService);
  readonly felder = ZIELFELDER;
  readonly vorschau = signal<ImportVorschau | null>(null);
  readonly fehler = signal('');
  readonly busy = signal(false);
  modus: ImportModus = 'ergaenzen';
  zuordnung: Zuordnung = {};
  private file: File | null = null;
  private format: DateiFormat | null = null;
  private manuell = false;

  zeile(k: KorrekturFelder): string {
    return [k.typ, k.schluessel, k.aktion, k.wert].filter(x => x).join(' · ');
  }

  datei(ev: Event): void {
    const f = (ev.target as HTMLInputElement).files?.[0] ?? null;
    this.vorschau.set(null);
    this.fehler.set('');
    this.manuell = false;
    this.zuordnung = {};
    this.file = f;
    this.format = f ? formatAusDateiname(f.name) : null;
    if (f && !this.format) { this.fehler.set(this.i18n.t('imp.format')); return; }
    this.vorschauLaden();
  }

  zuordnen(feld: string, spalte: string): void {
    this.zuordnung = { ...this.zuordnung, [feld]: spalte || null };
    this.manuell = true;
    this.vorschauLaden();
  }

  vorschauLaden(): void {
    if (!this.file || !this.format) return;
    this.svc.importVorschau(this.file, this.format, this.modus, this.manuell ? this.zuordnung : null).subscribe({
      next: v => { this.vorschau.set(v); this.zuordnung = { ...v.zuordnung }; this.fehler.set(''); },
      error: e => { this.vorschau.set(null); this.fehler.set(fehlertext(e)); },
    });
  }

  anwenden(): void {
    if (!this.file || !this.format) return;
    if (!this.svc.wer()) { this.fehler.set(this.i18n.t('korr.wer.missing')); return; }
    if (this.modus === 'ersetzen' && !confirm(this.i18n.t('imp.replace.confirm'))) return;
    this.busy.set(true);
    this.svc.importieren(this.file, this.format, this.modus, this.manuell ? this.zuordnung : null, this.version).subscribe({
      next: s => { this.busy.set(false); this.vorschau.set(null); this.uebernommen.emit(s); },
      error: e => {
        this.busy.set(false);
        this.fehler.set(fehlertext(e));
        if ((e as { status?: number })?.status === 409) this.konflikt.emit();
      },
    });
  }
}
