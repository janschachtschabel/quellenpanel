import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ContentItem, FieldGenItem, SourceDetail } from './models';
import { QUALITY_GROUPS, QualityEntry, qualityEntries } from './quality';
import { groupInternal, InternalGroups } from './internal-labels';
import { SourcesService } from './sources.service';
import { PdfService } from './pdf.service';
import { TierService } from './tier.service';
import { I18n } from './i18n.service';

/**
 * Source detail (Steckbrief) in a Material dialog. Laid out as tidy titled CARD sections
 * (Grund-Informationen / Bildung / Lizenz / Qualität / KI-Nutzung & Recht / Metadaten-Erzeugung /
 * Interne Felder), mirroring the Quellensteckbriefe profile. Tier-gated content appears only when
 * the backend included it: tier 1 adds the KI + field-generation sections; tier 2 adds the
 * internal fields, data-problem flags and the per-field provenance pills.
 */
@Component({
  selector: 'wlo-detail-dialog',
  standalone: true,
  imports: [
    DecimalPipe, NgTemplateOutlet, MatDialogModule, MatChipsModule, MatIconModule, MatButtonModule,
    MatProgressSpinnerModule,
  ],
  template: `
  <!-- per-field provenance pill (team / tier 2); no-op when the field has no provenance entry -->
  <ng-template #pp let-k>@if (prov(k); as p) { <span class="prov {{ provClass(p) }}">{{ p }}</span> }</ng-template>

  <div class="dh">
    <div class="dh-preview">
      @if (effectivePreview()) {
        <img [src]="effectivePreview()" [alt]="detail.name" loading="lazy">
      } @else {
        <div class="dh-init">{{ initial }}</div>
      }
    </div>
    <div class="dh-info">
      <h2 mat-dialog-title class="dh-name">{{ detail.name }}</h2>
      <mat-chip-set>
        @if (detail.oer) { <mat-chip class="c-oer">OER</mat-chip> }
        @if (detail.license) { <mat-chip>{{ detail.license }}</mat-chip> }
        @if (detail.language) { <mat-chip>{{ detail.language }}</mat-chip> }
      </mat-chip-set>
    </div>
    <button mat-icon-button mat-dialog-close [attr.aria-label]="i18n.t('action.close')"><mat-icon>close</mat-icon></button>
  </div>

  <mat-dialog-content class="db">
    <div class="count-bar">
      <span class="c-big">{{ detail.contentCount | number }}</span>
      <span class="c-lbl">{{ i18n.t('detail.contentCount') }}</span>
      <span class="spacer"></span>
      @if (tiers.tier() >= 1) {
        <button mat-stroked-button color="primary" type="button" [disabled]="pdfBusy()" (click)="exportPdf()">
          <mat-icon>picture_as_pdf</mat-icon> {{ pdfBusy() ? i18n.t('select.pdfBusy') : i18n.t('detail.pdf') }}
        </button>
      }
      @if (detail.searchUrl) {
        <a mat-stroked-button color="primary" [href]="detail.searchUrl" target="_blank" rel="noopener">
          <mat-icon>search</mat-icon> {{ i18n.t('action.search') }}
        </a>
      }
      @if (detail.url) {
        <a mat-flat-button color="primary" [href]="detail.url" target="_blank" rel="noopener">
          {{ i18n.t('action.open') }} <mat-icon>open_in_new</mat-icon>
        </a>
      }
    </div>

    <!-- Grund-Informationen -->
    <section class="sb">
      <h3><mat-icon>info</mat-icon> {{ i18n.t('detail.sec.basic') }}</h3>
      <div class="kv">
        @if (detail.bezugsquelle) {
          <div class="k">{{ i18n.t('detail.field.bezugsquelle') }}</div>
          <div class="v">{{ detail.bezugsquelle }}</div>
        }
        @if (effectiveDescription()) {
          <div class="k">{{ i18n.t('detail.field.description') }}@if (descFromContent()) { <span class="from-content"> {{ i18n.t('detail.fromContent.desc') }}</span> } @if (!descFromContent()) {<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'description' }"></ng-container> }</div>
          <div class="v">{{ effectiveDescription() }}</div>
        }
        @if (detail.language) {
          <div class="k">{{ i18n.t('detail.field.language') }}</div>
          <div class="v">{{ detail.language }}</div>
        }
        @if (detail.erschliessungsstatus) {
          <div class="k">{{ i18n.t('detail.field.status') }}</div>
          <div class="v">{{ detail.erschliessungsstatus }}</div>
        }
        @if (tiers.tier() >= 1 && tiers.repoUrl()) {
          <div class="k">{{ i18n.t('detail.field.repo') }}</div>
          <div class="v">{{ repoHost() }}</div>
        }
      </div>
    </section>

    <!-- Bildung & Einordnung -->
    @if (detail.subjects.length || detail.educationalContext.length || detail.contentTypes.length || displayKeywords().length || detail.targetGroup.length || detail.curriculum.length || detail.ageRange) {
      <section class="sb">
        <h3><mat-icon>school</mat-icon> {{ i18n.t('detail.sec.education') }}</h3>
        <div class="kv">
          @if (detail.subjects.length) {
            <div class="k">{{ i18n.t('detail.field.subjects') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'subjects' }"></ng-container></div>
            <div class="v"><mat-chip-set>@for (s of detail.subjects; track s) { <mat-chip>{{ s }}</mat-chip> }</mat-chip-set></div>
          }
          @if (detail.educationalContext.length) {
            <div class="k">{{ i18n.t('detail.field.levels') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'educationalContext' }"></ng-container></div>
            <div class="v"><mat-chip-set>@for (l of detail.educationalContext; track l) { <mat-chip>{{ l }}</mat-chip> }</mat-chip-set></div>
          }
          @if (detail.contentTypes.length) {
            <div class="k">{{ i18n.t('detail.field.types') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'contentTypes' }"></ng-container></div>
            <div class="v"><mat-chip-set>@for (t of detail.contentTypes; track t) { <mat-chip>{{ t }}</mat-chip> }</mat-chip-set></div>
          }
          @if (detail.targetGroup.length) {
            <div class="k">{{ i18n.t('detail.kv.targetGroup') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'targetGroup' }"></ng-container></div>
            <div class="v"><mat-chip-set>@for (g of detail.targetGroup; track g) { <mat-chip>{{ g }}</mat-chip> }</mat-chip-set></div>
          }
          @if (detail.curriculum.length) {
            <div class="k">{{ i18n.t('detail.kv.curriculum') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'curriculum' }"></ng-container></div>
            <div class="v"><mat-chip-set>@for (c of detail.curriculum; track c) { <mat-chip>{{ c }}</mat-chip> }</mat-chip-set></div>
          }
          @if (detail.ageRange) {
            <div class="k">{{ i18n.t('detail.kv.age') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'ageRange' }"></ng-container></div>
            <div class="v">{{ detail.ageRange }}</div>
          }
          @if (displayKeywords().length) {
            <div class="k">{{ i18n.t('detail.field.keywords') }}@if (keywordsFromContent()) { <span class="from-content"> {{ i18n.t('detail.fromContent.kw') }}</span> } @if (!keywordsFromContent()) {<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'keywords' }"></ng-container> }</div>
            <div class="v"><mat-chip-set>@for (k of displayKeywords(); track k) { <mat-chip>{{ k }}</mat-chip> }</mat-chip-set></div>
          }
        </div>
      </section>
    }

    <!-- Lizenz -->
    @if (detail.license || detail.oer || detail.author) {
      <section class="sb">
        <h3><mat-icon>copyright</mat-icon> {{ i18n.t('detail.sec.license') }}</h3>
        <div class="kv">
          @if (detail.license) { <div class="k">{{ i18n.t('detail.field.license') }}</div><div class="v">{{ detail.license }}</div> }
          @if (detail.oer) { <div class="k">OER</div><div class="v">ja</div> }
          @if (detail.author) { <div class="k">{{ i18n.t('detail.kv.author') }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: 'author' }"></ng-container></div><div class="v">{{ detail.author }}</div> }
        </div>
      </section>
    }

    <!-- Qualitätsmerkmale -->
    @if (hasQuality()) {
      <section class="sb">
        <h3><mat-icon>star</mat-icon> {{ i18n.t('detail.sec.quality') }}</h3>
        @for (g of qualityGroups; track g.titleKey) {
          @if (groupEntries(g.keys).length) {
            <div class="q-block">
              <div class="q-lbl">{{ i18n.t(g.titleKey) }}</div>
              <div class="q-grid">
                @for (e of groupEntries(g.keys); track e.key) {
                  <div class="q-card" [class]="'q-' + e.level">
                    <mat-icon>{{ e.icon }}</mat-icon>
                    <div class="q-clbl">{{ i18n.t(e.labelKey) }}</div>
                    <div class="q-cval">{{ i18n.tValue(e.value) }}</div>
                  </div>
                }
              </div>
            </div>
          }
        }
      </section>
    }

    <!-- Metadaten-Erzeugung (tier 1+) -->
    @if (fieldGenGroups.length) {
      <section class="sb">
        <h3><mat-icon>build</mat-icon> {{ i18n.t('detail.field.fieldgen') }}@if (detail.fieldActiveCount) { <span class="sb-sub"> · {{ detail.fieldActiveCount }} {{ i18n.t('detail.field.fieldsActive') }}</span> }</h3>
        <p class="sb-hint">{{ i18n.t('detail.fieldgen.hint') }}</p>
        <table class="fgtable">
          <thead><tr>
            <th>{{ i18n.t('detail.fg.item') }}</th><th>{{ i18n.t('detail.fg.field') }}</th>
            <th>{{ i18n.t('detail.fg.status') }}</th><th>{{ i18n.t('detail.fg.gen') }}</th>
          </tr></thead>
          <tbody>
            @for (g of fieldGenGroups; track g.item) {
              @for (f of g.fields; track $index; let i = $index) {
                <tr>
                  <td>@if (i === 0) { <b>{{ g.item }}</b> }</td>
                  <td>{{ f.field }}</td>
                  <td [class.fg-active]="f.aktiv">{{ f.aktiv ? ('✓ ' + i18n.t('detail.fg.active')) : (f.status || '—') }}</td>
                  <td class="fg-how">{{ f.how || (f.aktiv ? i18n.t('detail.fg.fromSource') : '') }}</td>
                </tr>
              }
            }
          </tbody>
        </table>
      </section>
    }

    <!-- KI-Nutzung & Recht (tier 1+): the four legal/AI fields (empty → —). Placed AFTER the crawler
         field-generation table (editorial order). -->
    @if (detail.ki && keys(detail.ki).length) {
      <section class="sb">
        <h3><mat-icon>balance</mat-icon> {{ i18n.t('detail.field.ki') }}</h3>
        <p class="sb-hint">{{ i18n.t('detail.ki.hint') }}</p>
        <div class="kv ki">
          @for (k of keys(detail.ki); track k) {
            <div class="k">{{ k }}<ng-container [ngTemplateOutlet]="pp" [ngTemplateOutletContext]="{ $implicit: k }"></ng-container></div>
            <div class="v">@if (detail.ki[k]) { {{ detail.ki[k] }} } @else { <span class="muted">—</span> }</div>
          }
        </div>
      </section>
    }

    <!-- Interne Felder (tier 2): tidy facts grid + Bemerkungen -->
    @if (internalGroups.facts.length || internalGroups.remarks.length) {
      <section class="sb internal">
        <h3><mat-icon>lock</mat-icon> {{ i18n.t('detail.field.internal') }}</h3>
        @if (internalGroups.facts.length) {
          <div class="kv">
            @for (f of internalGroups.facts; track f.label) {
              <div class="k">{{ f.label }}</div><div class="v">{{ f.value }}</div>
            }
          </div>
        }
        @if (internalGroups.remarks.length) {
          <div class="sb-sub2">{{ i18n.t('detail.internal.remarks') }}</div>
          <div class="kv remarks">
            @for (r of internalGroups.remarks; track r.label) {
              <div class="k">{{ r.label }}</div><div class="v">{{ r.value }}</div>
            }
          </div>
        }
      </section>
    }

    <!-- Datenproblem-Marker (tier 2) -->
    @if (detail.flags && detail.flags.length) {
      <section class="sb">
        <h3><mat-icon>flag</mat-icon> {{ i18n.t('detail.field.flags') }}</h3>
        <mat-chip-set>@for (f of detail.flags; track f) { <mat-chip>{{ f }}</mat-chip> }</mat-chip-set>
      </section>
    }

    <!-- Verwandte Quellen unter derselben Bezugsquelle (Publisher + Sub-Channels, z. B. YouTube).
         Audit-Tier (tier 2): data-work context, hier bei den Datenproblemen/Anmerkungen — nur
         sichtbar, wenn der Backend es liefert (tier 2) UND es Geschwister-Quellen gibt. -->
    @if (detail.related; as rel) {
      <section class="sb">
        <h3><mat-icon>account_tree</mat-icon> {{ i18n.t('detail.sec.related') }}</h3>
        <p class="sb-hint">{{ i18n.t('detail.related.hint') }} <strong>{{ rel.bezugsquelle }}</strong></p>
        <p class="sb-hint rel-warn"><mat-icon>flag</mat-icon> {{ i18n.t('detail.related.problem') }}</p>
        <div class="rel-list">
          @for (s of rel.items; track s.id) {
            <div class="rel-item">
              <mat-icon class="rel-ic" [class.node]="s.hasNode"
                [title]="s.hasNode ? i18n.t('detail.related.node') : i18n.t('detail.related.bq')">{{ s.hasNode ? 'description' : 'public' }}</mat-icon>
              <span class="rel-name" [title]="s.name">{{ s.name }}</span>
              @if (s.nodeId) { <span class="rel-node" [title]="i18n.t('bind.node')">{{ s.nodeId }}</span> }
              <span class="rel-cc">{{ s.contentCount | number }}</span>
            </div>
          }
          @if (rel.count > rel.items.length) {
            <div class="rel-more">+ {{ rel.count - rel.items.length }} {{ i18n.t('detail.related.andMore') }}</div>
          }
        </div>
      </section>
    }

    <!-- Beispiel-Inhalte -->
    <section class="sb">
      <h3><mat-icon>collections_bookmark</mat-icon> {{ i18n.t('detail.examples') }}@if (contentsTotal()) { <span class="sb-sub"> · {{ contentsTotal() | number }}</span> }</h3>
      @if (contents() === null) {
        <div class="ct-state"><mat-spinner diameter="22"></mat-spinner> {{ i18n.t('detail.contentLoading') }}</div>
      } @else if (contentsError()) {
        <div class="ct-state muted">{{ i18n.t('detail.contentError') }}</div>
      } @else if (contents()!.length) {
        <div class="ct-grid">
          @for (c of contents()!; track c.url) {
            <a class="ct-card" [href]="c.url" target="_blank" rel="noopener">
              <div class="ct-thumb">
                @if (c.previewUrl) { <img [src]="c.previewUrl" [alt]="c.title" loading="lazy"> }
                @else { <mat-icon>description</mat-icon> }
              </div>
              <div class="ct-body">
                <div class="ct-title">{{ c.title }}</div>
                @if (c.description) { <div class="ct-desc">{{ c.description }}</div> }
                @if (c.subjects.length) {
                  <div class="ct-chips">@for (s of c.subjects; track s) { <span class="ct-chip">{{ s }}</span> }</div>
                }
              </div>
            </a>
          }
        </div>
      } @else {
        <div class="ct-state muted">{{ i18n.t('detail.contentNone') }}</div>
      }
    </section>
  </mat-dialog-content>
  `,
  styles: [`
    :host { display: block; }
    .dh { display: flex; gap: 16px; padding: 16px 16px 8px; align-items: flex-start; }
    .dh-preview { width: 132px; height: 88px; border-radius: 10px; overflow: hidden; flex-shrink: 0; border: 1px solid var(--wlo-border); background: #e8eef7; }
    .dh-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .dh-init { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: 700; color: var(--wlo-primary); background: var(--wlo-primary-light); }
    .dh-info { flex: 1; min-width: 0; }
    .dh-name { margin: 0 0 8px !important; font-size: 19px; font-weight: 700; color: var(--wlo-text); line-height: 1.25; }
    .c-oer { --mdc-chip-elevated-container-color: #e6f4ea; --mdc-chip-label-text-color: #1a8a4d; font-weight: 700; }
    .db { padding: 0 16px 16px; display: flex; flex-direction: column; gap: 14px; background: var(--wlo-bg); }
    .count-bar { display: flex; align-items: center; gap: 10px; padding: 10px 14px; background: var(--wlo-primary-light); border-radius: 10px; flex-wrap: wrap; }
    .c-big { font-size: 24px; font-weight: 700; color: var(--wlo-primary); }
    .c-lbl { font-size: 13px; color: var(--wlo-primary); opacity: .85; }
    .spacer { flex: 1; }

    /* Titled card sections (mirrors the Quellensteckbriefe profile). */
    .sb { background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 12px; padding: 14px 16px; }
    .sb > h3 { display: flex; align-items: center; gap: 6px; margin: 0 0 12px; font-size: 14px; font-weight: 700; color: var(--wlo-primary); }
    .sb > h3 mat-icon { font-size: 18px; width: 18px; height: 18px; }
    .sb-sub { font-weight: 400; font-size: 12px; color: var(--wlo-text-muted); }
    .sb-hint { font-size: 12px; color: var(--wlo-text-muted); margin: -4px 0 10px; line-height: 1.45; }
    /* Related sources (Bezugsquelle family — publisher + its sub-channels) */
    /* Data-problem note: multiple datasets per Bezugsquelle are tracked in the audit protocol. */
    .rel-warn { display: flex; align-items: flex-start; gap: 5px; color: #aa6600; }
    .rel-warn mat-icon { font-size: 14px; width: 14px; height: 14px; margin-top: 1px; flex-shrink: 0; }
    .rel-list { display: flex; flex-direction: column; gap: 1px; }
    .rel-item { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 13px; }
    .rel-ic { font-size: 16px; width: 16px; height: 16px; color: #8aa0c0; flex-shrink: 0; }
    .rel-ic.node { color: #1a8a4d; }
    .rel-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--wlo-text); }
    /* Node-ID (Audit tier): the edu-sharing Quelldatensatz id, monospace + copy-selectable. */
    .rel-node { flex-shrink: 0; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: ui-monospace, Consolas, monospace; font-size: 10px; color: var(--wlo-text-muted); user-select: all; }
    .rel-cc { font-size: 11px; color: var(--wlo-text-muted); flex-shrink: 0; }
    .rel-more { font-size: 12px; color: var(--wlo-text-muted); font-style: italic; padding-top: 4px; }
    .sb.internal > h3 { color: #b3261e; }

    /* Key/value grid (label | value). */
    .kv { display: grid; grid-template-columns: 168px 1fr; gap: 6px 14px; font-size: 13px; align-items: start; }
    .kv .k { color: var(--wlo-text-muted); }
    .kv .v { color: var(--wlo-text); word-break: break-word; }
    .kv .v .muted { color: var(--wlo-text-muted); }
    .kv.remarks .v { white-space: pre-wrap; line-height: 1.5; }
    .kv.ki .v { max-height: 150px; overflow: auto; background: var(--wlo-bg); border: 1px solid var(--wlo-border); border-radius: 6px; padding: 4px 8px; white-space: pre-wrap; }
    @media (max-width: 560px) { .kv { grid-template-columns: 1fr; gap: 1px 0; } .kv .k { margin-top: 8px; font-weight: 600; } }
    .from-content { font-weight: 400; opacity: .8; }

    /* Provenance pill (team, tier 2) — palette mirrors the Quellensteckbriefe app. */
    .prov { display: inline-block; margin-left: 6px; font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 6px; background: #eef3fb; color: #4466aa; white-space: nowrap; vertical-align: middle; }
    .prov.api { color: #1a8a4d; background: #e7f7ee; }
    .prov.csv { color: #aa6600; background: #fff3e6; }
    .prov.facet { color: #2e6ca8; background: #eaf1fb; }
    .prov.other { color: #5b6b86; background: #eef2f8; }

    /* Quality groups. */
    .q-block { margin-bottom: 10px; }
    .q-block:last-child { margin-bottom: 0; }
    .q-lbl { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--wlo-text-muted); margin-bottom: 6px; }
    .q-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
    .q-card { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 10px 8px; border-radius: 10px; text-align: center; }
    .q-card mat-icon { font-size: 20px; width: 20px; height: 20px; }
    .q-card .q-clbl { font-size: 10px; line-height: 1.3; opacity: .85; }
    .q-card .q-cval { font-size: 11.5px; font-weight: 600; line-height: 1.3; }
    .q-card.q-good { background: var(--q-good-bg); color: var(--q-good-fg); }
    .q-card.q-neutral { background: var(--q-neutral-bg); color: var(--q-neutral-fg); }
    .q-card.q-bad { background: var(--q-bad-bg); color: var(--q-bad-fg); }
    .q-card.q-unknown { background: var(--q-unknown-bg); color: var(--q-unknown-fg); }

    /* Crawler field-generation table. */
    .sb-sub2 { font-size: 12px; font-weight: 600; color: var(--wlo-text-muted); margin: 12px 0 6px; padding-top: 8px; border-top: 1px dashed var(--wlo-border); }
    .fgtable { width: 100%; border-collapse: collapse; font-size: 12px; }
    .fgtable th, .fgtable td { text-align: left; padding: 4px 8px; border-bottom: 1px solid #eef2f8; vertical-align: top; }
    .fgtable th { color: var(--wlo-text-muted); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; }
    .fgtable .fg-how { color: #6b7a90; }
    .fgtable .fg-active { color: #1a8a4d; font-weight: 600; }

    /* Example content. */
    .ct-state { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--wlo-text-muted); padding: 6px 0; }
    .ct-state.muted { font-style: italic; }
    .ct-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; }
    .ct-card { display: flex; flex-direction: column; text-decoration: none; color: inherit; background: var(--wlo-card); border: 1px solid var(--wlo-border); border-radius: 12px; overflow: hidden; transition: border-color .15s, box-shadow .15s, transform .15s; }
    .ct-card:hover { border-color: var(--wlo-primary); box-shadow: 0 6px 18px rgba(0,59,124,.12); transform: translateY(-2px); }
    .ct-thumb { aspect-ratio: 16 / 9; background: #e8eef7; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    .ct-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .ct-thumb mat-icon { font-size: 32px; width: 32px; height: 32px; color: #9fb2cd; }
    .ct-body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 5px; }
    .ct-title { font-size: 13px; font-weight: 600; line-height: 1.35; color: var(--wlo-text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .ct-desc { font-size: 12px; line-height: 1.45; color: var(--wlo-text-muted); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .ct-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
    .ct-chip { font-size: 10px; padding: 2px 8px; border-radius: 20px; background: #eaf0f9; color: #003b7c; white-space: nowrap; }
  `],
})
export class DetailDialogComponent implements OnInit {
  private readonly api = inject(SourcesService);
  private readonly pdf = inject(PdfService);
  readonly detail = inject<SourceDetail>(MAT_DIALOG_DATA);
  readonly i18n = inject(I18n);
  readonly tiers = inject(TierService);

  readonly pdfBusy = signal(false);
  readonly contents = signal<ContentItem[] | null>(null);
  readonly contentsTotal = signal(0);
  readonly contentsError = signal(false);

  // Fall back to a representative example content when the source itself has none of its own
  // (node-less crawlers like YouTube / Bayerischer Rundfunk and pure Bezugsquellen).
  readonly effectivePreview = computed(() => this.detail.previewUrl || this.contents()?.[0]?.previewUrl || '');
  readonly effectiveDescription = computed(() => this.detail.description || this.contents()?.[0]?.description || '');
  readonly descFromContent = computed(() => !this.detail.description && !!this.contents()?.[0]?.description);
  readonly displayKeywords = computed(() => {
    if (this.detail.keywords.length) { return this.detail.keywords; }
    const seen = new Set<string>();
    const out: string[] = [];
    for (const c of this.contents() ?? []) {
      for (const k of c.keywords) {
        const key = k.toLowerCase();
        if (!seen.has(key)) { seen.add(key); out.push(k); }
        if (out.length >= 10) { return out; }
      }
    }
    return out;
  });
  readonly keywordsFromContent = computed(() => !this.detail.keywords.length && this.displayKeywords().length > 0);

  readonly qualityGroups = QUALITY_GROUPS;
  /** Crawler field-generation rows grouped by LOM item (computed once — the dialog data is static). */
  readonly fieldGenGroups: Array<{ item: string; fields: FieldGenItem[] }> = this.groupFieldGen();
  /** Internal fields split into labelled facts + remarks (tier 2; empty when not authorised). */
  readonly internalGroups: InternalGroups = groupInternal(this.detail.internal);

  get initial(): string {
    return (this.detail.name || '?').charAt(0).toUpperCase();
  }

  /** Host of the configured edu-sharing repo the data refers to (e.g. redaktion.openeduhub.net). */
  repoHost(): string {
    return this.tiers.repoUrl().replace(/^https?:\/\//, '');
  }

  hasQuality(): boolean {
    return this.qualityGroups.some((g) => this.groupEntries(g.keys).length > 0);
  }

  groupEntries(keys: string[]): QualityEntry[] {
    return qualityEntries(this.detail.quality, keys);
  }

  /** Keys of a flat tier-1/2 key-value object (ki) for template iteration. */
  keys(obj: Record<string, unknown> | undefined): string[] {
    return obj ? Object.keys(obj) : [];
  }

  /** Per-field data source for the provenance pill — team-only (tier 2). '' = none / not authorised. */
  prov(key: string): string {
    return this.detail.provenance?.[key] ?? '';
  }

  /** Colour class for a provenance pill, matching the Quellensteckbriefe palette (api/facet/csv). */
  provClass(p: string): string {
    const s = (p || '').toLowerCase();
    if (s.includes('facet')) return 'facet';
    if (s.includes('api')) return 'api';
    if (s.includes('csv') || s.includes('crawler')) return 'csv';
    return 'other';
  }

  private groupFieldGen(): Array<{ item: string; fields: FieldGenItem[] }> {
    const groups: Array<{ item: string; fields: FieldGenItem[] }> = [];
    const byItem = new Map<string, FieldGenItem[]>();
    for (const f of this.detail.fieldGeneration ?? []) {
      const item = f.item || '—';
      let fields = byItem.get(item);
      if (!fields) { fields = []; byItem.set(item, fields); groups.push({ item, fields }); }
      fields.push(f);
    }
    return groups;
  }

  /** Export THIS source as a single-source Steckbrief PDF (tier 1+), via the shared PdfService. */
  async exportPdf(): Promise<void> {
    if (this.pdfBusy()) return;
    this.pdfBusy.set(true);
    try {
      await this.pdf.generate([this.detail.id]);
    } finally {
      this.pdfBusy.set(false);
    }
  }

  ngOnInit(): void {
    this.api.contents(this.detail.id).subscribe({
      next: (r) => { this.contents.set(r.nodes); this.contentsTotal.set(r.total); },
      error: () => { this.contentsError.set(true); this.contents.set([]); },
    });
  }
}
