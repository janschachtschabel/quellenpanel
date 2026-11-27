import { Component, inject, ChangeDetectionStrategy } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

import { I18n } from './i18n.service';

/** Short, optional help for the corrections area: collapsed by default (details/summary). */
@Component({
  selector: 'wlo-korrektur-hilfe',
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: true,
  imports: [MatIconModule],
  template: `
    <details class="hilfe">
      <summary><mat-icon aria-hidden="true">help_outline</mat-icon>{{ i18n.t('korr.help.title') }}</summary>
      <dl>
        <dt>node</dt><dd>{{ i18n.t('korr.help.node') }}</dd>
        <dt>bezugsquelle</dt><dd>{{ i18n.t('korr.help.bq') }}</dd>
        <dt>blacklist</dt><dd>{{ i18n.t('korr.help.blacklist') }}</dd>
        <dt>whitelist</dt><dd>{{ i18n.t('korr.help.whitelist') }}</dd>
        <dt>vermerk</dt><dd>{{ i18n.t('korr.help.vermerk') }}</dd>
        <dt>bezugsquelle_setzen</dt><dd>{{ i18n.t('korr.help.bqSetzen') }}</dd>
        <dt>spider_setzen</dt><dd>{{ i18n.t('korr.help.spiderSetzen') }}</dd>
        <dt>beschreibung</dt><dd>{{ i18n.t('korr.help.beschreibung') }}</dd>
        <dt>vorschaubild</dt><dd>{{ i18n.t('korr.help.vorschaubild') }}</dd>
      </dl>
      <p>{{ i18n.t('korr.help.mehrere') }}</p>
      <p>{{ i18n.t('korr.help.wirkung') }}</p>
    </details>
  `,
  styles: [`
    .hilfe { font-size: 13px; color: var(--textMain); background: var(--primaryBackground50); border-radius: 8px; padding: 8px 12px; }
    summary { cursor: pointer; display: flex; align-items: center; gap: 6px; font-weight: 600; color: var(--primaryText); }
    summary mat-icon { font-size: 18px; width: 18px; height: 18px; }
    dl { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px; margin: 10px 0 6px; }
    dt { font-family: ui-monospace, monospace; font-size: 12px; color: var(--primaryForeground800); }
    dd { margin: 0; }
    p { margin: 6px 0 0; }
  `],
})
export class KorrekturHilfeComponent {
  readonly i18n = inject(I18n);
}
