// Compilación centralizada de ARKIS AI LAB.
//
//   npm run build            entorno + frontend + validación de producción + backend (sintaxis
//                            siempre; verificación completa si las dependencias están instaladas)
//   npm run build:frontend   solo el frontend
//   npm run build:backend    solo el backend, verificación completa (obligatoria)
//   npm run build:netlify    build para Netlify  (exige VITE_API_URL https pública)
//   npm run build:vercel     build para Vercel   (exige VITE_API_URL https pública)
//
// Python no se "compila": se despliega como código fuente en el servicio que lo ejecuta.
// Aquí solo se valida que el backend es correcto y arranca.

import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = resolve(fileURLToPath(new URL('..', import.meta.url)));
const args = Object.fromEntries(process.argv.slice(2).map((a) => a.replace(/^--/, '').split('=')));
const plataforma = args.plataforma || 'local';
const solo = args.solo || 'todo';
const DESPLIEGUE = plataforma === 'netlify' || plataforma === 'vercel';

let pasoN = 0;
const paso = (t) => console.log(`\n[${++pasoN}] ${t}`);
const ok = (t) => console.log(`    ✓ ${t}`);
const aviso = (t) => console.log(`    ! ${t}`);
function fallar(t) {
  console.error(`\n✗ BUILD FALLIDO: ${t}\n`);
  process.exit(1);
}

function validarEntorno() {
  paso(`Entorno (plataforma: ${plataforma})`);
  const [mayor] = process.versions.node.split('.').map(Number);
  if (mayor < 18) fallar(`Node ${process.versions.node}: se necesita Node 18 o superior`);
  ok(`Node ${process.versions.node}`);
  if (!existsSync(join(RAIZ, 'node_modules', 'vite'))) fallar('Faltan dependencias del frontend: ejecuta npm install (o npm ci)');
  ok('dependencias del frontend instaladas');

  const url = (process.env.VITE_API_URL || '').trim();
  if (DESPLIEGUE) {
    if (!url) fallar(`VITE_API_URL es obligatoria en ${plataforma}: la URL pública del backend Python (https://...). Configúrala en las variables de entorno del proyecto.`);
    let u;
    try { u = new URL(url); } catch { fallar(`VITE_API_URL no es una URL válida: ${url}`); }
    if (u.protocol !== 'https:') fallar(`VITE_API_URL debe usar https en producción: ${url}`);
    if (['localhost', '127.0.0.1', '0.0.0.0'].includes(u.hostname)) fallar(`VITE_API_URL apunta a ${u.hostname}: en producción debe ser el dominio público del backend`);
    if (u.pathname !== '/' && u.pathname !== '') fallar('VITE_API_URL debe ser solo el origen del backend (sin /api ni otras rutas)');
    ok(`VITE_API_URL = ${u.origin}`);
  } else {
    ok(url ? `VITE_API_URL = ${url}` : 'VITE_API_URL vacía: rutas relativas /api (mismo dominio o proxy de desarrollo)');
  }
  for (const k of Object.keys(process.env)) {
    if (k.startsWith('VITE_') && /TOKEN|SECRET|KEY|PASS|CLAVE/i.test(k)) fallar(`${k}: las variables VITE_* se incrustan en el JavaScript público; nunca pongas secretos en ellas`);
  }
}

async function construirFrontend() {
  paso('Frontend (Vite)');
  const { build } = await import('vite');
  try {
    await build({ root: RAIZ, logLevel: 'warn' });
  } catch (e) {
    fallar(`Vite no pudo compilar: ${e.message}`);
  }
  ok('dist/ generado');

  paso('Validación de producción del frontend');
  const dist = join(RAIZ, 'dist');
  if (!existsSync(join(dist, 'index.html'))) fallar('dist/index.html no existe');
  const archivos = [];
  const recorrer = (d) => readdirSync(d).forEach((n) => { const p = join(d, n); statSync(p).isDirectory() ? recorrer(p) : archivos.push(p); });
  recorrer(dist);
  const js = archivos.filter((f) => /\.(js|html|css)$/.test(f));
  ok(`${archivos.length} archivos, ${js.length} de código`);
  const local = js.filter((f) => /\b(localhost|127\.0\.0\.1)\b/.test(readFileSync(f, 'utf8')));
  if (local.length) {
    const msg = `URL de localhost dentro del build: ${local.map((f) => f.replace(RAIZ, '')).join(', ')}`;
    if (DESPLIEGUE) fallar(msg); else aviso(msg);
  } else ok('sin URLs de localhost en el build');
  if (archivos.some((f) => /\.(py|env)$/.test(f))) fallar('dist/ contiene archivos de Python o .env');
  ok('sin archivos internos (.py, .env) en dist/');
}

function python() {
  for (const cmd of ['python3', 'python']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf8' });
    if (r.status === 0 && /Python 3/.test(r.stdout + r.stderr)) return cmd;
  }
  return null;
}

function verificarBackend(completo) {
  paso(`Backend Python (${completo === 'obligatorio' ? 'verificación completa' : 'validación'})`);
  const py = python();
  if (!py) {
    if (completo === 'obligatorio') fallar('No se encuentra Python 3 en este entorno');
    aviso('Python no disponible aquí: se omite la validación del backend (este proveedor solo publica el frontend).');
    return;
  }
  const sintaxis = spawnSync(py, ['-m', 'compileall', '-q', 'arkis_lab', 'run.py'], { cwd: RAIZ, encoding: 'utf8' });
  if (sintaxis.status !== 0) fallar(`Error de sintaxis en el backend:\n${sintaxis.stdout}${sintaxis.stderr}`);
  ok('sintaxis de arkis_lab/ correcta');

  const deps = spawnSync(py, ['-c', 'import fastapi, uvicorn, numpy, sklearn, skops'], { cwd: RAIZ });
  if (deps.status !== 0) {
    if (completo === 'obligatorio') fallar('Faltan dependencias de Python: pip install -r requirements.txt');
    aviso('Dependencias de Python no instaladas aquí: verificación de arranque omitida (se hace en el servicio que ejecuta el backend o con npm run build:backend).');
    return;
  }
  const env = { ...process.env };
  if (DESPLIEGUE) { delete env.APP_ENV; delete env.ARKIS_TOKEN; delete env.CORS_ORIGINS; }   // config del backend: vive en su propio servicio
  const v = spawnSync(py, ['-m', 'arkis_lab.servidor.verificar'], { cwd: RAIZ, encoding: 'utf8', env });
  const lineas = v.stdout.split(/\r?\n/).filter(Boolean);
  console.log(lineas.map((l) => `    ${l}`).join('\n'));
  if (v.status !== 0) fallar(`La verificación del backend falló:\n${v.stderr}`);
  ok('el backend se importa y responde');
}

const t0 = Date.now();
if (solo === 'backend') {
  verificarBackend('obligatorio');
} else {
  validarEntorno();
  await construirFrontend();
  if (solo !== 'frontend') verificarBackend('si_es_posible');
}
console.log(`\n✓ Build completado en ${((Date.now() - t0) / 1000).toFixed(1)} s (${plataforma}${solo !== 'todo' ? `, solo ${solo}` : ''})`);
if (DESPLIEGUE) console.log(`  Recuerda: ${plataforma} publica el frontend; el backend Python se ejecuta en su propio servicio (${process.env.VITE_API_URL}).`);
