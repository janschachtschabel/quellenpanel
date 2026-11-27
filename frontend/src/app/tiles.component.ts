import { Component, EventEmitter, Input, Output, inject, ChangeDetectionStrategy } from '@angular/core';
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

/** Tile grid (Muster card layout). Presentational: renders `items`, emits `open` with the id.
 * From the Details tier (`selectable`, tier 1+) each tile also carries a multi-select checkbox for Sammel-PDF. */
@Component({
  selector: 'wlo-tiles',
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [DecimalPipe, MatCheckboxModule, MatIconModule, MatTooltipModule, QualityRowComponent],
  template: `
    <div class="grid">
      @for (s of items; track s.id) {
        <article class="tile" [class.selected]="selectable && sel.has(s.id)">
          <!-- 1 header bar (edu-sharing card anatomy): type badge, OER / family, checkbox far right -->
          <div class="top">
            <span class="type-badge" [matTooltip]="i18n.t('tile.type')"><mat-icon aria-hidden="true">public</mat-icon></span>
            @if (s.oer) {
              <span class="pill oer" [matTooltip]="i18n.t('tile.oer')"><mat-icon aria-hidden="true">workspace_premium</mat-icon>OER</span>
            }
            @if (s.familyCount) {
              <span class="pill family" [matTooltip]="s.familyCount + ' ' + i18n.t('tile.family')"><mat-icon aria-hidden="true">hub</mat-icon>{{ s.familyCount }}</span>
            }
            @if (selectable) {
              <mat-checkbox class="sel" [checked]="sel.has(s.id)" (change)="sel.toggle(s.id)"
                [aria-label]="i18n.t('select.one') + ': ' + s.name"></mat-checkbox>
            }
          </div>
          <!-- 2–4 click target: the button holds title + preview (accessible name = title, count);
               its ::after stretches over description and metadata so the whole card body opens. -->
          <h3 class="h"><button type="button" class="open" (click)="open.emit(s.id)">
            <span class="name">{{ s.name }}</span>
            <span class="thumb" [class.placeholder]="!(s.previewUrl || resolvedPreview.get(s.id))">
              @if (s.previewUrl || resolvedPreview.get(s.id); as preview) {
                <img class="blur" [src]="preview" alt="" loading="lazy">
                <img class="pic" [src]="preview" alt="" loading="lazy">
              } @else {
                <mat-icon aria-hidden="true">public</mat-icon>
              }
              <span class="count">{{ s.contentCount | number }} {{ i18n.t('unit.content') }}</span>
            </span>
          </button></h3>
          <div class="meta-area">
            @if (s.description) { <p class="desc">{{ s.description }}</p> }
            <!-- Metadata as icon lines (as before the redesign): icon + values, left-aligned, one line
                 each; the label stays for screen readers. Empty lines are left out,
                 the block keeps the height of three lines so the option bar lines up. -->
            <dl class="rows">
              @if (s.contentTypes.length) {
                <div class="row"><dt class="label"><mat-icon aria-hidden="true">description</mat-icon><span class="sr">{{ i18n.t('filter.lrt') }}</span></dt><dd class="value">{{ s.contentTypes.slice(0, 3).join(', ') }}</dd></div>
              }
              @if (s.subjects.length) {
                <div class="row"><dt class="label"><mat-icon aria-hidden="true">menu_book</mat-icon><span class="sr">{{ i18n.t('filter.subject') }}</span></dt><dd class="value">{{ s.subjects.slice(0, 4).join(', ') }}</dd></div>
              }
              @if (s.educationalContext.length) {
                <div class="row"><dt class="label"><mat-icon aria-hidden="true">school</mat-icon><span class="sr">{{ i18n.t('filter.level') }}</span></dt><dd class="value">{{ s.educationalContext.slice(0, 4).join(', ') }}</dd></div>
              }
            </dl>
          </div>
          <!-- 5 option bar: quality (left), field profile and source bindings (right) -->
          <div class="foot">
            <wlo-quality-row [quality]="s.quality"></wlo-quality-row>
            <div class="badges">
              @if (s.fieldActiveCount) {
                <span class="pill ok" [matTooltip]="s.fieldActiveCount + ' ' + i18n.t('tile.fieldProfile')">{{ s.fieldActiveCount }} F</span>
              }
              @if (s.bind) {
                <div class="bind">
                  <span class="bdot" [class.on]="s.bind.node" [matTooltip]="i18n.t('bind.node') + ': ' + (s.bind.node || i18n.t('bind.none'))"><mat-icon aria-hidden="true">description</mat-icon></span>
                  <span class="bdot" [class.on]="s.bind.bezugsquelle" [matTooltip]="i18n.t('bind.bezugsquelle') + ': ' + (s.bind.bezugsquelle || i18n.t('bind.none'))"><mat-icon aria-hidden="true">search</mat-icon></span>
                  <span class="bdot" [class.on]="s.bind.spider" [matTooltip]="i18n.t('bind.spider') + ': ' + (s.bind.spider || i18n.t('bind.none'))"><mat-icon aria-hidden="true">settings</mat-icon></span>
                </div>
              }
            </div>
          </div>
        </article>
      }
    </div>
  `,
  styles: [`
    /* Column counts stay tied to the page size (grid-columns.ts: 2 → 3 → 4 → 5); gap 20px as in
       the edu-sharing card grid. Tiles stretch to equal height per row. */
    .grid { display: grid; gap: 20px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    @media (min-width: 621px)  { .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
    @media (min-width: 921px)  { .grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
    @media (min-width: 1240px) { .grid { grid-template-columns: repeat(5, minmax(0, 1fr)); } }
    @media (max-width: 480px)  { .grid { grid-template-columns: minmax(0, 1fr); } }

    /* edu-sharing Grid card: no radius, bottom shadow, elevated background (node-entries-anatomy §1). */
    .tile {
      position: relative; display: flex; flex-direction: column; min-width: 0;
      background: var(--backgroundElevatedColor); box-shadow: var(--shadowBottom);
      transition: box-shadow var(--transitionNormal), background var(--transitionNormal);
    }
    .tile:hover { box-shadow: var(--shadowMedium); background: var(--primaryBackground50); }
    .tile.selected { background: var(--primaryBackground50); }

    .top {
      height: 40px; display: flex; align-items: center; gap: 10px; padding: 0 15px;
      background: color-mix(in srgb, var(--primary) 20%, var(--textWhite));
    }
    .type-badge {
      display: inline-flex; padding: 5px; border-radius: 50%; background: var(--backgroundColor);
      box-shadow: var(--shadowSmall); color: var(--primaryForeground800); margin-right: auto;
    }
    .type-badge mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .pill {
      display: inline-flex; align-items: center; gap: 5px; padding: 2px 10px 2px 5px; font-size: 12px; font-weight: 600;
      border-radius: var(--borderRadiusBadges); white-space: nowrap; background: var(--defaultBackground); color: var(--primaryForeground800);
    }
    .pill mat-icon { font-size: 14px; width: 14px; height: 14px; }
    .pill.oer, .pill.ok { background: var(--colorStatusPositiveBackground); color: var(--colorStatusPositiveText); }
    .pill.ok { padding: 2px 10px; }
    .pill.family { cursor: help; }
    .sel { margin-right: -10px; }

    .h { margin: 0; font: inherit; }
    .open {
      all: unset; box-sizing: border-box; display: flex; flex-direction: column; cursor: pointer; min-width: 0;
      width: 100%;   /* a button shrinks to its content: without this narrow previews sat off-centre */
      font: inherit; color: var(--textMain); text-align: left;
    }
    /* Stretched click area: from below the header bar to above the option bar. */
    .open::after { content: ''; position: absolute; inset: 40px 0 40px 0; }
    .open:focus-visible { outline: none; }
    .open:focus-visible .name { outline: 2px solid var(--focusColor); outline-offset: 2px; }
    .top, .foot { position: relative; z-index: 1; }

    .thumb {
      position: relative; height: 150px; display: flex; align-items: center; justify-content: center; overflow: hidden;
      background: var(--primaryBackground50);
    }
    .thumb .blur { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: blur(15px); transform: scale(1.15); opacity: .7; }
    .thumb .pic { position: relative; max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
    .thumb.placeholder mat-icon { font-size: 40px; width: 40px; height: 40px; color: var(--textMediumLight); }
    .count {
      position: absolute; bottom: 10px; right: 10px; background: var(--overlayDark); color: var(--textWhite);
      font-size: 12px; font-weight: 600; padding: 2px 10px; border-radius: var(--borderRadiusBadges);
    }

    .thumb { order: -1; }
    .open .name { margin: 10px 15px 0; }
    .meta-area { display: flex; flex-direction: column; gap: 5px; padding: 5px 15px 10px; flex: 1; min-width: 0; }
    .desc { margin: 0; }
    .rows { margin: 0; }
    .row dt { margin: 0; }
    .row dd { margin: 0; }
    /* Title: left-aligned, at most two lines (limitLineCount(2, 1.4)), space for two lines reserved. */
    .name {
      font-size: 16px; font-weight: 600; line-height: 1.4; min-height: 2.8em; color: var(--textMain);
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere;
    }
    .desc {
      font-size: 13px; line-height: 1.4; color: var(--textLight);
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    /* Metadata lines: icon + values, left-aligned, one line each; room for three lines reserved. */
    .rows { display: flex; flex-direction: column; gap: 6px; margin-top: auto; padding-top: 6px; min-height: calc(3 * 20px + 2 * 6px); }
    .row { display: flex; align-items: center; gap: 8px; min-height: 20px; font-size: 13px; min-width: 0; }
    .label { flex-shrink: 0; display: inline-flex; color: var(--textMediumLight); }
    .label mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .value { color: var(--textMain); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
    .sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0; }

    .foot {
      display: flex; align-items: center; gap: 10px; min-height: 40px; padding: 0 15px;
      border-top: 1px solid var(--tableSeperatorLineColor);
    }
    .badges { margin-left: auto; display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
    .bind { display: flex; gap: 5px; }
    .bdot { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; cursor: help; background: var(--q-unknown-bg); color: var(--q-unknown-fg); }
    .bdot mat-icon { font-size: 14px; width: 14px; height: 14px; }
    .bdot.on { background: var(--q-good-bg); color: var(--q-good-fg); }
  `],
})
export class TilesComponent {
  private readonly api = inject(SourcesService);
  readonly i18n = inject(I18n);
  readonly sel = inject(SelectionService);

  @Input() selectable = false;

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
}
