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

/** Tile grid (Muster card layout). Presentational: renders `items`, emits `open` with the id.
 * From the Details tier (`selectable`, tier 1+) each tile also carries a multi-select checkbox for Sammel-PDF. */
@Component({
  selector: 'wlo-tiles',
  standalone: true,
  imports: [DecimalPipe, MatCheckboxModule, MatIconModule, MatTooltipModule, QualityRowComponent],
  template: `
    <div class="grid">
      @for (s of items; track s.id) {
        <article class="tile" [class.selected]="selectable && sel.has(s.id)"
          (click)="open.emit(s.id)" (keydown.enter)="open.emit(s.id)" tabindex="0" role="button">
          @if (selectable) {
            <mat-checkbox class="sel" [checked]="sel.has(s.id)" (change)="sel.toggle(s.id)"
              (click)="$event.stopPropagation()" (keydown.enter)="$event.stopPropagation()"
              [attr.aria-label]="i18n.t('select.one')"></mat-checkbox>
          }
          <div class="thumb" [class.placeholder]="!(s.previewUrl || resolvedPreview.get(s.id))">
            @if (s.previewUrl || resolvedPreview.get(s.id); as preview) {
              <img [src]="preview" [alt]="s.name" loading="lazy">
            } @else {
              <mat-icon>public</mat-icon>
            }
            <span class="thumb-count">{{ s.contentCount | number }} {{ i18n.t('unit.content') }}</span>
          </div>
          <div class="body">
            <div class="head">
              <h3 class="name">{{ s.name }}</h3>
              @if (s.oer) {
                <span class="oer-badge" [matTooltip]="i18n.t('tile.oer')"><mat-icon>workspace_premium</mat-icon>OER</span>
              }
              @if (s.familyCount) {
                <span class="family-badge" [matTooltip]="s.familyCount + ' ' + i18n.t('tile.family')"><mat-icon>hub</mat-icon>{{ s.familyCount }}</span>
              }
            </div>
            @if (s.description) { <p class="desc">{{ s.description }}</p> }
            <!-- Reserve space for the 3 meta lines (Inhaltstyp / Fach / Bildungsstufe) so the foot
                 row sits at the same height on every tile, even when some lines are empty. -->
            <div class="metas">
              @if (s.contentTypes.length) {
                <div class="meta"><mat-icon>description</mat-icon><span>{{ s.contentTypes.slice(0, 3).join(', ') }}</span></div>
              }
              @if (s.subjects.length) {
                <div class="meta"><mat-icon>menu_book</mat-icon><span>{{ s.subjects.slice(0, 4).join(', ') }}</span></div>
              }
              @if (s.educationalContext.length) {
                <div class="meta"><mat-icon>school</mat-icon><span>{{ s.educationalContext.slice(0, 4).join(', ') }}</span></div>
              }
            </div>
            <div class="tile-foot">
              <wlo-quality-row [quality]="s.quality"></wlo-quality-row>
              <div class="badges">
                @if (s.fieldActiveCount) {
                  <span class="fp-badge" [matTooltip]="s.fieldActiveCount + ' ' + i18n.t('tile.fieldProfile')">{{ s.fieldActiveCount }} F</span>
                }
                @if (s.bind) {
                  <div class="bind">
                    <span class="bdot" [class.on]="s.bind.node" [matTooltip]="i18n.t('bind.node') + ': ' + (s.bind.node || i18n.t('bind.none'))"><mat-icon>description</mat-icon></span>
                    <span class="bdot" [class.on]="s.bind.bezugsquelle" [matTooltip]="i18n.t('bind.bezugsquelle') + ': ' + (s.bind.bezugsquelle || i18n.t('bind.none'))"><mat-icon>search</mat-icon></span>
                    <span class="bdot" [class.on]="s.bind.spider" [matTooltip]="i18n.t('bind.spider') + ': ' + (s.bind.spider || i18n.t('bind.none'))"><mat-icon>settings</mat-icon></span>
                  </div>
                }
              </div>
            </div>
          </div>
        </article>
      }
    </div>
  `,
  styles: [`
    /* Mobile-first column counts (2 → 3 → 4 → 5). CSS grid keeps every tile the same width and leaves
       empty slots on the last, incomplete row instead of stretching the remaining tiles. */
    .grid { display: grid; gap: 14px; grid-template-columns: repeat(2, 1fr); }
    @media (min-width: 621px)  { .grid { grid-template-columns: repeat(3, 1fr); } }
    @media (min-width: 921px)  { .grid { grid-template-columns: repeat(4, 1fr); } }
    @media (min-width: 1240px) { .grid { grid-template-columns: repeat(5, 1fr); } }
    .tile {
      position: relative;
      display: flex; flex-direction: column; cursor: pointer; text-align: left;
      background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 14px; overflow: hidden;
      transition: transform .16s, box-shadow .16s, border-color .16s;
    }
    .tile:hover { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(0,59,124,.13); border-color: var(--wlo-primary); }
    .tile:focus-visible { outline: 2px solid var(--wlo-primary); outline-offset: 2px; }
    /* Selection ring as an OUTSET box-shadow: it sits outside the border box, so it is neither
       clipped by the tile's overflow:hidden nor covered by the full-bleed thumbnail — a uniform
       ring on all four sides (an inset shadow / inner outline was hidden/clipped up top). */
    .tile.selected { border-color: var(--wlo-primary); box-shadow: 0 0 0 2px var(--wlo-primary); }
    .tile.selected:hover { box-shadow: 0 0 0 2px var(--wlo-primary), 0 10px 26px rgba(0,59,124,.13); }
    /* Multi-select checkbox (tier 1+): overlaid on the preview, on a chip for legibility. */
    .sel { position: absolute; top: 6px; left: 6px; z-index: 2; background: rgba(255,255,255,.92); border-radius: 8px; }

    /* Preview keeps the modal 3:2 ratio of the WLO thumbnails → no awkward cropping */
    .thumb { position: relative; aspect-ratio: 3 / 2; background: #e8eef7; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .thumb.placeholder mat-icon { font-size: 44px; width: 44px; height: 44px; color: #9fb2cd; }
    .thumb-count { position: absolute; bottom: 8px; right: 8px; background: rgba(15,33,58,.82); color: #fff; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px; backdrop-filter: blur(3px); }

    /* flex:1 lets the body fill the tile's stretched height (grid stretches all tiles in a row to
       equal height), so the foot can be pinned to the very bottom on every tile. */
    .body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
    .head { display: flex; align-items: flex-start; gap: 8px; }
    /* Reserve exactly two lines for the title so the description always starts at the same height
       across tiles (uniform cards), regardless of a 1- or 2-line name. */
    .name { flex: 1; font-size: 14px; font-weight: 600; line-height: 1.3; margin: 0; color: var(--wlo-text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; min-height: 2.6em; }
    .oer-badge { flex-shrink: 0; display: inline-flex; align-items: center; gap: 3px; background: #e6f4ea; color: #1a8a4d; font-size: 11px; font-weight: 700; padding: 3px 9px 3px 6px; border-radius: 20px; white-space: nowrap; }
    .oer-badge mat-icon { font-size: 14px; width: 14px; height: 14px; }
    /* Bezugsquelle-family badge (publisher + sub-channels, e.g. YouTube) — count of related sources. */
    .family-badge { flex-shrink: 0; display: inline-flex; align-items: center; gap: 3px; background: #e7eefb; color: #2e5aa8; font-size: 11px; font-weight: 700; padding: 3px 8px 3px 6px; border-radius: 20px; white-space: nowrap; cursor: help; }
    .family-badge mat-icon { font-size: 13px; width: 13px; height: 13px; }
    .desc { font-size: 12.5px; color: var(--wlo-text-muted); margin: 0; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    /* Reserve the height of the three meta lines (Inhaltstyp / Fach / Bildungsstufe) so the foot
       sits at the same height across tiles even when some lines are empty — 3 × 18px + 2 × 6px gap. */
    .metas { display: flex; flex-direction: column; gap: 6px; min-height: 66px; }
    .meta { display: flex; align-items: center; gap: 7px; font-size: 12px; color: #3f5170; min-width: 0; }
    .meta mat-icon { font-size: 17px; width: 17px; height: 17px; color: #8aa0c0; flex-shrink: 0; }
    .meta span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    /* Bottom row: quality pills (left) + Audit source-binding badges (right).
       margin-top:auto pins it to the bottom of the (flex:1) body — uniform across all tiles. */
    .tile-foot { display: flex; align-items: center; gap: 8px; margin-top: auto; padding-top: 2px; }
    .badges { margin-left: auto; display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
    .bind { display: flex; gap: 4px; }
    /* Field-profile badge: active metadata fields from the crawler profile. */
    .fp-badge { display: inline-flex; align-items: center; gap: 3px; background: #e6f4ea; color: #1a8a4d; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 20px; cursor: help; }
    /* Binding badge — same optic as the quality dots: green when present, grey when absent. */
    .bdot { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; cursor: help; background: var(--q-unknown-bg); color: var(--q-unknown-fg); }
    .bdot mat-icon { font-size: 13px; width: 13px; height: 13px; }
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
