import { Component } from '@angular/core';
import { MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

/**
 * Impressum (legal notice), shown in a Material dialog from the footer link — content taken
 * from the Quellensteckbriefe app (operator edu-sharing.net e.V., per wirlernenonline.de).
 */
@Component({
  selector: 'wlo-impressum',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
  <div class="lh">
    <h2 mat-dialog-title>Impressum</h2>
    <button mat-icon-button mat-dialog-close aria-label="Schließen"><mat-icon>close</mat-icon></button>
  </div>
  <mat-dialog-content class="legal">
    <p class="intro">Die Anwendung „Quellenverzeichnis" ist Teil von WirLernenOnline/WissenLebtOnline und wird vom edu-sharing.net e.V. betrieben. Es gilt das folgende Impressum.</p>

    <h3>1. Geltungsbereich</h3>
    <p>Dieses Impressum gilt für die Websites unter den Domains wirlernenonline.de und wirlernen.online und openeduhub.de.</p>

    <h3>2. Diensteanbieter</h3>
    <p><strong>Adresse / Anschrift</strong><br>edu-sharing.net e.V.<br>Am Horn 21a<br>99425 Weimar</p>
    <p><strong>Mailkontakt</strong> (bevorzugt):<br><a href="mailto:redaktion@wirlernenonline.de">redaktion&#64;wirlernenonline.de</a></p>
    <p><strong>Telefonkontakt</strong> (nur in Notfällen):<br>+49 (0) 3643 / 811 697</p>
    <p><strong>Anbieterkennzeichnung:</strong><br>Name des Dienstanbieters: edu-sharing.net e.V.<br>Rechtsform: gemeinnütziger Verein, Amtsgericht Weimar VR 131198<br>Vertretungsberechtigter Vorstand: Prof. Dr. Christian Erfurth, Stellvertreter: Annett Zobel<br>Steuernummer: 162 / 141 / 16077, zuständiges Finanzamt: Jena</p>

    <h3>3. Verantwortlich für die Inhalte § 55 Abs. 2 RStV</h3>
    <p>Prof. Dr. Christian Erfurth, Annett Zobel<br>Anschrift und Kontaktdaten siehe 2.</p>

    <h3>4. Haftung</h3>
    <p>Als Diensteanbieter ist der edu-sharing.net e.V. gemäß § 7 TMG für eigene Informationen, die sie zur Nutzung bereithält, nach den allgemeinen Gesetzen verantwortlich. Dementsprechend besteht keine Verantwortung für die von anderen Anbietern bereitgestellten Inhalte, insbesondere solche, auf die mittels Hyperlinks verwiesen wird.</p>
    <p>Wir prüfen verlinkte Seiten zum Zeitpunkt der Verlinkung auf mögliche Rechtsverstöße und erklären, dass dabei keine rechtswidrigen Inhalte erkennbar waren.</p>
    <p>Da eine permanente, anlasslose Kontrolle der verlinkten Seiten nicht zumutbar ist, bitten wir um entsprechende Mitteilung, falls von unserem Angebot aus verlinkte Seiten aus fachlichen oder rechtlichen Gründen Anlass zur Beanstandung geben. Wir werden derartige Links bei Bekanntwerden unverzüglich entfernen.</p>

    <h3>5. Urheberrecht / Lizenz</h3>
    <p>Die Inhalte auf den genannten Websites, die durch den Diensteanbieter erstellt worden sind, stehen unter der Creative-Commons-Lizenz CC BY 4.0. Sollten für Inhalte Dritter, die auf diesen Websites veröffentlicht sind, andere Regelungen gelten, werden sie auf der jeweiligen Seite angezeigt.</p>

    <h3>6. Widerspruch Werbe-Mails</h3>
    <p>Der Nutzung von im Rahmen der Impressumspflicht veröffentlichten Kontaktdaten zur Übersendung von nicht ausdrücklich angeforderter Werbung und Informationsmaterialien wird hiermit widersprochen. Die Betreiber der Seiten behalten sich ausdrücklich rechtliche Schritte im Falle der unverlangten Zusendung von Werbeinformationen, etwa durch Spam-E-Mails, vor.</p>

    <p class="src">Übernommen vom Impressum unter <a href="https://wirlernenonline.de/impressum/" target="_blank" rel="noopener">wirlernenonline.de/impressum/</a>.</p>
  </mat-dialog-content>
  `,
  styles: [`
    .lh { display: flex; align-items: center; justify-content: space-between; padding: 8px 16px 0; }
    .lh h2 { margin: 0 !important; font-size: 18px; font-weight: 700; color: var(--wlo-text); }
    .legal { padding: 0 16px 16px; color: var(--wlo-text); }
    .legal h3 { font-size: 14px; font-weight: 700; margin: 18px 0 4px; color: var(--wlo-primary); }
    .legal p { font-size: 13px; line-height: 1.55; margin: 0 0 8px; }
    .legal .intro { color: var(--wlo-text-muted); }
    .legal .src { margin-top: 16px; font-size: 12px; color: var(--wlo-text-muted); }
    .legal a { color: var(--wlo-primary); }
  `],
})
export class ImpressumDialogComponent {}
