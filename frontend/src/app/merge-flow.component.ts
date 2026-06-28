import { Component, inject, signal } from '@angular/core';
import { I18n } from './i18n.service';

/**
 * Interactive SVG process-flow diagram (team view) explaining HOW the data-truth engine merges its
 * inputs into one unified source record. The six stages mirror the backend build (truth.py): load →
 * join (the 3-way Spider ↔ Bezugsquelle ↔ Quelldatensatz core) → aggregate → enrich → classify →
 * output. Click a phase to read its details below. Labels + descriptions are co-located here in
 * DE/EN (domain text, kept out of the global i18n dict — same convention as data-problem-filters.ts).
 */
interface Stage {
  n: number; de: string; en: string; subDe: string; subEn: string;
  detailDe: string; detailEn: string;
}

const STAGES: Stage[] = [
  {
    n: 1, de: 'Laden', en: 'Load', subDe: 'Knoten · CSV · Facetten · Korrekturen', subEn: 'nodes · CSV · facets · corrections',
    detailDe: 'Die Engine liest alle Eingaben ein: edu-sharing-Knoten (Titel, Beschreibung, Fächer, Bildungsstufen, Lizenz, Vorschaubild, Qualitätsmerkmale), die Crawler-Tabelle datencrawler.csv (Spider-Namen, robots.txt/TDM §44b/AGB/Lizenz-Check, Feldgenerierung), die Bezugsquellen- und Spider-Facetten (Inhaltszahlen), die Korrekturliste (Blacklist/Whitelist) und ein Vokabular für Alt-Spider. Daraus werden Indizes nach Spider-Name und Node-ID aufgebaut.',
    detailEn: 'The engine reads every input: edu-sharing nodes (title, description, subjects, levels, licence, preview, quality), the crawler table datencrawler.csv (spider names, robots.txt/TDM §44b/terms/licence-check, field generation), the publisher and spider facets (content counts), the correction list (blacklist/whitelist) and a vocabulary for legacy spiders. It then builds indexes by spider name and node id.',
  },
  {
    n: 2, de: 'Verknüpfen', en: 'Join', subDe: 'Spider ↔ Bezugsquelle ↔ Quelldatensatz', subEn: 'spider ↔ Bezugsquelle ↔ source dataset',
    detailDe: 'Der Kern: Für jeden Spider wird ein passender Quelldatensatz (Knoten) gesucht und die Bezugsquelle (Publisher) bestimmt. Schlüssel sind Spider-Name, Publisher-Feld und Node-ID. Bei Konflikten gilt eine feste Reihenfolge (Precedence): dominanter Publisher der gecrawlten Inhalte > Eintrag aus datencrawler.csv > Publisher des Knotens. So verschmelzen drei Quellen zu EINEM Datensatz.',
    detailEn: 'The core: for each spider a matching source dataset (node) is found and the Bezugsquelle (publisher) is determined. The keys are spider name, publisher field and node id. Conflicts follow a fixed precedence: dominant publisher of the crawled content > entry from datencrawler.csv > the node’s publisher. Three inputs thus merge into ONE record.',
  },
  {
    n: 3, de: 'Aggregieren', en: 'Aggregate', subDe: 'Restknoten & Facetten-Bezugsquellen', subEn: 'orphan nodes & facet publishers',
    detailDe: 'Knoten, die noch keinem Spider zugeordnet sind, werden als eigene Quelldatensätze ergänzt (primär oder als Zweit-Datensatz derselben Bezugsquelle). Bezugsquellen, die nur als Facette existieren (Inhalte, aber kein Datensatz), werden als eigene Einträge erfasst — so geht keine Quelle verloren und nichts wird doppelt gezählt.',
    detailEn: 'Nodes not yet claimed by a spider are added as their own source datasets (primary, or as a secondary dataset of the same publisher). Publishers that exist only as a facet (content but no dataset) are captured as their own entries — so no source is lost and nothing is double-counted.',
  },
  {
    n: 4, de: 'Anreichern', en: 'Enrich', subDe: 'Public/Internal · Provenance', subEn: 'public/internal · provenance',
    detailDe: 'Jeder Datensatz wird mit Feldern gefüllt und in öffentlich / intern getrennt (field_policy ist die eine Wahrheit dafür). Pro Feld wird die Herkunft vermerkt (Provenance: WLO-API, datencrawler.csv, Facette …), dazu Qualitätsmerkmale und die Feldgenerierung des Crawlers.',
    detailEn: 'Every record is filled and split into public / internal (field_policy is the single source of truth for that). Each field records its origin (provenance: WLO-API, datencrawler.csv, facet …), plus quality attributes and the crawler’s field generation.',
  },
  {
    n: 5, de: 'Klassifizieren', en: 'Classify', subDe: 'Marker · Datenprobleme', subEn: 'markers · data problems',
    detailDe: 'Marker und Datenprobleme werden gesetzt: Provenienz (Migration, Alt-Bindung), Sub-Channel-Erkennung (z. B. „YouTube – Mathematrick" unter „YouTube"), Zweit-Datensätze, dünne Metadaten, Dubletten-Verdacht sowie Status- und Publikations-Probleme. Diese Flags treiben Team-Filter, Protokoll und Statistik.',
    detailEn: 'Markers and data problems are set: provenance (migration, legacy binding), sub-channel detection (e.g. "YouTube – Mathematrick" under "YouTube"), secondary datasets, thin metadata, suspected duplicates and status/publication issues. These flags drive the team filter, the protocol and the statistics.',
  },
  {
    n: 6, de: 'Ausgabe', en: 'Output', subDe: 'sortiert → truth.json', subEn: 'sorted → truth.json',
    detailDe: 'Die Datensätze werden nach Inhaltsanzahl sortiert, Kennzahlen (Gesamtzahlen, Verteilung nach Art der Quelle) zusammengefasst und atomar nach data/truth.json geschrieben — die Datengrundlage, die diese App in allen drei Stufen ausliefert.',
    detailEn: 'The records are sorted by content count, key figures (totals, distribution by source type) are summarised and written atomically to data/truth.json — the data foundation this app serves across all three tiers.',
  },
];

const STEP = 157;   // horizontal distance between stage boxes
const X0 = 8;       // x of the first box

@Component({
  selector: 'wlo-merge-flow',
  standalone: true,
  template: `
    <p class="mf-intro">{{ i18n.lang() === 'de' ? 'Phase anklicken für Details:' : 'Click a phase for details:' }}</p>
    <svg viewBox="0 0 945 150" class="mf" role="img" [attr.aria-label]="i18n.lang() === 'de' ? 'Datenfluss der Engine' : 'Engine data flow'">
      <defs>
        <marker id="mf-ah" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" class="mf-ahf"></path>
        </marker>
      </defs>
      @for (a of arrows; track a) { <path [attr.d]="a" class="mf-arrow"></path> }
      @for (s of stages; track s.n) {
        <g class="mf-g" [class.sel]="selected() === s.n" (click)="select(s.n)" (keydown.enter)="select(s.n)"
           tabindex="0" role="button" [attr.aria-pressed]="selected() === s.n">
          <rect [attr.x]="s.x" y="24" width="140" height="74" rx="11" class="mf-rect"></rect>
          <circle [attr.cx]="s.x + 20" cy="61" r="13" class="mf-num"></circle>
          <text [attr.x]="s.x + 20" y="65" class="mf-numt">{{ s.n }}</text>
          <foreignObject [attr.x]="s.x + 38" y="26" width="98" height="70">
            <div xmlns="http://www.w3.org/1999/xhtml" class="mf-inner">
              <div class="mf-t">{{ i18n.lang() === 'de' ? s.de : s.en }}</div>
              <div class="mf-s">{{ i18n.lang() === 'de' ? s.subDe : s.subEn }}</div>
            </div>
          </foreignObject>
        </g>
      }
    </svg>
    @if (current(); as c) {
      <div class="mf-detail">
        <div class="mf-detail-h"><span class="mf-detail-n">{{ c.n }}</span>{{ i18n.lang() === 'de' ? c.de : c.en }}</div>
        <p class="mf-detail-t">{{ i18n.lang() === 'de' ? c.detailDe : c.detailEn }}</p>
      </div>
    }
  `,
  styles: [`
    :host { display: block; }
    .mf-intro { font-size: 12px; color: var(--wlo-text-muted); margin: 0 0 6px; }
    .mf { width: 100%; height: auto; display: block; }
    .mf-g { cursor: pointer; }
    .mf-g:focus-visible { outline: none; }
    .mf-g:focus-visible .mf-rect { stroke: var(--wlo-primary); stroke-width: 2; }
    .mf-rect { fill: var(--wlo-card); stroke: var(--wlo-border); stroke-width: 1.2; transition: fill .15s, stroke .15s; }
    .mf-g:hover .mf-rect { stroke: var(--wlo-primary); }
    /* ONLY the selected phase is highlighted — no permanent accent that could look "stuck". */
    .mf-g.sel .mf-rect { stroke: var(--wlo-primary); stroke-width: 2.6; fill: var(--wlo-primary-light); }
    .mf-num { fill: #8aa0c0; }
    .mf-g.sel .mf-num { fill: var(--wlo-primary); }
    .mf-numt { fill: #fff; font-size: 12px; font-weight: 700; text-anchor: middle; }
    /* foreignObject content — flows + wraps like normal HTML */
    .mf-inner { height: 70px; display: flex; flex-direction: column; justify-content: center; font-family: inherit; pointer-events: none; }
    .mf-t { font-size: 12px; font-weight: 700; color: var(--wlo-text); line-height: 1.15; }
    .mf-s { font-size: 9.5px; color: var(--wlo-text-muted); line-height: 1.12; margin-top: 3px; }
    .mf-arrow { stroke: #8aa0c0; stroke-width: 1.6; fill: none; marker-end: url(#mf-ah); }
    .mf-ahf { fill: #8aa0c0; }
    .mf-detail { margin-top: 12px; background: var(--wlo-bg); border: 1px solid var(--wlo-border); border-left: 3px solid var(--wlo-primary); border-radius: 8px; padding: 12px 16px; }
    .mf-detail-h { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 700; color: var(--wlo-text); }
    .mf-detail-n { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; background: var(--wlo-primary); color: #fff; font-size: 12px; flex-shrink: 0; }
    .mf-detail-t { font-size: 13px; color: var(--wlo-text); line-height: 1.55; margin: 8px 0 0; }
  `],
})
export class MergeFlowComponent {
  readonly i18n = inject(I18n);
  readonly stages = STAGES.map((s, i) => ({ ...s, x: X0 + i * STEP }));
  /** Selected phase — starts on the join (the key 3-way step), so details show immediately. */
  readonly selected = signal(2);
  /** Connector arrows between consecutive boxes (right edge → next left edge). */
  readonly arrows = STAGES.slice(0, -1).map((_, i) => {
    const x1 = X0 + i * STEP + 140;
    const x2 = X0 + (i + 1) * STEP - 2;
    return `M ${x1} 61 L ${x2} 61`;
  });

  select(n: number): void {
    this.selected.set(n);
  }

  current(): Stage | undefined {
    return STAGES.find((s) => s.n === this.selected());
  }
}
