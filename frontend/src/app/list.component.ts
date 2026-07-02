import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';

import { SourceCard } from './models';
import { QualityRowComponent } from './quality-row.component';
import { SourcesService } from './sources.service';
import { SelectionService } from './selection.service';
import { backfillPreviews } from './preview-backfill';
import { I18n } from './i18n.service';

/** Source list table (look of the old Quellenliste). Presentational: renders `items`, emits `open`.
 * From the Details tier (`selectable`, tier 1+) a leading checkbox column drives the Sammel-PDF selection. */
@Component({
  selector: 'wlo-list',
  standalone: true,
  imports: [DecimalPipe, MatCheckboxModule, MatIconModule, MatTooltipModule, QualityRowComponent],
  template: `
    <div class="list-wrap">
      <table class="ltable">
        <thead>
          <tr>
            @if (selectable) { <th class="c-sel"></th> }
            <th class="c-thumb"></th>
            <th class="c-name">{{ i18n.t('col.source') }}</th>
            <th class="c-count">{{ i18n.t('col.content') }}</th>
            <th class="c-subj">{{ i18n.t('col.subject') }}</th>
            <th class="c-edu">{{ i18n.t('col.level') }}</th>
            <th class="c-type">{{ i18n.t('col.type') }}</th>
            <th class="c-oer">{{ i18n.t('col.oer') }}</th>
            <th class="c-status">{{ i18n.t('col.status') }}</th>
            <th class="c-qual">{{ i18n.t('col.quality') }}</th>
            <th class="c-go"></th>
          </tr>
        </thead>
        <tbody>
          @for (s of items; track s.id) {
            <tr [class.selected]="selectable && sel.has(s.id)" (click)="open.emit(s.id)">
              @if (selectable) {
                <td class="c-sel" (click)="$event.stopPropagation()">
                  <mat-checkbox [checked]="sel.has(s.id)" (change)="sel.toggle(s.id)"
                    [attr.aria-label]="i18n.t('select.one')"></mat-checkbox>
                </td>
              }
              <td class="c-thumb">
                @if (s.previewUrl || resolvedPreview.get(s.id); as preview) {
                  <img class="lavatar" [src]="preview" [alt]="s.name" loading="lazy">
                } @else {
                  <div class="lavatar init">{{ initial(s) }}</div>
                }
              </td>
              <td class="c-name">
                <div class="lname-row">
                  <span class="lname">{{ s.name }}</span>
                  @if (s.familyCount) {
                    <span class="lfamily" [matTooltip]="s.familyCount + ' ' + i18n.t('tile.family')"><mat-icon>hub</mat-icon>{{ s.familyCount }}</span>
                  }
                </div>
                @if (s.contentTypes.length) { <span class="lsub">{{ s.contentTypes.slice(0, 2).join(' · ') }}</span> }
              </td>
              <td class="c-count">
                <span class="cn">{{ s.contentCount | number }}</span>
                <span class="cl">{{ i18n.t('unit.content') }}</span>
              </td>
              <td class="c-subj">
                @for (x of s.subjects.slice(0, 3); track x) { <span class="tag subj">{{ x }}</span> }
              </td>
              <td class="c-edu">
                @for (x of s.educationalContext.slice(0, 2); track x) { <span class="tag edu">{{ x }}</span> }
              </td>
              <td class="c-type">
                @for (x of s.contentTypes.slice(0, 2); track x) { <span class="tag type">{{ x }}</span> }
              </td>
              <td class="c-oer">
                @if (s.oer) { <span class="tag oer">OER</span> }
              </td>
              <td class="c-status">
                @if (statusCode(s.erschliessungsstatus); as code) {
                  <span class="status-badge" [class.done]="code === '9'"
                    [matTooltip]="s.erschliessungsstatus">{{ code }}</span>
                }
              </td>
              <td class="c-qual">
                <wlo-quality-row [quality]="s.quality"></wlo-quality-row>
              </td>
              <td class="c-go">
                @if (s.url) {
                  <a class="go" [href]="s.url" target="_blank" rel="noopener" [matTooltip]="i18n.t('action.open')" (click)="$event.stopPropagation()">
                    <mat-icon>open_in_new</mat-icon>
                  </a>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
  styles: [`
    .list-wrap { overflow-x: auto; }
    .ltable { width: 100%; border-collapse: collapse; font-size: 13px; background: var(--wlo-card); }
    .ltable thead tr { background: var(--wlo-bg); border-bottom: 2px solid var(--wlo-border); }
    .ltable th { padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; color: var(--wlo-text-muted); text-transform: uppercase; letter-spacing: .04em; white-space: nowrap; }
    .ltable td { padding: 9px 12px; border-bottom: 1px solid #eef2f8; vertical-align: middle; }
    .ltable th, .ltable td { border-right: 1px solid #edf1f7; }
    .ltable th:last-child, .ltable td:last-child { border-right: none; }
    .ltable tbody tr { cursor: pointer; transition: background .12s; }
    .ltable tbody tr:hover td { background: #f4f7ff; }
    .ltable tbody tr.selected td { background: var(--wlo-primary-light); }
    .c-sel { width: 44px; text-align: center; }
    .ltable th.c-count, .ltable td.c-count { text-align: right; }
    .c-thumb { width: 80px; } .c-count { width: 84px; } .c-subj { width: 150px; }
    .c-edu { width: 130px; } .c-type { width: 130px; } .c-oer { width: 50px; } .c-status { width: 56px; text-align: center; } .c-qual { width: 152px; } .c-go { width: 40px; text-align: center; }
    .status-badge { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--wlo-primary-light); color: var(--wlo-primary); font-weight: 700; font-size: 12px; cursor: help; }
    .status-badge.done { background: #e6f4ea; color: #1a8a4d; }
    .lavatar { width: 66px; height: 44px; border-radius: 6px; object-fit: cover; display: block; }
    .lavatar.init { display: flex; align-items: center; justify-content: center; background: #eef2f9; color: var(--wlo-primary); font-weight: 700; font-size: 18px; }
    .lname-row { display: flex; align-items: center; gap: 6px; }
    .lname { font-weight: 600; line-height: 1.3; color: var(--wlo-text); }
    /* Bezugsquelle-family badge (publisher + sub-channels) — count of related sources. */
    .lfamily { flex-shrink: 0; display: inline-flex; align-items: center; gap: 2px; background: #e7eefb; color: #2e5aa8; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 10px; cursor: help; }
    .lfamily mat-icon { font-size: 12px; width: 12px; height: 12px; }
    .lsub { font-size: 11px; color: #8295b0; }
    .c-count .cn { font-weight: 700; color: var(--wlo-primary); display: block; }
    .c-count .cl { font-size: 9px; color: #8295b0; text-transform: uppercase; letter-spacing: .04em; }
    .tag { display: inline-block; font-size: 10px; padding: 2px 8px; border-radius: 20px; margin: 1px; white-space: nowrap; }
    .tag.subj { background: #eaf0f9; color: #003b7c; }
    .tag.edu  { background: #e6f3f1; color: #0b7870; }
    .tag.type { background: #eef2f8; color: #41506b; }
    .tag.oer  { background: #e6f4ea; color: #1a8a4d; font-weight: 700; }
    .go { display: inline-flex; color: #9aabc4; }
    .go:hover { color: var(--wlo-primary); }
    .go mat-icon { font-size: 20px; width: 20px; height: 20px; }
  `],
})
export class ListComponent {
  private readonly api = inject(SourcesService);
  readonly i18n = inject(I18n);
  readonly sel = inject(SelectionService);

  /** When true (tier 1+), render the leading multi-select checkbox column for Sammel-PDF. */
  @Input() selectable = false;

  /** Lazily resolved preview images for node-less rows (see backfillPreviews), keyed by id. */
  readonly resolvedPreview = new Map<string, string>();
  private _items: SourceCard[] = [];

  @Input() set items(value: SourceCard[]) {
    this._items = value;
    backfillPreviews(value, this.api, this.resolvedPreview);
  }
  get items(): SourceCard[] {
    return this._items;
  }

  @Output() open = new EventEmitter<string>();

  /** Fallback avatar letter when a source has no preview image. */
  initial(s: SourceCard): string {
    return (s.name || '?').charAt(0).toUpperCase();
  }

  /** Leading digit of the exact editorial status code (team / tier 2, e.g. "9." → "9"); '' for the
   *  coarse public statement (tier 0/1), so the compact status badge shows only the real code — the
   *  coarse statement itself is shown in the detail dialog. */
  statusCode(status: string): string {
    const s = status ?? '';
    return /^\d/.test(s) ? s.charAt(0) : '';
  }
}
