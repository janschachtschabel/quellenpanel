import { Component, Input, inject } from '@angular/core';
import { BarEntry, FullStats } from './models';
import { BarRow, StatBarsComponent, barRows } from './stat-bars.component';
import { I18n } from './i18n.service';

/**
 * Extended statistics ADDED at tier 1+ ("Details" / "Audit"), shown as swimlanes BENEATH the base
 * end-user stats — never replacing them. Deliberately omits what the base already shows (KPIs, top
 * sources / subjects / levels / licences / languages) and contributes the deeper cuts: source
 * management, content coverage, content-volume brackets, descriptive-metadata fill (over the
 * Quelldatensätze) and crawler method / type.
 *
 * Optics match the base view exactly: each lane is a flex row whose cards grow to fill the width
 * (flex:1, the wide card flex:2), same green bars, no chart library.
 */
@Component({
  selector: 'wlo-full-stats',
  standalone: true,
  imports: [StatBarsComponent],
  template: `
  @if (stats; as s) {
    <div class="tier-head">{{ i18n.t('stats.tier1.title') }}</div>

    <div class="sec">{{ i18n.t('stats.sec.origin') }}</div>
    <div class="grid">
      <wlo-stat-bars [wide]="true" [title]="i18n.t('stats.card.quellenverwaltung')" [rows]="qvRows()" [hint]="i18n.t('stats.qv.hint')"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.coverage')" [rows]="coverageRows()" [hint]="i18n.t('stats.cov.hint')"></wlo-stat-bars>
    </div>

    <div class="sec">{{ i18n.t('stats.sec.brackets') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.brktNode')" [rows]="rows(s.contentBracketsNode)"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.bqSize')" [rows]="rows(s.bqSizeBrackets)"></wlo-stat-bars>
    </div>

    <div class="sec">{{ i18n.t('stats.sec.crawler') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.fillContent')" [rows]="beschRows(s.beschreibendeFelder.inhalt)"
        [percent]="true" [hint]="fillHint(s.beschreibendeFelder.basis)"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.fillClass')" [rows]="beschRows(s.beschreibendeFelder.einordnung)"
        [percent]="true" [hint]="fillHint(s.beschreibendeFelder.basis)"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.method')" [rows]="rows(s.fieldGeneration.byMethod)"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.crawlerType')" [rows]="rows(s.crawlerByType)"></wlo-stat-bars>
    </div>
  }
  `,
  styles: [`
    :host { display: block; padding: 0 16px 8px; }
    .tier-head { font-size: 13px; font-weight: 700; color: var(--wlo-primary); margin: 22px 0 4px; padding-top: 14px; border-top: 2px solid var(--wlo-border); }
    .sec { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--wlo-text-muted); margin: 16px 0 8px; }
    /* Flex lanes whose cards grow to fill the row (matches the base stats lane optics). */
    .grid { display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch; }
    .grid wlo-stat-bars { flex: 1 1 0; min-width: 240px; }
    .grid wlo-stat-bars.wide { flex: 2 1 0; min-width: 360px; }
  `],
})
export class FullStatsComponent {
  readonly i18n = inject(I18n);
  @Input() stats: FullStats | null = null;

  /** {value,count} list → bar rows. No per-row colour → the card's default green (matches base). */
  rows(items: BarEntry[] | undefined): BarRow[] {
    return barRows(items);
  }

  qvRows(): BarRow[] {
    const q = this.stats?.quellenverwaltung;
    return q ? [
      { label: this.i18n.t('stats.qv.all'), value: q.gesamt },
      { label: this.i18n.t('stats.qv.node'), value: q.mitQuelldatensatz },
      { label: this.i18n.t('stats.qv.bq'), value: q.mitBezugsquelle },
      { label: this.i18n.t('stats.qv.both'), value: q.ueberschneidung },
    ] : [];
  }

  coverageRows(): BarRow[] {
    const c = this.stats?.contentCoverage;
    return c ? [
      { label: this.i18n.t('stats.cov.bq'), value: c.bezugsquelle },
      { label: this.i18n.t('stats.cov.crawler'), value: c.crawler },
      { label: this.i18n.t('stats.cov.node'), value: c.quelldatensatz },
    ] : [];
  }

  /** Descriptive-field fill (already a percentage over the Quelldatensätze), highest first. */
  beschRows(items: Array<{ feld: string; prozent: number }> | undefined): BarRow[] {
    return (items ?? []).map((f) => ({ label: f.feld, value: f.prozent }));
  }

  fillHint(basis: number): string {
    return `${this.i18n.t('stats.fill.nodeHint')} (n=${basis})`;
  }
}
