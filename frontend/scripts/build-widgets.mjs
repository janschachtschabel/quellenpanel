// Builds the light widget script and the iframe helper into dist-widgets/ (no framework).
import { build } from 'esbuild';
import { cpSync, mkdirSync, writeFileSync } from 'node:fs';

const out = 'dist-widgets';
mkdirSync(out, { recursive: true });
const common = { bundle: true, minify: true, format: 'iife', target: 'es2019', legalComments: 'none' };
await build({ ...common, entryPoints: ['src/widgets/widgets.ts'], outfile: `${out}/quellenpanel-widgets.js` });
await build({ ...common, entryPoints: ['src/widgets/embed-entry.ts'], outfile: `${out}/embed.js` });
writeFileSync(`${out}/embed.css`, 'html,body{margin:0;padding:0;background:transparent}body{padding:2px}\n');
cpSync('widgets-beispiele', `${out}/beispiele`, { recursive: true });
console.log('widgets built');
