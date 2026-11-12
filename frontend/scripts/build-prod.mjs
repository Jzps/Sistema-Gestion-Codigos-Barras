/**
 * SGCBP — Build de PRODUCCIÓN del frontend (sin dependencias externas).
 *
 * Pasos:
 *   1. Lee la variable de entorno API_URL y valida que sea una URL pública
 *      (no localhost, no vacía).
 *   2. Genera src/environments/environment.prod.ts con esa URL.
 *   3. Ejecuta `ng build --configuration production` (Angular sustituye
 *      environment.ts por environment.prod.ts vía fileReplacements).
 *   4. Verifica que el bundle NO contenga ninguna dirección localhost.
 *
 * Uso (en Render el build command es):
 *   cd frontend && npm ci && npm run build:prod
 *
 * En local, para una prueba:
 *   API_URL=https://mi-api.onrender.com npm run build:prod
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ENV_TARGET = join(ROOT, 'src', 'environments', 'environment.prod.ts');
const DIST_DIR = join(ROOT, 'dist', 'frontend', 'browser');

function fail(message) {
  console.error(`[sgcbp] ERROR: ${message}`);
  process.exit(1);
}

// --- 1. Validar API_URL -------------------------------------------------------
const rawUrl = (process.env.API_URL ?? '').trim();
if (!rawUrl) {
  fail(
    'falta la variable de entorno API_URL.\n' +
      '         Debe ser la URL publica de la API, sin barra final, por ejemplo:\n' +
      '           API_URL=https://sgcbp-api.onrender.com npm run build:prod',
  );
}

const apiUrl = rawUrl.replace(/\/+$/, '');
if (!/^https?:\/\/[^/\s]+/i.test(apiUrl)) {
  fail(`API_URL no es una URL valida: "${rawUrl}"`);
}
if (/localhost|127\.0\.0\.1|\[::1\]/i.test(apiUrl)) {
  fail(`API_URL no puede apuntar a localhost en produccion: "${rawUrl}"`);
}

// --- 2. Generar environment.prod.ts ------------------------------------------
const envFile = `// Generado por scripts/build-prod.mjs - NO editar a mano.
// La URL de la API viene de la variable de entorno API_URL.
export const environment = {
  production: true,
  apiUrl: '${apiUrl}/api',
};
`;
writeFileSync(ENV_TARGET, envFile, 'utf8');
console.log(`[sgcbp] environment.prod.ts generado (apiUrl=${apiUrl}/api)`);

// --- 3. Build de Angular ------------------------------------------------------
const build = spawnSync('ng build --configuration production', {
  cwd: ROOT,
  shell: true,
  stdio: 'inherit',
});
if (build.status !== 0) {
  fail('el build de Angular ha fallado');
}

// --- 4. Verificar que el bundle no lleva direcciones locales ------------------
function collectJsFiles(dir) {
  const found = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      found.push(...collectJsFiles(full));
    } else if (entry.endsWith('.js')) {
      found.push(full);
    }
  }
  return found;
}

let checked = 0;
for (const file of collectJsFiles(DIST_DIR)) {
  const content = readFileSync(file, 'utf8');
  checked += 1;
  if (/localhost|127\.0\.0\.1/.test(content)) {
    fail(`el bundle ${relative(ROOT, file)} contiene una direccion local`);
  }
}
console.log(`[sgcbp] Build de produccion correcto (${checked} bundles sin direcciones locales).`);
