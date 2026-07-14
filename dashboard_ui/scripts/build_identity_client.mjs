import { build } from 'esbuild';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
const dashboardDir = resolve(scriptDir, '..');

await build({
  entryPoints: [resolve(dashboardDir, 'assets/js/auth-entry.js')],
  outfile: resolve(dashboardDir, 'assets/js/identity-client.js'),
  bundle: true,
  format: 'iife',
  target: ['es2020'],
  minify: true,
  legalComments: 'none',
});
