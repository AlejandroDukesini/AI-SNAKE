/* Cliente HTTP único del laboratorio: ningún componente llama a fetch directamente.

   URL base (VITE_API_URL, se fija al compilar):
   - vacía  → rutas relativas /api/… (desarrollo con el proxy de Vite, o el contenedor
              que sirve web y API en el mismo dominio);
   - https://… → backend en otro dominio (frontend en Netlify o Vercel). El backend
              debe incluir ese dominio en CORS_ORIGINS.
   La clave de escritura NO va en el build: la escribe el usuario y se guarda solo en su
   navegador. */

export const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '');
const TIEMPO_MAXIMO_MS = 30_000;
const CLAVE_TOKEN = 'ia-snake:token';

export function leerToken() {
  try { return localStorage.getItem(CLAVE_TOKEN) || ''; } catch { return ''; }
}

export function guardarToken(t) {
  try { if (t) localStorage.setItem(CLAVE_TOKEN, t); else localStorage.removeItem(CLAVE_TOKEN); } catch { /* sin almacenamiento */ }
}

async function pedir(metodo, ruta, cuerpo, tiempo = TIEMPO_MAXIMO_MS) {
  const headers = {};
  if (cuerpo !== undefined) headers['Content-Type'] = 'application/json';
  const token = leerToken();
  if (token) headers['X-IA-Snake-Token'] = token;
  const control = new AbortController();
  const temporizador = setTimeout(() => control.abort(), tiempo);
  let r;
  try {
    r = await fetch(API_URL + ruta, {
      method: metodo, headers, signal: control.signal,
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    });
  } catch (e) {
    throw new Error(e.name === 'AbortError'
      ? 'El servidor tardó demasiado en responder.'
      : 'No se pudo conectar con el servidor del laboratorio.');
  } finally {
    clearTimeout(temporizador);
  }
  const tipo = r.headers.get('content-type') || '';
  if (!r.ok) {
    let msg = r.status === 401 ? 'Esta acción necesita la clave del laboratorio (arriba a la derecha).' : `Error ${r.status}`;
    if (tipo.includes('application/json')) {
      try {
        const j = await r.json();
        if (j.detail && r.status !== 401) msg = typeof j.detail === 'string' ? j.detail : 'Datos no válidos';
      } catch { /* cuerpo ilegible */ }
    }
    throw new Error(msg);
  }
  if (tipo.includes('application/json')) return r.json();
  if (tipo.includes('application/zip') || tipo.includes('octet-stream')) return r.blob();
  throw new Error('Respuesta inesperada del servidor (no es JSON).');
}

export const api = {
  get: (ruta) => pedir('GET', ruta),
  post: (ruta, cuerpo = {}, tiempo) => pedir('POST', ruta, cuerpo, tiempo),
  patch: (ruta, cuerpo) => pedir('PATCH', ruta, cuerpo),
  del: (ruta) => pedir('DELETE', ruta),
};

export async function descargar(ruta, nombre) {
  const blob = await api.get(ruta);
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: nombre });
  a.click();
  URL.revokeObjectURL(url);
}

export function archivoABase64(archivo) {
  return new Promise((ok, mal) => {
    const lector = new FileReader();
    lector.onload = () => ok(String(lector.result).split(',')[1]);
    lector.onerror = mal;
    lector.readAsDataURL(archivo);
  });
}

export const FLECHA = { arriba: '↑', abajo: '↓', izquierda: '←', derecha: '→' };
export const ACCIONES = ['arriba', 'abajo', 'izquierda', 'derecha'];
export const TECLAS = {
  ArrowUp: 'arriba', ArrowDown: 'abajo', ArrowLeft: 'izquierda', ArrowRight: 'derecha',
  w: 'arriba', s: 'abajo', a: 'izquierda', d: 'derecha',
};

export const ESTADOS = {
  sin_entrenar: 'Sin entrenar', entrenado: 'Entrenado', evaluado: 'Evaluado',
  validado: 'Validado', preentrenado: 'Preentrenado', experimentacion: 'En experimentación',
  pendiente: 'Pendiente (Etapa 5)',
};

export const DIFICULTADES = { facil: 'Fácil 4×4', medio: 'Medio 8×8', dificil: 'Difícil 16×16' };

export function fmt(v, dec = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return typeof v === 'number' ? v.toLocaleString('es', { maximumFractionDigits: dec }) : String(v);
}

export function pct(v, dec = 1) {
  return v === null || v === undefined ? '—' : `${(v * 100).toLocaleString('es', { maximumFractionDigits: dec })} %`;
}
