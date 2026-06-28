import { Component, OnInit, inject, signal } from '@angular/core';
import { MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { SourcesService } from './sources.service';
import { I18n } from './i18n.service';

/**
 * Audit report (team / tier 2): the data-problem protocol, fetched as Markdown from
 * /api/protokoll.md and shown in a large read-only text area so the team can read it in-app and
 * save (.md) or print it directly — without leaving the page. Team-gated server-side.
 */
@Component({
  selector: 'wlo-audit-report',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule],
  template: `
    <h2 mat-dialog-title class="ar-title"><mat-icon>fact_check</mat-icon> {{ i18n.t('audit.title') }}</h2>
    <mat-dialog-content class="ar-body">
      @if (loading()) {
        <div class="ar-state"><mat-spinner diameter="26"></mat-spinner> {{ i18n.t('audit.loading') }}</div>
      } @else if (error()) {
        <div class="ar-state muted">{{ i18n.t('audit.error') }}</div>
      } @else {
        <p class="ar-hint">{{ i18n.t('audit.hint') }}</p>
        <textarea class="ar-text" readonly [value]="text()" aria-label="Audit-Protokoll"></textarea>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>{{ i18n.t('action.close') }}</button>
      <button mat-stroked-button type="button" [disabled]="!text()" (click)="print()">
        <mat-icon>print</mat-icon> {{ i18n.t('audit.print') }}
      </button>
      <button mat-flat-button color="primary" type="button" [disabled]="!text()" (click)="download()">
        <mat-icon>download</mat-icon> {{ i18n.t('audit.save') }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .ar-title { display: flex; align-items: center; gap: 8px; color: var(--wlo-primary); }
    .ar-title mat-icon { color: #b3261e; }
    .ar-body { display: flex; flex-direction: column; width: 100%; box-sizing: border-box; }
    .ar-hint { font-size: 12px; color: var(--wlo-text-muted); margin: 0 0 8px; }
    .ar-state { display: flex; align-items: center; gap: 10px; padding: 32px; color: var(--wlo-text-muted); }
    .ar-state.muted { font-style: italic; }
    .ar-text { width: 100%; height: 60vh; resize: vertical; box-sizing: border-box; padding: 10px 12px;
      font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: 12px; line-height: 1.5;
      color: var(--wlo-text); background: var(--wlo-bg); border: 1px solid var(--wlo-border); border-radius: 8px; }
  `],
})
export class AuditReportComponent implements OnInit {
  private readonly api = inject(SourcesService);
  readonly i18n = inject(I18n);

  readonly text = signal('');
  readonly loading = signal(true);
  readonly error = signal(false);

  ngOnInit(): void {
    this.api.protokoll().subscribe({
      next: (md) => { this.text.set(md); this.loading.set(false); },
      error: () => { this.error.set(true); this.loading.set(false); },
    });
  }

  /** Save the protocol as a Markdown file (client-side blob download). */
  download(): void {
    const blob = new Blob([this.text()], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'audit-protokoll.md';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  /** Print the protocol via a throwaway window (textContent, so the report is never injected as HTML).
   * NOTE: the "noopener" window feature makes window.open() return null (which broke printing), so we
   * instead sever the back-reference (w.opener = null) right after opening — same protection, and we
   * keep the handle we need to print. The window is a blank, same-origin page we fully control. */
  print(): void {
    const w = window.open('', '_blank', 'width=900,height=700');
    if (!w) return;   // popup blocked
    try { w.opener = null; } catch { /* some engines disallow setting opener; harmless */ }
    const pre = w.document.createElement('pre');
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.fontFamily = 'ui-monospace, Consolas, monospace';
    pre.style.fontSize = '12px';
    pre.style.padding = '16px';
    pre.textContent = this.text();
    w.document.body.appendChild(pre);
    w.document.title = 'Audit-Protokoll';
    w.focus();
    // Let the new document lay out before printing (Firefox/Safari otherwise print blank).
    setTimeout(() => w.print(), 150);
  }
}
