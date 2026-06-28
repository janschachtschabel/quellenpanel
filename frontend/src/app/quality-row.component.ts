import { Component, Input, inject } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { COMPACT_KEYS, QualityEntry, qualityEntries } from './quality';
import { I18n } from './i18n.service';

/**
 * Compact, colour-coded quality icons (cost, ads, login, data protection …) shown on tiles
 * and in list rows. Shared so the markup + styles live in one place (not duplicated per view).
 * `display: contents` lets the host vanish from layout, so an empty quality dict adds no gap.
 */
@Component({
  selector: 'wlo-quality-row',
  standalone: true,
  imports: [MatIconModule, MatTooltipModule],
  template: `
    @if (entries.length) {
      <div class="qrow">
        @for (e of entries; track e.key) {
          <span class="qdot" [class]="'q-' + e.level" [matTooltip]="i18n.t(e.labelKey) + ': ' + i18n.tValue(e.value)"><mat-icon>{{ e.icon }}</mat-icon></span>
        }
      </div>
    }
  `,
  styles: [`
    :host { display: contents; }
    .qrow { display: flex; flex-wrap: wrap; gap: 4px; }
    .qdot { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; cursor: help; flex-shrink: 0; }
    .qdot mat-icon { font-size: 13px; width: 13px; height: 13px; }
    .q-good { background: var(--q-good-bg); color: var(--q-good-fg); }
    .q-neutral { background: var(--q-neutral-bg); color: var(--q-neutral-fg); }
    .q-bad { background: var(--q-bad-bg); color: var(--q-bad-fg); }
    .q-unknown { background: var(--q-unknown-bg); color: var(--q-unknown-fg); }
  `],
})
export class QualityRowComponent {
  readonly i18n = inject(I18n);
  entries: QualityEntry[] = [];

  @Input() set quality(q: Record<string, string> | undefined) {
    this.entries = qualityEntries(q, COMPACT_KEYS);
  }
}
