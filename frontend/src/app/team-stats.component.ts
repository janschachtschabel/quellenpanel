import { Component, Input, inject } from '@angular/core';
import { DupInfo, TeamStats } from './models';
import { BarRow, StatBarsComponent } from './stat-bars.component';
import { PRUEF_GROUPS } from './data-problem-filters';
import { MergeFlowComponent } from './merge-flow.component';
import { I18n } from './i18n.service';

/** Map each data-problem flag (the filter vocabulary) to its key in the team `probleme` payload,
 * so the chart reuses the SAME translated labels as the "Datenprüfung" filter (single source of
 * truth). Flags without a problem count (WLO_MIGRATION / LEGACY_BINDUNG are provenance markers,
 * not problems) are simply absent here and skipped. */
const PROBLEM_KEY: Record<string, string> = {
  FEHLTAGGING: 'mischTypen_fehltagging',
  ZWEITDATENSATZ: 'zweitDatensaetze',
  BQ_EINZELINHALT: 'bezugsquelleEinzelinhalt',
  DUBLETTE_VERDACHT: 'dublettenVerdacht',
  METADATEN_DUENN: 'metadatenDuenn',
  BLACKLIST: 'blacklist',
  QD_OHNE_BEZUGSQUELLE: 'quelldatensatzOhneBezugsquelle',
  BINDUNG_UNVOLLSTAENDIG: 'bindungUnvollstaendig',
  TYP_NICHT_QUELLE: 'typNichtQuelle',
  BQ_OHNE_QD: 'bezugsquelleOhneQuelldatensatz',
  OHNE_STATUS: 'ohneStatus',
  STATUS_INKONSISTENT: 'statusInkonsistent',
  NICHT_PUBLIZIERT: 'nichtPubliziert',
  SPIDER_UNEINDEUTIG: 'spiderUneindeutig',
  BQ_SUBCHANNEL: 'bqSubchannel',
  WLO_MIGRATION: 'wloMigration',
  LEGACY_BINDUNG: 'legacyBindung',
};

/**
 * Team-only statistics addendum (tier 2, "Audit"), shown beneath the full overview: data problems
 * (1:1 with the "Datenprüfung" filter), spider/source binding, origin overlap, duplicate URLs /
 * titles, field fill-levels and information origin. Bar-list cards only (no chart library).
 */
@Component({
  selector: 'wlo-team-stats',
  standalone: true,
  imports: [StatBarsComponent, MergeFlowComponent],
  template: `
  @if (stats; as s) {
    <div class="tier-head team">🔒 {{ i18n.t('stats.tier2.title') }}</div>

    <!-- Data quality: a problem-concentration overview (NOT a repeat of the per-problem bars),
         then the problems split by thematic group, then example drill-downs -->
    <div class="sec team">{{ i18n.t('stats.team.sec.problems') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.perSource')" [rows]="perSourceRows()"
        [hint]="i18n.t('stats.perSource.hint')"></wlo-stat-bars>
    </div>

    <div class="sec team">{{ i18n.t('stats.team.sec.problemGroups') }}</div>
    <div class="grid">
      @for (g of problemGroups(); track g.title) {
        <wlo-stat-bars [title]="g.title" [rows]="g.rows"></wlo-stat-bars>
      }
    </div>

    @if (problemExampleCards().length) {
      <div class="sec team">{{ i18n.t('stats.team.sec.problemExamples') }}</div>
      <div class="grid">
        @for (c of problemExampleCards(); track c.title) {
          <wlo-stat-bars [title]="c.title" [rows]="c.rows" [hint]="c.hint"></wlo-stat-bars>
        }
      </div>
    }

    <!-- Spider / source-dataset binding -->
    <div class="sec team">{{ i18n.t('stats.team.sec.binding') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.spiderBinding')" [rows]="spiderRows()"
        [hint]="i18n.t('stats.spider.hint')"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.intersection')" [rows]="schnittRows()"
        [hint]="i18n.t('stats.intersection.hint')"></wlo-stat-bars>
    </div>

    <!-- Fill level: AI/legal notes only (descriptive-metadata fill is in the Details view) -->
    <div class="sec team">{{ i18n.t('stats.team.sec.fill') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.fillKi')" [rows]="fuellKi()" [percent]="true"
        [hint]="fillHint(s.feldFuellstand.kiBasis)"></wlo-stat-bars>
    </div>

    <div class="sec team">{{ i18n.t('stats.team.sec.dups') }}</div>
    <div class="grid">
      <wlo-stat-bars [title]="i18n.t('stats.card.dupUrl')" [rows]="dupRows(s.probleme.doppelteUrl)"
        [hint]="dupHint(s.probleme.doppelteUrl)"></wlo-stat-bars>
      <wlo-stat-bars [title]="i18n.t('stats.card.dupTitle')" [rows]="dupRows(s.probleme.doppelteTitel)"
        [hint]="dupHint(s.probleme.doppelteTitel)"></wlo-stat-bars>
    </div>

    <!-- How the engine merges the data (replaces the old information-origin bars) -->
    <div class="sec team">{{ i18n.t('stats.team.sec.merge') }}</div>
    <wlo-merge-flow></wlo-merge-flow>
  }
  `,
  styles: [`
    :host { display: block; padding: 0 16px 16px; }
    .tier-head { font-size: 13px; font-weight: 700; margin: 22px 0 4px; padding-top: 14px; border-top: 2px solid var(--wlo-border); }
    .tier-head.team { color: #b3261e; }
    .sec { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--wlo-text-muted); margin: 20px 0 8px; }
    .sec.team { color: #b3261e; display: flex; align-items: center; gap: 6px; }
    .sec.team::before { content: '🔒'; font-size: 12px; }
    /* Flex lanes whose cards grow to fill the row. min-width 340 caps a row at ~3 cards on the full
       width, so the 6 example cards form a balanced 3+3 (instead of 5 + one full-width straggler)
       while the 2- and 3-card lanes still fill the row. */
    .grid { display: flex; flex-wrap: wrap; gap: 12px; align-items: stretch; }
    .grid wlo-stat-bars { flex: 1 1 0; min-width: 340px; }
    .grid wlo-stat-bars.wide { flex: 2 1 0; min-width: 360px; }
  `],
})
export class TeamStatsComponent {
  readonly i18n = inject(I18n);
  @Input() stats: TeamStats | null = null;

  /** Problem-concentration overview: how many sources carry 0 / 1 / 2 / 3+ data defects at once.
   * Complements (does not duplicate) the per-problem group charts below. */
  perSourceRows(): BarRow[] {
    return (this.stats?.problemeProQuelle ?? []).map((e) => ({ label: this.bucketLabel(e.value), value: e.count }));
  }

  private bucketLabel(b: string): string {
    const de = this.i18n.lang() === 'de';
    if (b === '0') return de ? 'ohne Datenproblem' : 'no data problem';
    const noun = de ? (b === '1' ? 'Datenproblem' : 'Datenprobleme') : (b === '1' ? 'problem' : 'problems');
    return `${b} ${noun}`;
  }

  /** The same problems, split into the three thematic groups (reuses the filter vocabulary),
   * each sorted by frequency — makes the severity per category visible at a glance. */
  problemGroups(): Array<{ title: string; rows: BarRow[] }> {
    const pr = this.stats?.probleme;
    if (!pr) return [];
    const de = this.i18n.lang() === 'de';
    return PRUEF_GROUPS.map((g) => ({
      title: de ? g.de : g.en,
      rows: g.options
        .map((o) => ({ label: de ? o.de : o.en, value: (pr[PROBLEM_KEY[o.flag]] as number) ?? 0 }))
        .sort((a, b) => b.value - a.value),
    }));
  }

  /** Drill-down: the biggest problems with a few concrete example sources (largest by content). */
  problemExampleCards(): Array<{ title: string; rows: BarRow[]; hint: string }> {
    const pr = this.stats?.probleme;
    const ex = this.stats?.problemBeispiele;
    if (!pr || !ex) return [];
    const de = this.i18n.lang() === 'de';
    return PRUEF_GROUPS.flatMap((g) => g.options)
      .map((o) => ({ o, count: (pr[PROBLEM_KEY[o.flag]] as number) ?? 0, samples: ex[o.flag] ?? [] }))
      .filter((x) => x.count > 0 && x.samples.length)
      .sort((a, b) => b.count - a.count)
      .slice(0, 6)
      .map((x) => ({
        title: de ? x.o.de : x.o.en,
        rows: x.samples.map((s) => ({ label: s.name, value: s.inhalte })),
        hint: `${x.count} ${this.i18n.t('stats.examples.affected')}`,
      }));
  }

  spiderRows(): BarRow[] {
    const sb = this.stats?.spiderBindung;
    return sb ? [
      { label: this.i18n.t('stats.spider.gi'), value: sb.mitGeneralIdentifier },
      { label: this.i18n.t('stats.spider.rs'), value: sb.mitReplicationsource },
      { label: this.i18n.t('stats.spider.both'), value: sb.beide },
      { label: this.i18n.t('stats.spider.real'), value: sb.echteBindungGesamt },
    ] : [];
  }

  schnittRows(): BarRow[] {
    const h = this.stats?.herkunft;
    return h ? [
      { label: this.i18n.t('stats.herkunft.clean'), value: h.schnittmenge_sauber },
      { label: this.i18n.t('stats.herkunft.zweit'), value: h.schnittmenge_zweitDatensatz },
      { label: this.i18n.t('stats.herkunft.blacklist'), value: h.schnittmenge_blacklist },
    ] : [];
  }

  fuellKi(): BarRow[] {
    return (this.stats?.feldFuellstand.ki ?? []).map((f) => ({ label: f.feld, value: f.prozent }));
  }

  fillHint(basis: number): string {
    return `${this.i18n.t('stats.fill.hint')} (n=${basis})`;
  }

  dupRows(d: DupInfo | undefined): BarRow[] {
    return (d?.beispiele ?? []).map((b) => ({ label: b.wert || '—', value: b.anzahl }));
  }

  dupHint(d: DupInfo | undefined): string {
    if (!d) return '';
    return `${d.gruppen} ${this.i18n.t('stats.dup.groups')} · ${d.ueberzaehlig} ${this.i18n.t('stats.dup.extra')}`;
  }
}
