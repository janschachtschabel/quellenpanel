import { Component, Input, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Stats } from './models';
import { I18n } from './i18n.service';

/**
 * Public statistics view (Kachel/Liste/Statistiken). Mirrors the lanes of the old
 * Quellenliste statistics tab, but only the end-user-safe ones — no data-quality /
 * legal / accessibility donuts (those are team-internal). Pure presentational: the
 * parent fetches the Stats and passes them in.
 */
@Component({
  selector: 'wlo-stats',
  standalone: true,
  imports: [DecimalPipe],
  template: `
  @if (!stats) {
    <div class="loading">{{ i18n.t('stats.loading') }}</div>
  } @else {
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-val">{{ stats.total | number }}</div><div class="kpi-lbl">{{ i18n.t('stats.kpi.sources') }}</div></div>
      <div class="kpi"><div class="kpi-val">{{ stats.totalContents | number }}</div><div class="kpi-lbl">{{ i18n.t('stats.kpi.content') }}</div></div>
      <div class="kpi"><div class="kpi-val">{{ stats.withQuelldatensatz | number }}</div><div class="kpi-lbl">{{ i18n.t('stats.kpi.withNode') }}</div></div>
      <div class="kpi accent"><div class="kpi-val">{{ stats.oer.percent | number:'1.0-1' }}%</div><div class="kpi-lbl">{{ i18n.t('stats.kpi.oer') }}</div></div>
      <div class="kpi"><div class="kpi-val">{{ stats.crawlerCount | number }}</div><div class="kpi-lbl">{{ i18n.t('stats.kpi.crawler') }}</div></div>
    </div>

    <div class="lane">
      <div class="lane-lbl">{{ i18n.t('stats.lane.dist') }}</div>
      <div class="lane-row">
        <div class="chart grow2">
          <div class="chart-title">{{ i18n.t('stats.chart.topSources') }}</div>
          <div class="bars">
            @for (e of stats.topByContent.slice(0, 15); track e.value) {
              <div class="bar">
                <span class="b-lbl">{{ e.value }}</span>
                <div class="b-track"><div class="b-fill" [style.width.%]="pct(e.count, stats.topByContent[0]?.count ?? 1)"></div></div>
                <span class="b-val">{{ e.count | number }}</span>
              </div>
            }
          </div>
        </div>
        <div class="chart grow1">
          <div class="chart-title">{{ i18n.t('stats.chart.languages') }}</div>
          <div class="bars">
            @for (e of stats.topLanguages; track e.value) {
              <div class="bar">
                <span class="b-lbl">{{ e.value }}</span>
                <div class="b-track"><div class="b-fill" [style.width.%]="pct(e.count, stats.topLanguages[0]?.count ?? 1)"></div></div>
                <span class="b-val">{{ e.count | number }}</span>
              </div>
            }
          </div>
        </div>
      </div>
    </div>

    <div class="lane">
      <div class="lane-lbl">{{ i18n.t('stats.lane.topics') }}</div>
      <div class="lane-row">
        <div class="chart grow2">
          <div class="chart-title">{{ i18n.t('stats.chart.subjects') }}</div>
          <div class="bars">
            @for (e of stats.topSubjects.slice(0, 15); track e.value) {
              <div class="bar">
                <span class="b-lbl">{{ e.value }}</span>
                <div class="b-track"><div class="b-fill" [style.width.%]="pct(e.count, stats.topSubjects[0]?.count ?? 1)"></div></div>
                <span class="b-val">{{ e.count | number }}</span>
              </div>
            }
          </div>
        </div>
        <div class="chart grow1">
          <div class="chart-title">{{ i18n.t('stats.chart.levels') }}</div>
          <div class="bars">
            @for (e of stats.topLevels.slice(0, 10); track e.value) {
              <div class="bar">
                <span class="b-lbl">{{ e.value }}</span>
                <div class="b-track"><div class="b-fill" [style.width.%]="pct(e.count, stats.topLevels[0]?.count ?? 1)"></div></div>
                <span class="b-val">{{ e.count | number }}</span>
              </div>
            }
          </div>
        </div>
      </div>
    </div>

    <div class="lane">
      <div class="lane-lbl">{{ i18n.t('stats.lane.openness') }}</div>
      <div class="lane-row">
        <div class="chart grow2">
          <div class="chart-title">{{ i18n.t('stats.chart.licenses') }}</div>
          <div class="bars">
            @for (e of stats.licenseDistribution.slice(0, 12); track e.value) {
              <div class="bar">
                <span class="b-lbl">{{ e.value }}</span>
                <div class="b-track"><div class="b-fill" [style.width.%]="pct(e.count, stats.licenseDistribution[0]?.count ?? 1)"></div></div>
                <span class="b-val">{{ e.count | number }}</span>
              </div>
            }
          </div>
        </div>
        <div class="chart grow1 center">
          <div class="chart-title">{{ i18n.t('stats.chart.oer') }}</div>
          <div class="donut-wrap">
            <svg class="donut" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="46" fill="none" stroke="var(--wlo-border)" stroke-width="14"/>
              <circle cx="60" cy="60" r="46" fill="none" stroke="#16a34a" stroke-width="14"
                [attr.stroke-dasharray]="oerDash(stats.oer.percent)" transform="rotate(-90 60 60)"/>
            </svg>
            <div class="donut-lbl">
              <span class="d-pct">{{ stats.oer.percent | number:'1.0-1' }}%</span>
              <span class="d-sub">{{ stats.oer.count | number }} OER</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  }
  `,
  styles: [`
    :host { display: block; padding: 16px; }
    .loading { text-align: center; padding: 48px; color: var(--wlo-text-muted); }
    .kpi-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
    .kpi { flex: 1; min-width: 120px; background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 12px; padding: 16px; text-align: center; }
    .kpi.accent { background: var(--wlo-primary-light); border-color: transparent; }
    .kpi-val { font-size: 24px; font-weight: 700; color: var(--wlo-primary); }
    .kpi-lbl { font-size: 12px; color: var(--wlo-text-muted); margin-top: 4px; }
    .lane { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
    .lane-lbl { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--wlo-text-muted); }
    .lane-row { display: flex; gap: 12px; flex-wrap: wrap; }
    .chart { flex: 1; min-width: 260px; background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 10px; overflow: hidden; }
    .chart.grow2 { flex: 2; } .chart.grow1 { flex: 1; }
    .chart.center { display: flex; flex-direction: column; align-items: center; }
    .chart-title { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--wlo-text-muted); padding: 8px 16px; background: var(--wlo-bg); border-bottom: 1px solid var(--wlo-border); align-self: stretch; }
    .bars { display: flex; flex-direction: column; gap: 5px; padding: 14px 16px; }
    .bar { display: flex; align-items: center; gap: 8px; }
    .b-lbl { width: 120px; font-size: 11px; flex-shrink: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--wlo-text); }
    .b-lbl.mono { width: 64px; font-family: ui-monospace, monospace; font-size: 10px; }
    .b-track { flex: 1; height: 8px; background: var(--wlo-bg); border-radius: 4px; overflow: hidden; }
    .b-fill { height: 100%; border-radius: 4px; background: #16a34a; transition: width .4s; }
    .b-val { width: 48px; font-size: 10px; text-align: right; color: var(--wlo-text-muted); flex-shrink: 0; }
    .donut-wrap { position: relative; display: flex; align-items: center; justify-content: center; padding: 16px; }
    .donut { width: 120px; height: 120px; }
    .donut-lbl { position: absolute; display: flex; flex-direction: column; align-items: center; }
    .d-pct { font-size: 20px; font-weight: 700; color: var(--wlo-text); }
    .d-sub { font-size: 11px; color: var(--wlo-text-muted); }
  `],
})
export class StatsComponent {
  readonly i18n = inject(I18n);
  @Input() stats: Stats | null = null;

  pct(val: number, max: number): number {
    return max ? Math.round((val / max) * 100) : 0;
  }

  oerDash(percent: number): string {
    const circ = 2 * Math.PI * 46;
    return `${(percent / 100) * circ} ${circ}`;
  }
}
