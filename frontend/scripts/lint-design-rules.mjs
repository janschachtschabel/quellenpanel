#!/usr/bin/env node
// Kopie aus github.com/janschachtschabel/edu-sharing-11-ux-skills (build-components/scripts), unverändert.
// Prüft Angular-Komponentendateien (.scss, .html, .ts) auf Verstöße gegen die edu-sharing-DESIGN.md.
// Aufruf:  node lint-design-rules.mjs <datei-oder-ordner> [...]
// Ausgabe: datei:zeile  [FEHLER|WARNUNG] regel-id  Hinweis
// Exit-Code 1, wenn mindestens ein FEHLER gefunden wurde.
// Keine Abhängigkeiten; Node >= 18.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, extname, basename } from 'node:path';

// Dateien, in denen Farbwerte definiert werden DÜRFEN (Token-Quelle).
const TOKEN_SOURCES = new Set([
    'variables.scss',
    'variables-scss.scss',
    'variables-root.scss',
    'material-theme.scss',
    'branding.scss',
]);

const RULES = [
    {
        id: 'no-color-literal',
        level: 'FEHLER',
        ext: ['.scss', '.css', '.html'],
        // #rgb/#rrggbb/#rrggbbaa, rgb()/rgba()/hsl() mit Zahlen, benannte Grundfarben als Wert
        re: /(#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d|hsla?\(\s*\d|:\s*(white|black|red|blue|green|gray|grey)\s*[;!])/,
        skipLine: /^\s*(\/\/|\*|\/\*)|url\(|@include|\$[\w-]+\s*:\s*var\(/,
        msg: 'Farbliteral im Komponentencode. Nur var(--…) aus variables.scss verwenden; fehlt ein Token, in :root UND body.isDarkTheme ergänzen.',
    },
    {
        id: 'no-raw-palette',
        level: 'WARNUNG',
        ext: ['.scss', '.css', '.html'],
        re: /--palette-(primary|accent|warn)-(\d|A\d)/,
        msg: '--palette-*-X kippt im Dark Mode nicht. --primaryBackground50/100/300/700/900 bzw. --primaryForeground800/900 nehmen.',
    },
    {
        id: 'no-mat-icon',
        level: 'WARNUNG',
        ext: ['.html', '.ts'],
        re: /<mat-icon\b/,
        msg: 'Icons über die Direktive esIcon: <i esIcon="name"></i> (dekorativ) bzw. mit [aria]="true" (bedeutungstragend).',
    },
    {
        id: 'legacy-structural-directive',
        level: 'WARNUNG',
        ext: ['.html', '.ts'],
        re: /\*ngIf=|\*ngFor=|\[ngSwitch\]/,
        msg: 'Neue Templates nutzen @if / @for / @switch (Angular-Control-Flow).',
    },
    {
        id: 'legacy-mat-selector',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /\.mat-(form-field-(wrapper|label|outline|infix|flex|prefix|suffix|subscript)|tab-(label|labels|header(?!-)|body-wrapper)|flat-button|raised-button|stroked-button|radio-outer-circle|checkbox-(frame|background|inner)|chip(?!-)|select-(value|arrow|panel)|option(?!-)|tooltip|card(?!-)|list-item)\b/,
        msg: 'Selektor aus der Zeit vor MDC – greift unter Angular Material 21 nicht. .mat-mdc-*-Klassen oder --mat-*-Tokens verwenden.',
    },
    {
        id: 'no-font-family',
        level: 'FEHLER',
        ext: ['.scss', '.css'],
        re: /font-family\s*:(?![^;]*(inherit|monospace|var\())/,
        msg: 'Schriftart nicht im Komponentencode setzen; global gilt $primaryFontFamily (Open Sans) bzw. das Branding.',
    },
    {
        id: 'no-gradient-text-glass',
        level: 'FEHLER',
        ext: ['.scss', '.css'],
        re: /background-clip\s*:\s*text|-webkit-text-fill-color/,
        msg: 'Verlaufstext gehört nicht zum edu-sharing-Stil.',
    },
    {
        id: 'backdrop-blur',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /backdrop-filter/,
        msg: 'Unschärfe nur für Overlays (Mixin blurBackground()), nicht als Deko-Glassmorphism auf Kacheln/Flächen.',
    },
    {
        id: 'raw-box-shadow',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /box-shadow\s*:(?!\s*(none|var\(|inset 0 0 0 var))/,
        msg: 'Schatten über Mixins: materialShadow(), materialShadowSmall(), materialShadowMedium(), materialShadowBottom().',
    },
    {
        id: 'raw-radius',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /border-radius\s*:\s*(?!0\b|50%|var\(|inherit|unset)\d/,
        msg: 'Radius über Token: var(--borderRadiusCards) 20px, var(--borderRadiusButtons) 18px, var(--borderRadiusBadges) 10px.',
    },
    {
        id: 'off-scale-spacing',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        // padding/margin/gap mit px-Wert außerhalb der Skala 5/10/15/20/25/30/40 (0 und 1px erlaubt; 2px nur für Linien/Offsets, nicht für Abstände)
        test: (line) => {
            const allowed = new Set([0, 1, 5, 10, 15, 20, 25, 30, 40]);
            // jede Deklaration der Zeile prüfen (auch `.a { padding: …; margin: … }` in einer Zeile)
            return line.split(/[;{}]/).some((decl) => {
                const m = decl.match(/^\s*(padding|margin|gap|row-gap|column-gap)(-[a-z-]+)?\s*:\s*(.+)$/);
                return m && [...m[3].matchAll(/(-?\d+(?:\.\d+)?)px/g)].some((v) => !allowed.has(Math.abs(Number(v[1]))));
            });
        },
        msg: 'Abstand außerhalb der spacing-Skala (DESIGN.md): 5/10/15/20/25/30/40px, 2px nur für Linien/Offsets.',
    },
    {
        id: 'raw-breakpoint',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /@media[^{]*\(\s*(max|min)-width\s*:\s*\d+px/,
        msg: 'Breakpoints aus variables-scss: vars.$mobileTabSwitchWidth (900px), vars.$mobileWidth (700px), vars.$mobileWidthPortrait (400px).',
    },
    {
        id: 'focus-removed',
        level: 'WARNUNG',
        ext: ['.scss', '.css'],
        re: /outline\s*:\s*(none|0)\b/,
        msg: 'Fokus entfernt. Ersatz nötig: @include setGlobalKeyboardFocus() (bzw. setGlobalInsetFocus()).',
    },
    {
        id: 'img-without-alt',
        level: 'FEHLER',
        ext: ['.html'],
        re: /<img\b(?![^>]*\s(alt|\[alt\]|\[attr\.alt\])\s*=)[^>]*>/,
        msg: '<img> ohne alt. Dekorativ: alt="", sonst Text über translate-Pipe.',
    },
    {
        id: 'hardcoded-ui-text',
        level: 'WARNUNG',
        ext: ['.html'],
        // Text zwischen Tags mit mind. 2 Wörtern, ohne {{ }} – grober Hinweis auf fehlende Übersetzung
        re: />\s*[A-Za-zÄÖÜäöüß]{3,}\s+[A-Za-zÄÖÜäöüß]{2,}[^<{]*</,
        msg: 'Sichtbarer Text ohne Übersetzung. Schlüssel in src/assets/i18n/<bereich>/de.json + en.json anlegen, im Template | translate.',
    },
];

function collect(path, out) {
    const st = statSync(path);
    if (st.isDirectory()) {
        for (const name of readdirSync(path)) {
            if (name === 'node_modules' || name === 'fonts' || name.startsWith('.')) {
                continue;
            }
            collect(join(path, name), out);
        }
    } else if (['.scss', '.css', '.html', '.ts'].includes(extname(path))) {
        if (!path.endsWith('.spec.ts') && !path.endsWith('.stories.ts')) {
            out.push(path);
        }
    }
    return out;
}

const targets = process.argv.slice(2);
if (targets.length === 0) {
    console.error('Aufruf: node lint-design-rules.mjs <datei-oder-ordner> [...]');
    process.exit(2);
}

let errors = 0;
let warnings = 0;
for (const file of targets.flatMap((t) => collect(t, []))) {
    if (TOKEN_SOURCES.has(basename(file))) {
        continue;
    }
    const ext = extname(file);
    const lines = readFileSync(file, 'utf8').split(/\r?\n/);
    // CSS in <style>-Blöcken einer .html-Datei bzw. in styles: [`…`] einer .ts-Datei wie .css prüfen
    let inStyle = false;
    const styleLine = lines.map((line) => {
        const opens = ext === '.html' ? /<style\b/.test(line) : ext === '.ts' ? /styles\s*:\s*\[?\s*`/.test(line) : false;
        const closes = ext === '.html' ? /<\/style>/.test(line) : ext === '.ts' ? inStyle && /`/.test(line) && !opens : false;
        if (opens) {
            inStyle = true;
        }
        const result = inStyle && !opens;
        if (closes || (opens && (ext === '.html' ? /<\/style>/.test(line) : /`[^`]*`/.test(line)))) {
            inStyle = false;
        }
        return result;
    });
    lines.forEach((line, i) => {
        const lineExt = styleLine[i] ? '.css' : ext;
        for (const rule of RULES) {
            if (!rule.ext.includes(lineExt)) {
                continue;
            }
            if (rule.skipLine && rule.skipLine.test(line)) {
                continue;
            }
            if (rule.test ? rule.test(line) : rule.re.test(line)) {
                const isError = rule.level === 'FEHLER';
                isError ? errors++ : warnings++;
                const shown = file.split('\\').join('/');
                console.log(`${shown}:${i + 1}  [${rule.level}] ${rule.id}  ${rule.msg}`);
            }
        }
    });
    // Regeln über ganze Tags (auch mehrzeilig)
    if (ext === '.html') {
        const text = lines.join('\n');
        for (const m of text.matchAll(/<button\b[^>]*\bmat-(?:mini-)?(?:icon-button|fab)\b[^>]*>([\s\S]*?)<\/button>/g)) {
            const openTag = m[0].slice(0, m[0].indexOf('>') + 1);
            const labelOnButton = /\s(aria-label|\[aria-label\]|\[attr\.aria-label\]|aria-labelledby|\[attr\.aria-labelledby\])\s*=/.test(openTag);
            // Name über das Icon: esIcon mit [aria]="true" bzw. [altText] (cdk-visually-hidden)
            const labelViaIcon = /\[aria\]\s*=\s*"true"|\saria\s*=\s*"true"|\[altText\]\s*=|\saltText\s*=/.test(m[1]);
            // sichtbarer Text oder Übersetzung im Button (z. B. mat-fab extended)
            const visibleText = /\|\s*translate|>\s*[A-Za-zÄÖÜäöüß]{3,}/.test(m[1].replace(/<i\b[^>]*>[^<]*<\/i>/g, ''));
            if (labelOnButton || labelViaIcon || visibleText) {
                continue;
            }
            errors++;
            const line = text.slice(0, m.index).split('\n').length;
            const shown = file.split('\\').join('/');
            console.log(
                `${shown}:${line}  [FEHLER] icon-button-without-label  Icon-Button ohne zugänglichen Namen. [attr.aria-label]="'KEY' | translate" am <button> setzen (matTooltip ersetzt kein Label).`,
            );
        }
    }
}
console.log(`\n${errors} Fehler, ${warnings} Warnungen`);
process.exit(errors > 0 ? 1 : 0);
