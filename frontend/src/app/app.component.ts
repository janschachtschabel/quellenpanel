import { Component, Input, OnInit, OnDestroy, inject, signal, computed, Signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

import { FilterOptions, FullStats, SourcesPage, Stats, TeamStats } from './models';
import { SourcesService } from './sources.service';
import { StatsComponent } from './stats.component';
import { FullStatsComponent } from './full-stats.component';
import { TeamStatsComponent } from './team-stats.component';
import { TilesComponent } from './tiles.component';
import { ListComponent } from './list.component';
import { DetailDialogComponent } from './detail.component';
import { ImpressumDialogComponent } from './impressum.component';
import { AuditReportComponent } from './audit-report.component';
import { TeamLoginComponent } from './team-login.component';
import { TierService } from './tier.service';
import { SelectionService } from './selection.service';
import { PdfService } from './pdf.service';
import { PRUEF_GROUPS } from './data-problem-filters';
import { I18n } from './i18n.service';

type View = 'tile' | 'list' | 'stats';

/**
 * Page shell + orchestrator: the framed header, the filter controls, the view switch and
 * pagination, plus data loading and dialog opening. The three views (tiles / list / stats)
 * and the dialogs (detail / Impressum) live in their own components.
 */
@Component({
  selector: 'wlo-root',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatIconModule, MatButtonModule, MatButtonToggleModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatCheckboxModule, MatPaginatorModule,
    MatProgressBarModule, MatDialogModule, MatSnackBarModule, StatsComponent, FullStatsComponent,
    TeamStatsComponent, TilesComponent, ListComponent,
  ],
  template: `
  <div class="host">
    <header class="bar">
      <div class="bar-left">
        <img class="logo" src="wlo-logo.svg" alt="WissenLebtOnline">
        <span class="sep"></span>
        <span class="brand">{{ i18n.t('app.title') }}</span>
        @if (data) { <span class="total-badge">{{ data.total | number }}</span> }
      </div>
      <div class="bar-right">
        <mat-button-toggle-group class="views" [(ngModel)]="view" (change)="onViewChange()"
          hideSingleSelectionIndicator [attr.aria-label]="i18n.t('aria.view')">
          <mat-button-toggle value="tile"><mat-icon>grid_view</mat-icon> {{ i18n.t('view.tiles') }}</mat-button-toggle>
          <mat-button-toggle value="list"><mat-icon>view_list</mat-icon> {{ i18n.t('view.list') }}</mat-button-toggle>
          <mat-button-toggle value="stats"><mat-icon>bar_chart</mat-icon> {{ i18n.t('view.stats') }}</mat-button-toggle>
        </mat-button-toggle-group>
        <mat-button-toggle-group class="tiers" [value]="tiers.tier()" (change)="onTierToggle($event.value)"
          hideSingleSelectionIndicator [attr.aria-label]="i18n.t('tier.aria')">
          <mat-button-toggle [value]="0"><mat-icon>visibility</mat-icon> {{ i18n.t('tier.base') }}</mat-button-toggle>
          <mat-button-toggle [value]="1"><mat-icon>list_alt</mat-icon> {{ i18n.t('tier.details') }}</mat-button-toggle>
          <mat-button-toggle [value]="2"><mat-icon>lock</mat-icon> {{ i18n.t('tier.audit') }}</mat-button-toggle>
        </mat-button-toggle-group>
        <mat-button-toggle-group class="lang" [value]="i18n.lang()" (change)="i18n.set($event.value)"
          hideSingleSelectionIndicator [attr.aria-label]="i18n.t('aria.lang')">
          <mat-button-toggle value="de">DE</mat-button-toggle>
          <mat-button-toggle value="en">EN</mat-button-toggle>
        </mat-button-toggle-group>
      </div>
    </header>

    @if (view !== 'stats') {
      <div class="filters">
        <div class="filter-row top">
          <mat-form-field appearance="outline" class="search">
            <mat-icon matPrefix>search</mat-icon>
            <mat-label>{{ i18n.t('filter.search') }}</mat-label>
            <input matInput [(ngModel)]="q" (keyup.enter)="applyFilters()" [placeholder]="i18n.t('filter.search.ph')">
          </mat-form-field>
          <mat-form-field appearance="outline" class="art">
            <mat-icon matPrefix>category</mat-icon>
            <mat-label>{{ i18n.t('filter.art') }}</mat-label>
            <mat-select [(ngModel)]="quellenart" (selectionChange)="applyFilters()">
              <mat-option value="">{{ i18n.t('filter.all') }}</mat-option>
              <mat-option value="crawler">{{ i18n.t('filter.art.crawler') }}</mat-option>
              <mat-option value="node">{{ i18n.t('filter.art.node') }}</mat-option>
              <mat-option value="bq">{{ i18n.t('filter.art.bq') }}</mat-option>
              <mat-option value="both">{{ i18n.t('filter.art.both') }}</mat-option>
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="sort">
            <mat-icon matPrefix>sort</mat-icon>
            <mat-label>{{ i18n.t('filter.sort') }}</mat-label>
            <mat-select [(ngModel)]="sort" (selectionChange)="applyFilters()">
              <mat-option value="contentCount">{{ i18n.t('filter.sort.content') }}</mat-option>
              <mat-option value="name">{{ i18n.t('filter.sort.name') }}</mat-option>
            </mat-select>
          </mat-form-field>
        </div>
        <div class="filter-row">
          <mat-form-field appearance="outline" class="subject">
            <mat-icon matPrefix>school</mat-icon>
            <mat-label>{{ i18n.t('filter.subject') }}</mat-label>
            <mat-select [(ngModel)]="subject" (selectionChange)="applyFilters()">
              <mat-option value="">{{ i18n.t('filter.subject.all') }}</mat-option>
              @for (s of options?.subjects ?? []; track s) { <mat-option [value]="s">{{ s }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="level">
            <mat-icon matPrefix>grade</mat-icon>
            <mat-label>{{ i18n.t('filter.level') }}</mat-label>
            <mat-select [(ngModel)]="level" (selectionChange)="applyFilters()">
              <mat-option value="">{{ i18n.t('filter.level.all') }}</mat-option>
              @for (l of options?.levels ?? []; track l) { <mat-option [value]="l">{{ l }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="lrt">
            <mat-icon matPrefix>description</mat-icon>
            <mat-label>{{ i18n.t('filter.lrt') }}</mat-label>
            <mat-select [(ngModel)]="lrt" (selectionChange)="applyFilters()">
              <mat-option value="">{{ i18n.t('filter.all') }}</mat-option>
              @for (l of options?.lrts ?? []; track l) { <mat-option [value]="l">{{ l }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="status">
            <mat-icon matPrefix>task</mat-icon>
            <mat-label>{{ i18n.t('filter.status') }}</mat-label>
            <mat-select [(ngModel)]="erschliessung" (selectionChange)="applyFilters()">
              <mat-option value="">{{ i18n.t('filter.all') }}</mat-option>
              @for (e of options?.erschliessung ?? []; track e) { <mat-option [value]="e">{{ e }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-form-field appearance="outline" class="min">
            <mat-icon matPrefix>filter_9_plus</mat-icon>
            <mat-label>{{ i18n.t('filter.minCount') }}</mat-label>
            <mat-select [(ngModel)]="minCount" (selectionChange)="applyFilters()">
              @for (n of minCountOptions; track n) { <mat-option [value]="n">{{ n === 0 ? i18n.t('filter.all') : n + '+' }}</mat-option> }
            </mat-select>
          </mat-form-field>
          <mat-checkbox [(ngModel)]="onlyOer" (change)="applyFilters()">{{ i18n.t('filter.oer') }}</mat-checkbox>
          <mat-checkbox [(ngModel)]="onlyFieldProfile" (change)="applyFilters()">{{ i18n.t('filter.fieldProfile') }}</mat-checkbox>
          <button mat-stroked-button class="clear-btn" (click)="clearFilters()">
            <mat-icon>filter_alt_off</mat-icon> {{ i18n.t('filter.clear') }}
          </button>
          @if (tiers.tier() === 2) {
            <mat-form-field appearance="outline" class="flag">
              <mat-icon matPrefix>bug_report</mat-icon>
              <mat-label>{{ i18n.t('filter.problem') }}</mat-label>
              <mat-select [(ngModel)]="flag" (selectionChange)="applyFilters()" [panelWidth]="440">
                <mat-option value="">{{ i18n.t('filter.all') }}</mat-option>
                @for (g of pruefGroups; track g.de) {
                  <mat-optgroup [label]="i18n.lang() === 'de' ? g.de : g.en">
                    @for (o of g.options; track o.flag) {
                      <mat-option [value]="o.flag">{{ i18n.lang() === 'de' ? o.de : o.en }}</mat-option>
                    }
                  </mat-optgroup>
                }
              </mat-select>
            </mat-form-field>
          }
        </div>
      </div>
    }

    @if (loading && view !== 'stats') { <mat-progress-bar mode="indeterminate"></mat-progress-bar> }

    @if (view === 'stats') {
      <!-- Base stats always shown; higher tiers append their extra swimlanes below (same optics). -->
      <wlo-stats [stats]="stats"></wlo-stats>
      @if (tiers.tier() >= 1) { <wlo-full-stats [stats]="fullStats"></wlo-full-stats> }
      @if (tiers.tier() >= 2) { <wlo-team-stats [stats]="teamStats"></wlo-team-stats> }
    } @else {
      <div class="results">
        <div class="results-head">
          <p class="count">{{ data?.total ?? 0 | number }} {{ i18n.t('results.count') }}@if (tiers.tier() >= 2 && data?.hidden?.total) { <span class="hidden-info"> · {{ data!.hidden!.blacklist | number }} {{ i18n.t('status.blacklist') }} + {{ data!.hidden!.mehrfach | number }} {{ i18n.t('status.mehrfach') }} {{ i18n.t('status.hidden') }}</span> }</p>
          <span class="rh-spacer"></span>
          @if (tiers.tier() >= 1) {
            <button mat-stroked-button type="button" (click)="exportTablePdf()" [disabled]="tableBusy" [attr.title]="i18n.t('export.tableTitle')"><mat-icon>print</mat-icon> {{ i18n.t('export.table') }}</button>
            <button mat-stroked-button type="button" (click)="exportList('csv')" [attr.title]="i18n.t('action.exportCsv')"><mat-icon>download</mat-icon> CSV</button>
            <button mat-stroked-button type="button" (click)="exportList('json')" [attr.title]="i18n.t('action.exportJson')"><mat-icon>download</mat-icon> JSON</button>
          }
          @if (tiers.tier() >= 2) {
            <button mat-stroked-button type="button" (click)="openAuditReport()"><mat-icon>fact_check</mat-icon> {{ i18n.t('audit.open') }}</button>
          }
        </div>

        @if (tiers.tier() >= 1 && sel.count() > 0) {
          <div class="selbar">
            <span class="selcount"><mat-icon>check_box</mat-icon> {{ sel.count() }} {{ i18n.t('select.selected') }}</span>
            <span class="selspacer"></span>
            <button mat-stroked-button type="button" (click)="sel.clear()">
              <mat-icon>clear</mat-icon> {{ i18n.t('select.clear') }}
            </button>
            <button mat-flat-button color="primary" type="button" [disabled]="pdfBusy" (click)="exportPdf()">
              <mat-icon>picture_as_pdf</mat-icon> {{ pdfBusy ? i18n.t('select.pdfBusy') : i18n.t('select.pdf') }}
            </button>
          </div>
        }

        @if (view === 'tile') {
          <wlo-tiles [items]="data?.items ?? []" [selectable]="tiers.tier() >= 1" (open)="openDetail($event)"></wlo-tiles>
        } @else {
          <wlo-list [items]="data?.items ?? []" [selectable]="tiers.tier() >= 1" (open)="openDetail($event)"></wlo-list>
        }

        @if (!loading && (data?.total ?? 0) === 0) {
          <p class="empty">{{ i18n.t('results.empty') }}</p>
        }

        <mat-paginator
          [length]="data?.total ?? 0"
          [pageSize]="effectivePageSize()"
          [pageIndex]="page - 1"
          [pageSizeOptions]="pageSizeOptions()"
          (page)="onPage($event)">
        </mat-paginator>
      </div>
    }

    <footer class="appfoot">
      <span class="foot-brand">WissenLebtOnline · {{ i18n.t('app.title') }}</span>
      <nav class="foot-links">
        <button type="button" class="foot-link" (click)="openImpressum()">{{ i18n.t('footer.impressum') }}</button>
        <a class="foot-link" href="https://wirlernenonline.de/datenschutz/" target="_blank" rel="noopener">{{ i18n.t('footer.privacy') }} ↗</a>
        <a class="foot-link" href="https://wirlernenonline.de/" target="_blank" rel="noopener">wirlernenonline.de ↗</a>
      </nav>
    </footer>
  </div>
  `,
  styles: [`
    .host {
      max-width: 1320px; margin: 16px auto; background: var(--wlo-bg);
      border: 1px solid var(--wlo-border); border-radius: 12px; overflow: hidden;
      box-shadow: 0 1px 4px rgba(18,33,58,.06);
    }

    .bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 8px 16px; min-height: 56px; background: var(--wlo-card); border-bottom: 1px solid var(--wlo-border); }
    .bar-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .logo { height: 38px; width: auto; display: block; flex-shrink: 0; }
    .sep { width: 1px; height: 24px; background: var(--wlo-border); flex-shrink: 0; }
    .brand { font-size: 15px; font-weight: 700; color: var(--wlo-text); white-space: nowrap; }
    .total-badge { background: var(--wlo-primary-light); color: var(--wlo-primary); font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 10px; }
    .views { --mat-standard-button-toggle-height: 36px; font-size: 13px; }
    .views mat-icon { font-size: 17px; width: 17px; height: 17px; vertical-align: -3px; margin-right: 2px; }
    .bar-right { display: flex; align-items: center; gap: 12px; }
    .lang { --mat-standard-button-toggle-height: 36px; font-size: 12px; flex-shrink: 0; }
    .tiers { --mat-standard-button-toggle-height: 36px; font-size: 13px; }
    .tiers mat-icon { font-size: 16px; width: 16px; height: 16px; vertical-align: -3px; margin-right: 2px; }

    .filters { display: flex; flex-direction: column; gap: 12px; padding: 16px; }
    .filter-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .filter-row.top .search { flex: 1 1 auto; min-width: 240px; }
    .filter-row.top .art { width: 190px; flex-shrink: 0; }
    .filter-row.top .sort { width: 180px; flex-shrink: 0; }
    .filter-row .subject { width: 170px; }
    .filter-row .level { width: 150px; }
    .filter-row .lrt { width: 180px; }
    .filter-row .status { width: 220px; }
    .filter-row .min { width: 120px; }
    .filter-row .flag { width: 220px; }
    .filters mat-form-field { font-size: 14px; }
    .filters mat-form-field mat-icon[matPrefix] { font-size: 18px; width: 18px; height: 18px; color: var(--wlo-text-muted); }
    .filters mat-checkbox { font-size: 13px; }
    .clear-btn { flex-shrink: 0; font-size: 13px; }
    .results { padding: 0 16px 24px; }
    .results-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 4px 0 12px; }
    .results-head .count { color: var(--wlo-text-muted); font-size: 14px; margin: 0; }
    .results-head .hidden-info { color: var(--wlo-text-muted); }
    .results-head .rh-spacer { flex: 1; }
    .results-head button { --mat-standard-button-toggle-height: 32px; font-size: 13px; }
    .results-head button mat-icon { font-size: 17px; width: 17px; height: 17px; vertical-align: -3px; }
    .empty { text-align: center; color: var(--wlo-text-muted); padding: 40px; }
    mat-paginator { margin-top: 20px; background: var(--wlo-card); border-top: 1px solid var(--wlo-border); border-radius: 0 0 8px 8px; }

    /* Sammel-PDF selection bar (tier 1+, shown once ≥1 source is ticked). */
    .selbar { display: flex; align-items: center; gap: 10px; padding: 8px 14px; margin-bottom: 14px; background: var(--wlo-primary-light); border: 1px solid var(--wlo-primary); border-radius: 10px; }
    .selcount { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; font-size: 14px; color: var(--wlo-primary); }
    .selcount mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .selspacer { flex: 1; }

    .appfoot { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--wlo-border); background: var(--wlo-card); font-size: 12px; color: var(--wlo-text-muted); }
    .foot-links { display: flex; gap: 14px; align-items: center; }
    .foot-link { background: none; border: none; padding: 0; font: inherit; font-size: 12px; color: var(--wlo-text-muted); cursor: pointer; text-decoration: none; }
    .foot-link:hover { color: var(--wlo-primary); text-decoration: underline; }
    @media (max-width: 600px) { .filter-row.top .search { flex-basis: 100%; } .filter-row.top .sort { width: 100%; } }
  `],
})
export class AppComponent implements OnInit {
  private readonly api = inject(SourcesService);
  private readonly dialog = inject(MatDialog);
  private readonly snack = inject(MatSnackBar);
  private readonly pdf = inject(PdfService);
  readonly i18n = inject(I18n);
  readonly tiers = inject(TierService);
  readonly sel = inject(SelectionService);

  /**
   * Backend base URL, settable via the `api-base` attribute when embedded as a custom element
   * (see main.element.ts). A *static* `api-base` attribute is already present when
   * @angular/elements connects the element, so this setter runs before the first change-detection
   * pass and therefore before ngOnInit's load() — verified by embedding the built element on a
   * cross-origin host, where it loads from the configured backend rather than the host origin.
   * Omitted in the standalone SPA, which keeps the same-origin '/api'. (Setting api-base
   * dynamically *after* connect is not a supported pattern: it would not re-trigger the initial
   * load. The documented usage is the static attribute.)
   */
  @Input('api-base') set apiBase(value: string) {
    this.api.setBase(value);
  }

  /**
   * Enable credentialed (cookie) requests for cross-origin team login, via the `with-credentials`
   * attribute on the embedded element (e.g. `with-credentials="true"`, or the bare attribute).
   * Only needed when the panel is embedded on a DIFFERENT origin than the backend AND that origin
   * is listed in the backend's QE_ALLOWED_ORIGINS. Omitted in the same-origin SPA.
   */
  @Input('with-credentials') set withCredentials(value: string | boolean) {
    this.api.setCredentials(value === '' || value === true || value === 'true');
  }

  view: View = 'tile';
  q = '';
  subject = '';
  level = '';
  erschliessung = '';
  flag = '';                 // tier 2 (team) data-problem filter
  readonly pruefGroups = PRUEF_GROUPS;
  minCount = 0;
  sort: 'contentCount' | 'name' = 'contentCount';
  onlyOer = false;
  quellenart: '' | 'crawler' | 'node' | 'bq' | 'both' = '';
  onlyFieldProfile = false;
  lrt = '';
  readonly minCountOptions = [0, 1, 5, 10, 50, 100];

  page = 1;
  pageSize = 24;

  private readonly _columns = signal(5);
  private static readonly COL_BREAKPOINTS = [
    { min: 1240, cols: 5 },
    { min: 921,  cols: 4 },
    { min: 621,  cols: 3 },
    { min: 0,    cols: 2 },
  ];
  private readonly _mqls: MediaQueryList[] = [];
  private readonly _mqlHandlers: ((e: MediaQueryListEvent) => void)[] = [];

  readonly effectivePageSize: Signal<number> = computed(() => {
    const cols = this._columns();
    return Math.ceil(this.pageSize / cols) * cols;
  });

  readonly pageSizeOptions: Signal<number[]> = computed(() => {
    const cols = this._columns();
    return [...new Set([12, 24, 48, 96].map(n => Math.ceil(n / cols) * cols))];
  });
  data: SourcesPage | null = null;
  options: FilterOptions | null = null;
  stats: Stats | null = null;            // tier 0 overview
  fullStats: FullStats | null = null;    // tier 1+ overview
  teamStats: TeamStats | null = null;    // tier 2 problem addendum
  loading = false;
  pdfBusy = false;           // Sammel-PDF in progress (disables the export button)
  tableBusy = false;         // table-PDF ("Tabelle drucken") in progress

  constructor() {
    for (const bp of AppComponent.COL_BREAKPOINTS) {
      const mql = window.matchMedia(`(min-width: ${bp.min}px)`);
      const handler = (e: MediaQueryListEvent) => {
        if (e.matches) {
          this._columns.set(bp.cols);
          this.page = 1;
          this.load();
        }
      };
      mql.addEventListener('change', handler);
      this._mqls.push(mql);
      this._mqlHandlers.push(handler);
    }
    this.syncColumns();
  }

  private syncColumns(): void {
    for (const bp of AppComponent.COL_BREAKPOINTS) {
      if (window.matchMedia(`(min-width: ${bp.min}px)`).matches) {
        this._columns.set(bp.cols);
        return;
      }
    }
  }

  ngOnDestroy(): void {
    this._mqls.forEach((mql, i) => mql.removeEventListener('change', this._mqlHandlers[i]));
  }

  ngOnInit(): void {
    this.tiers.loadCapabilities();   // decides which tier controls the header shows
    this.api.filterOptions().subscribe((o) => (this.options = o));
    this.load();
  }

  onViewChange(): void {
    if (this.view === 'stats') { this.loadStats(); }   // fetch the right shape for the current tier
  }

  applyFilters(): void {
    this.page = 1;
    this.load();
  }

  /** Reset every filter control to its default and reload the list. */
  clearFilters(): void {
    this.q = '';
    this.subject = '';
    this.level = '';
    this.erschliessung = '';
    this.minCount = 0;
    this.sort = 'contentCount';
    this.onlyOer = false;
    this.quellenart = '';
    this.onlyFieldProfile = false;
    this.lrt = '';
    this.flag = '';
    this.applyFilters();
  }

  onPage(e: PageEvent): void {
    this.page = e.pageIndex + 1;
    const opts = this.pageSizeOptions();
    const idx = opts.indexOf(e.pageSize);
    this.pageSize = idx >= 0 ? [12, 24, 48, 96][idx] : e.pageSize;
    this.load();
  }

  /** Switch information tier via the header toggle (Basisinfos / Details / Audit). Audit (2)
   *  needs a team login when not yet authenticated; if it is cancelled, the `[value]` binding
   *  snaps the toggle back to the active tier. */
  onTierToggle(t: number): void {
    if (t === 2 && this.tiers.maxTier() < 2) {
      this.dialog.open(TeamLoginComponent, { width: '360px', autoFocus: false })
        .afterClosed().subscribe((ok) => { if (ok) this.reload(); });
      return;
    }
    this.tiers.setTier(t);
    this.reload();
  }

  private reload(): void {
    if (this.tiers.tier() < 2) { this.flag = ''; }   // the data-problem filter is tier-2 only
    if (this.tiers.tier() < 1) { this.sel.clear(); } // multi-select / Sammel-PDF is tier 1+ (Details/Audit)
    this.page = 1;
    this.load();
    if (this.view === 'stats') { this.loadStats(); }   // stats shape depends on the tier
  }

  /** Central error toast for a failed data load, so a backend/network failure is never silent. */
  private notifyError(): void {
    this.snack.open(this.i18n.t('error.load'), '', { duration: 4000 });
  }

  /** Build and download a single PDF for all currently selected sources (tier 1+). Mirrors the
   * existing apps' behaviour with a short confirmation toast (and an explicit error toast on
   * failure, so a failed export is never silent). */
  async exportPdf(): Promise<void> {
    const ids = [...this.sel.selected()];
    if (!ids.length || this.pdfBusy) return;
    this.pdfBusy = true;
    try {
      const count = await this.pdf.generate(ids);
      const msg = count ? `${this.i18n.t('select.pdfDone')} (${count})` : this.i18n.t('select.pdfEmpty');
      this.snack.open(msg, '', { duration: 3000 });
    } catch {
      this.snack.open(this.i18n.t('select.pdfError'), '', { duration: 4000 });
    } finally {
      this.pdfBusy = false;
    }
  }

  /** Open the source profile (Steckbrief) in a Material dialog. */
  openDetail(id: string): void {
    this.api.detail(id).subscribe({
      next: (d) => this.dialog.open(DetailDialogComponent, {
        data: d, width: 'min(760px, 96vw)', maxWidth: '96vw', maxHeight: '92vh', autoFocus: false,
      }),
      error: () => this.notifyError(),
    });
  }

  openImpressum(): void {
    this.dialog.open(ImpressumDialogComponent, { width: 'min(680px, 95vw)', maxHeight: '90vh', autoFocus: false });
  }

  /** Fetch the statistics: the base (end-user) overview is ALWAYS loaded and shown; higher tiers
   *  additionally load their extra swimlanes (full overview at tier 1+, team problems at tier 2). */
  private loadStats(): void {
    this.api.stats().subscribe({ next: (s) => (this.stats = s), error: () => this.notifyError() });
    const tier = this.tiers.tier();
    if (tier >= 1) {
      this.api.fullStats().subscribe({ next: (s) => (this.fullStats = s), error: () => this.notifyError() });
    }
    if (tier >= 2) {
      this.api.teamStats().subscribe({ next: (s) => (this.teamStats = s), error: () => this.notifyError() });
    }
  }

  /** Current filter params (shared by the list request and the CSV/JSON export, so they match). */
  private buildQuery(): Record<string, string | number | boolean> {
    const query: Record<string, string | number | boolean> = {
      q: this.q,
      subject: this.subject,
      level: this.level,
      erschliessung: this.erschliessung,
      min_count: this.minCount,
      sort: this.sort,
      order: this.sort === 'name' ? 'asc' : 'desc',
    };
    if (this.onlyOer) { query['oer'] = true; }
    if (this.quellenart === 'crawler') { query['has_spider'] = true; }
    else if (this.quellenart === 'node') { query['has_node'] = true; }
    else if (this.quellenart === 'bq') { query['has_bezugsquelle'] = true; }
    else if (this.quellenart === 'both') { query['has_node'] = true; query['has_bezugsquelle'] = true; }
    if (this.onlyFieldProfile) { query['only_field_profile'] = true; }
    if (this.lrt) { query['lrt'] = this.lrt; }
    if (this.tiers.tier() === 2 && this.flag) { query['flag'] = this.flag; }
    return query;
  }

  private load(): void {
    this.loading = true;
    const query = { ...this.buildQuery(), page: this.page, page_size: this.effectivePageSize() };
    this.api.sources(query).subscribe({
      next: (d) => { this.data = d; this.loading = false; },
      error: () => { this.loading = false; this.notifyError(); },
    });
  }

  /** Download the current (filtered) list as CSV / JSON — tier 1+ (the backend gates it). */
  exportList(format: 'csv' | 'json'): void {
    const a = document.createElement('a');
    a.href = this.api.exportUrl(format, this.buildQuery());
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  /** "Tabelle drucken": the current filtered list as a landscape table PDF (tier 1+). Like the
   * Sammel-PDF it confirms with a toast (and an explicit error toast on failure). */
  async exportTablePdf(): Promise<void> {
    if (this.tableBusy) return;
    this.tableBusy = true;
    try {
      const { total } = await this.pdf.tablePdf(this.buildQuery());
      const msg = total ? `${this.i18n.t('export.tableDone')} (${total})` : this.i18n.t('export.tableEmpty');
      this.snack.open(msg, '', { duration: 3000 });
    } catch {
      this.snack.open(this.i18n.t('export.tableError'), '', { duration: 4000 });
    } finally {
      this.tableBusy = false;
    }
  }

  /** Open the data-problem audit report (team / tier 2) — readable + savable + printable. */
  openAuditReport(): void {
    // maxWidth overrides MatDialog's 80vw default, which was capping the width regardless of `width`.
    this.dialog.open(AuditReportComponent, { width: '1200px', maxWidth: '96vw', maxHeight: '92vh', autoFocus: false });
  }
}
