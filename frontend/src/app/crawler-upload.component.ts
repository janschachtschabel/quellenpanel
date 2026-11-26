import { Component, EventEmitter, Output, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { I18n } from './i18n.service';
import { KorrekturenService } from './korrekturen.service';
import { CrawlerVorschau } from './models';
import { fehlertext } from './korrekturen-fehler';

/** Replace the crawler table: choose a CSV, see required columns and the effect per spider, replace. */
@Component({
  selector: 'wlo-crawler-upload',
  standalone: true,
  imports: [MatButtonModule, MatIconModule],
  template: `
  <p class="hint">{{ i18n.t('crawler.hint') }}</p>
  <input type="file" accept=".csv" (change)="datei($event)">
  @if (fehler()) { <p class="err" role="alert">{{ fehler() }}</p> }
  @if (vorschau(); as v) {
    @if (!v.ok) {
      <p class="err">{{ i18n.t('crawler.missing') }}: {{ v.fehlendePflicht.join(', ') }}</p>
    } @else {
      <p>{{ v.zeilen }} {{ i18n.t('korr.rows') }} ·
        <b>{{ v.spider.neu.length }}</b> {{ i18n.t('imp.new') }} ·
        <b>{{ v.spider.geaendert.length }}</b> {{ i18n.t('imp.changed') }} ·
        <b>{{ v.spider.gleich }}</b> {{ i18n.t('imp.same') }} ·
        <b class="err">{{ v.spider.entfallen.length }}</b> {{ i18n.t('imp.dropped') }}</p>
      @if (v.spider.neu.length) { <details><summary>{{ i18n.t('imp.new') }}</summary><ul>@for (s of v.spider.neu; track s) { <li>{{ s }}</li> }</ul></details> }
      @if (v.spider.geaendert.length) { <details><summary>{{ i18n.t('imp.changed') }}</summary><ul>@for (s of v.spider.geaendert; track s) { <li>{{ s }}</li> }</ul></details> }
      @if (v.spider.entfallen.length) { <details open><summary>{{ i18n.t('imp.dropped') }}</summary><ul>@for (s of v.spider.entfallen; track s) { <li>{{ s }}</li> }</ul></details> }
      <button mat-flat-button color="primary" type="button" [disabled]="busy()" (click)="ersetzen()">
        <mat-icon>upload</mat-icon> {{ i18n.t('crawler.replace') }}
      </button>
    }
  }
  @if (meldung()) { <p class="info" role="status">{{ meldung() }}</p> }
  `,
  styles: [`.err { color: #b00020; } .hint { color: #555; } .info { background: #e8f1fb; padding: 8px 12px; border-radius: 6px; }
    ul { max-height: 220px; overflow: auto; font-size: 13px; }`],
})
export class CrawlerUploadComponent {
  @Output() ersetzt = new EventEmitter<void>();
  readonly i18n = inject(I18n);
  private readonly svc = inject(KorrekturenService);
  readonly vorschau = signal<CrawlerVorschau | null>(null);
  readonly fehler = signal('');
  readonly meldung = signal('');
  readonly busy = signal(false);
  private file: File | null = null;

  datei(ev: Event): void {
    this.file = (ev.target as HTMLInputElement).files?.[0] ?? null;
    this.vorschau.set(null);
    this.fehler.set('');
    this.meldung.set('');
    if (!this.file) return;
    this.svc.crawlerVorschau(this.file).subscribe({ next: v => this.vorschau.set(v), error: e => this.fehler.set(fehlertext(e)) });
  }

  ersetzen(): void {
    if (!this.file) return;
    if (!this.svc.wer()) { this.fehler.set(this.i18n.t('korr.wer.missing')); return; }
    if (!confirm(this.i18n.t('crawler.confirm'))) return;
    this.busy.set(true);
    this.svc.crawlerErsetzen(this.file).subscribe({
      next: v => {
        this.busy.set(false);
        this.vorschau.set(null);
        this.meldung.set(this.i18n.t(v.anwenden?.wirktBeimNaechstenAufbau ? 'crawler.done.later' : 'crawler.done.now'));
        this.ersetzt.emit();
      },
      error: e => { this.busy.set(false); this.fehler.set(fehlertext(e)); },
    });
  }
}
