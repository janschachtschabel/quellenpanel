import { Component, HostBinding, Input } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { BarEntry } from './models';

export interface BarRow {
  label: string;
  value: number;
  color?: string;
  title?: string;
}

/** Map the backend's {value,count} bar entries to rows, optionally with a fixed colour. */
export function barRows(items: BarEntry[] | undefined, color?: string): BarRow[] {
  return (items ?? []).map((e) => ({ label: e.value, value: e.count, color }));
}

/**
 * One reusable bar-list card for the statistics views (full + team). Renders rows on a shared
 * scale — auto-max by default, or a fixed 100 in `percent` mode (for fill-levels where the value
 * is already a percentage). Deliberately dependency-free (CSS bars, no chart library), matching
 * the tier-0 stats view, so the public bundle gains no charting weight.
 */
@Component({
  selector: 'wlo-stat-bars',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <div class="card">
      <div class="card-t">{{ title }}</div>
      @if (hint) { <p class="card-h">{{ hint }}</p> }
      <div class="bars">
        @for (r of rows; track r.label) {
          <div class="bar">
            <span class="b-lbl" [title]="r.title || r.label">{{ r.label }}</span>
            <div class="b-track"><div class="b-fill" [style.width.%]="width(r.value)" [style.background]="r.color || color"></div></div>
            <span class="b-val">{{ percent ? r.value + '%' : (r.value | number) }}</span>
          </div>
        } @empty {
          <div class="b-empty">—</div>
        }
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; }
    .card { background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 10px; overflow: hidden; height: 100%; }
    .card-t { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--wlo-text-muted); padding: 8px 14px; background: var(--wlo-bg); border-bottom: 1px solid var(--wlo-border); }
    .card-h { font-size: 11px; color: var(--wlo-text-muted); margin: 8px 14px 0; line-height: 1.4; }
    .bars { display: flex; flex-direction: column; gap: 5px; padding: 12px 14px; }
    .bar { display: flex; align-items: center; gap: 8px; }
    .b-lbl { width: 150px; font-size: 11px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--wlo-text); }
    .b-track { flex: 1; height: 8px; background: var(--wlo-bg); border-radius: 4px; overflow: hidden; min-width: 40px; }
    .b-fill { height: 100%; border-radius: 4px; transition: width .4s; }
    .b-val { width: 52px; font-size: 10px; text-align: right; color: var(--wlo-text-muted); flex-shrink: 0; }
    .b-empty { font-size: 12px; color: var(--wlo-text-muted); font-style: italic; }
  `],
})
export class StatBarsComponent {
  @Input() title = '';
  @Input() hint = '';
  @Input() rows: BarRow[] = [];
  @Input() percent = false;       // value is already 0–100 → bar width = value, label = "value%"
  @Input() color = '#16a34a';

  /** When set, the card spans two grid columns in the parent statistics grid. */
  @Input() @HostBinding('class.wide') wide = false;

  width(v: number): number {
    const max = this.percent ? 100 : Math.max(1, ...this.rows.map((r) => r.value));
    return Math.round((v / max) * 100);
  }
}
