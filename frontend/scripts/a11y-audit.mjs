#!/usr/bin/env node
// A11y-Audit (WCAG 2.1 AA + Zielgröße 2.2) mit axe-core über alle Ansichten des Quellenpanels.
// Aufruf:  node scripts/a11y-audit.mjs <basis-url> [--team-pw <passwort>] [--out <datei.json>] [--primary #rrggbb]
//   --primary prüft mit einer anderen Markenfarbe (ersetzt branding in /api/capabilities).
// Braucht Playwright (im Container vorinstalliert) und axe-core (devDependency).
// Exit-Code 1 bei Verstößen der Stufe serious/critical.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const AXE = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');

const args = process.argv.slice(2);
const base = (args[0] || 'http://127.0.0.1:18080').replace(/\/$/, '');
const opt = (n) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : undefined; };
const teamPw = opt('--team-pw');
const out = opt('--out');
const primary = opt('--primary');
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function pruefen(page, name) {
  await page.addScriptTag({ content: AXE });
  const r = await page.evaluate(async (tags) => {
    // eslint-disable-next-line no-undef
    const res = await axe.run(document, { runOnly: { type: 'tag', values: tags } });
    return res.violations.map(v => ({ id: v.id, impact: v.impact, help: v.help,
      nodes: v.nodes.slice(0, 5).map(n => ({ target: n.target.join(' '), summary: n.failureSummary?.split('\n').slice(0, 3).join(' ') })),
      count: v.nodes.length }));
  }, TAGS);
  return { name, violations: r };
}

async function toggle(page, text) {
  await page.locator('mat-button-toggle', { hasText: text }).first().click();
  await page.waitForTimeout(2000);
}

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
if (teamPw) {
  const r = await ctx.request.post(`${base}/api/auth`, { headers: { 'x-team-password': teamPw } });
  if (!r.ok()) console.error('Team-Login fehlgeschlagen:', r.status());
}
if (primary) {
  await ctx.route('**/api/capabilities', async (route) => {
    const r = await route.fetch();
    const j = await r.json();
    await route.fulfill({ response: r, json: { ...j, branding: { ...(j.branding || {}), primary } } });
  });
}
const page = await ctx.newPage();
const ergebnisse = [];
await page.goto(base + '/');
await page.waitForTimeout(4000);
ergebnisse.push(await pruefen(page, 'Kacheln (Basis)'));
await toggle(page, 'Liste');
ergebnisse.push(await pruefen(page, 'Liste (Basis)'));
await toggle(page, 'Statistiken');
ergebnisse.push(await pruefen(page, 'Statistiken (Basis)'));
await toggle(page, 'Kacheln');
await toggle(page, 'Details');
ergebnisse.push(await pruefen(page, 'Kacheln (Details)'));
await page.locator('wlo-tiles button.open').first().click();
await page.waitForTimeout(3000);
ergebnisse.push(await pruefen(page, 'Steckbrief (Details)'));
await page.keyboard.press('Escape');
await page.waitForTimeout(800);
if (teamPw) {
  await toggle(page, 'Audit');
  ergebnisse.push(await pruefen(page, 'Kacheln (Audit)'));
  await toggle(page, 'Korrekturen');
  ergebnisse.push(await pruefen(page, 'Korrekturen (Audit)'));
}
const mobil = await ctx.newPage();
await mobil.setViewportSize({ width: 375, height: 800 });
await mobil.goto(base + '/');
await mobil.waitForTimeout(4000);
ergebnisse.push(await pruefen(mobil, 'Kacheln mobil (375px)'));
await browser.close();

let schwer = 0;
for (const e of ergebnisse) {
  console.log(`\n## ${e.name}: ${e.violations.length ? e.violations.length + ' Regel(n) verletzt' : 'keine Verstöße'}`);
  for (const v of e.violations) {
    if (v.impact === 'serious' || v.impact === 'critical') schwer++;
    console.log(`- [${v.impact}] ${v.id} (${v.count}×): ${v.help}`);
    for (const n of v.nodes) console.log(`    ${n.target}  — ${n.summary ?? ''}`);
  }
}
if (out) writeFileSync(out, JSON.stringify(ergebnisse, null, 2));
console.log(`\nSchwere Verstöße (serious/critical): ${schwer}`);
process.exit(schwer ? 1 : 0);
