import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSelectModule } from '@angular/material/select';
import { MatTabsModule } from '@angular/material/tabs';

import { I18n } from './i18n.service';
import { KorrekturDialogComponent } from './korrektur-dialog.component';
import { KorrekturenService } from './korrekturen.service';
import { AKTIONEN_JE_TYP, TYPEN, filterKorrekturen } from './korrekturen-utils';
import { Anwenden, Korrektur, KorrekturFelder, KorrekturStand, VerlaufEintrag } from './models';

/** Message of an API error in the service's error shape ({error, message, …}). */
export function fehlertext(e: unknown): string {
  const err = e as HttpErrorResponse;
  return (err?.error && typeof err.error === 'object' && err.error.message) || err?.message || String(e);
}

/**
 * Team area "Korrekturen" (tier 2): the corrections table with search/filter, create / edit / delete,
 * CSV export and the change history. Every save recomputes the data on the server; the answer says
 * whether it is effective now or at the next data build.
 */
@Component({
  selector: 'wlo-korrekturen',
  standalone: true,
  imports: [FormsModule, MatButtonModule, MatDialogModule, MatFormFieldModule, MatIconModule, MatInputModule,
            MatPaginatorModule, MatSelectModule, MatTabsModule],
  template: `
  <div class="tier-head team">🔒 {{ i18n.t('korr.title') }}</div>
  <mat-tab-group animationDuration="0ms" (selectedIndexChange)="tab($event)">
    <mat-tab [label]="i18n.t('korr.tab.list')">
      <div class="bar">
        <mat-form-field appearance="outline" class="q">
          <mat-label>{{ i18n.t('korr.search') }}</mat-label>
          <input matInput [(ngModel)]="q" (ngModelChange)="seite = 0">
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('korr.col.typ') }}</mat-label>
          <mat-select [(ngModel)]="typ" (selectionChange)="seite = 0">
            <mat-option value="">{{ i18n.t('korr.all') }}</mat-option>
            @for (t of typen; track t) { <mat-option [value]="t">{{ t }}</mat-option> }
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>{{ i18n.t('korr.col.aktion') }}</mat-label>
          <mat-select [(ngModel)]="aktion" (selectionChange)="seite = 0">
            <mat-option value="">{{ i18n.t('korr.all') }}</mat-option>
            @for (a of alleAktionen; track a) { <mat-option [value]="a">{{ a }}</mat-option> }
          </mat-select>
        </mat-form-field>
        <span class="spacer"></span>
        <button mat-flat-button color="primary" type="button" (click)="neu()"><mat-icon>add</mat-icon> {{ i18n.t('korr.new') }}</button>
        <a mat-stroked-button [href]="svc.exportUrl()" download="korrekturen.csv"><mat-icon>download</mat-icon> {{ i18n.t('korr.export') }}</a>
      </div>

      @if (meldung()) { <p class="info" role="status">{{ meldung() }}</p> }
      @if (fehler()) { <p class="err" role="alert">{{ fehler() }}</p> }
      @if (stand(); as s) {
        @if (s.fehler.length || s.warnungen.length) {
          <details class="probleme">
            <summary>{{ s.fehler.length }} {{ i18n.t('korr.rowErrors') }}, {{ s.warnungen.length }} {{ i18n.t('korr.rowWarnings') }}</summary>
            <ul>
              @for (m of s.fehler; track $index) { <li class="err">{{ i18n.t('korr.line') }} {{ m.zeile }}: {{ m.text }}</li> }
              @for (m of s.warnungen; track $index) { <li>{{ i18n.t('korr.line') }} {{ m.zeile }}: {{ m.text }}</li> }
            </ul>
          </details>
        }
        <p class="count">{{ gefiltert().length }} / {{ s.eintraege.length }} {{ i18n.t('korr.rows') }}</p>
        <div class="tablewrap">
          <table class="korr">
            <thead><tr>
              <th>{{ i18n.t('korr.col.typ') }}</th><th>{{ i18n.t('korr.col.schluessel') }}</th>
              <th>{{ i18n.t('korr.col.aktion') }}</th><th>{{ i18n.t('korr.col.wert') }}</th>
              <th>{{ i18n.t('korr.col.kommentar') }}</th><th>{{ i18n.t('korr.col.wer') }}</th><th></th>
            </tr></thead>
            <tbody>
              @for (k of seiteZeilen(); track k.id) {
                <tr>
                  <td>{{ k.typ }}</td><td class="mono">{{ k.schluessel }}</td><td>{{ k.aktion }}</td>
                  <td class="clip" [title]="k.wert">{{ k.wert }}</td><td class="clip" [title]="k.kommentar">{{ k.kommentar }}</td>
                  <td>{{ k.geaendert_von }}<br><small>{{ k.geaendert_am }}</small></td>
                  <td class="act">
                    <button mat-icon-button type="button" (click)="bearbeiten(k)" [attr.aria-label]="i18n.t('korr.edit')"><mat-icon>edit</mat-icon></button>
                    <button mat-icon-button type="button" (click)="loeschen(k)" [attr.aria-label]="i18n.t('korr.delete')"><mat-icon>delete</mat-icon></button>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <mat-paginator [length]="gefiltert().length" [pageIndex]="seite" [pageSize]="groesse"
          [pageSizeOptions]="[25, 50, 100, 250]" (page)="blaettern($event)"></mat-paginator>
      }
    </mat-tab>
    <mat-tab [label]="i18n.t('korr.tab.history')">
      <div class="tablewrap">
        <table class="korr">
          <thead><tr><th>{{ i18n.t('korr.h.when') }}</th><th>{{ i18n.t('korr.col.wer') }}</th><th>{{ i18n.t('korr.h.what') }}</th>
            <th>{{ i18n.t('korr.h.old') }}</th><th>{{ i18n.t('korr.h.new') }}</th></tr></thead>
          <tbody>
            @for (v of verlauf(); track $index) {
              <tr><td>{{ v.zeitpunkt }}</td><td>{{ v.wer }}</td><td>{{ v.vorgang }}</td>
                <td class="clip mono" [title]="v.alt">{{ v.alt }}</td><td class="clip mono" [title]="v.neu">{{ v.neu }}</td></tr>
            } @empty { <tr><td colspan="5">{{ i18n.t('korr.h.empty') }}</td></tr> }
          </tbody>
        </table>
      </div>
    </mat-tab>
  </mat-tab-group>
  `,
  styles: [`
    .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 12px; }
    .bar .q { flex: 1 1 260px; }
    .spacer { flex: 1; }
    .tablewrap { overflow-x: auto; }
    table.korr { width: 100%; border-collapse: collapse; font-size: 13px; }
    table.korr th, table.korr td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e3e6ec; vertical-align: top; }
    table.korr th { font-weight: 600; background: #f5f7fa; position: sticky; top: 0; }
    .mono { font-family: ui-monospace, monospace; font-size: 12px; word-break: break-all; }
    .clip { max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .act { white-space: nowrap; }
    .count { color: #555; margin: 4px 0; }
    .info { background: #e8f1fb; padding: 8px 12px; border-radius: 6px; }
    .err { color: #b00020; }
    .probleme { margin: 8px 0; }
  `],
})
export class KorrekturenComponent implements OnInit {
  readonly i18n = inject(I18n);
  readonly svc = inject(KorrekturenService);
  private readonly dialog = inject(MatDialog);

  readonly typen = TYPEN;
  readonly alleAktionen = [...new Set(Object.values(AKTIONEN_JE_TYP).flat())];
  readonly stand = signal<KorrekturStand | null>(null);
  readonly verlauf = signal<VerlaufEintrag[]>([]);
  readonly meldung = signal('');
  readonly fehler = signal('');
  q = '';
  typ = '';
  aktion = '';
  seite = 0;
  groesse = 50;

  ngOnInit(): void { this.laden(); }

  laden(): void {
    this.svc.lesen().subscribe({ next: s => this.stand.set(s), error: e => this.fehler.set(fehlertext(e)) });
  }

  tab(i: number): void {
    if (i === 1) this.svc.verlauf().subscribe({ next: v => this.verlauf.set(v), error: e => this.fehler.set(fehlertext(e)) });
  }

  gefiltert(): Korrektur[] {
    return filterKorrekturen(this.stand()?.eintraege ?? [], this.q, this.typ, this.aktion);
  }

  seiteZeilen(): Korrektur[] {
    return this.gefiltert().slice(this.seite * this.groesse, (this.seite + 1) * this.groesse);
  }

  blaettern(e: PageEvent): void { this.seite = e.pageIndex; this.groesse = e.pageSize; }

  /** Show the server's answer of a save: new state + whether it is effective now. */
  uebernehmen(s: KorrekturStand): void {
    this.stand.set(s);
    this.fehler.set('');
    this.meldung.set(this.anwendenText(s.anwenden));
  }

  anwendenText(a?: Anwenden): string {
    if (!a) return '';
    return this.i18n.t(a.wirktBeimNaechstenAufbau ? 'korr.applied.later' : 'korr.applied.now');
  }

  fehlerAnzeigen(e: unknown): void {
    this.meldung.set('');
    this.fehler.set(fehlertext(e));
    if ((e as HttpErrorResponse)?.status === 409) this.laden();
  }

  neu(vorlage?: Partial<KorrekturFelder>): void {
    this.dialog.open(KorrekturDialogComponent, { data: { neu: true, korrektur: vorlage }, autoFocus: false })
      .afterClosed().subscribe((k?: KorrekturFelder) => {
        if (!k) return;
        this.svc.anlegen(k, this.stand()?.version ?? '').subscribe({ next: s => this.uebernehmen(s), error: e => this.fehlerAnzeigen(e) });
      });
  }

  bearbeiten(alt: Korrektur): void {
    this.dialog.open(KorrekturDialogComponent, { data: { neu: false, korrektur: alt }, autoFocus: false })
      .afterClosed().subscribe((k?: KorrekturFelder) => {
        if (!k) return;
        this.svc.aendern(alt.id, k, this.stand()?.version ?? '').subscribe({ next: s => this.uebernehmen(s), error: e => this.fehlerAnzeigen(e) });
      });
  }

  loeschen(k: Korrektur): void {
    if (!this.svc.wer()) { this.fehler.set(this.i18n.t('korr.wer.missing')); return; }
    if (!confirm(`${this.i18n.t('korr.delete.confirm')}\n${k.typ} · ${k.schluessel} · ${k.aktion}`)) return;
    this.svc.loeschen(k.id, this.stand()?.version ?? '').subscribe({ next: s => this.uebernehmen(s), error: e => this.fehlerAnzeigen(e) });
  }
}
