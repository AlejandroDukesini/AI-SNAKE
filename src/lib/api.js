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

/* Error con su categoría, para que la interfaz distinga los casos. */
export class ErrorApi extends Error {
  constructor(mensaje, tipo, estado) { super(mensaje); this.tipo = tipo; this.estado = estado; }
}

const TRANSITORIOS = [502, 503, 504];      // típicos de un servidor que está arrancando
const dormir = (ms) => new Promise((r) => setTimeout(r, ms));

async function intento(metodo, ruta, cuerpo, tiempo) {
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
    throw e.name === 'AbortError'
      ? new ErrorApi('El servidor tardó demasiado en responder.', 'tiempo')
      : new ErrorApi('No se pudo conectar con el servidor del laboratorio.', 'conexion');
  } finally {
    clearTimeout(temporizador);
  }
  if (r.status === 204) return null;
  const tipo = r.headers.get('content-type') || '';
  if (!r.ok) {
    if (TRANSITORIOS.includes(r.status)) {
      throw new ErrorApi('El servidor no está disponible en este momento (puede estar arrancando).', 'no_disponible', r.status);
    }
    let msg = r.status === 401 ? 'Esta acción necesita la clave del laboratorio (arriba a la derecha).'
      : r.status >= 500 ? 'Error interno del servidor.' : `Error ${r.status}`;
    if (tipo.includes('application/json') && r.status < 500) {
      try {
        const j = await r.json();
        if (j.detail && r.status !== 401) msg = typeof j.detail === 'string' ? j.detail : 'Datos no válidos';
      } catch { /* cuerpo ilegible */ }
    }
    throw new ErrorApi(msg, 'http', r.status);
  }
  if (tipo.includes('application/json')) {
    try { return await r.json(); } catch { throw new ErrorApi('El servidor envió una respuesta JSON inválida.', 'formato', r.status); }
  }
  if (tipo.includes('application/zip') || tipo.includes('octet-stream')) return r.blob();
  throw new ErrorApi('Respuesta inesperada del servidor (no es JSON).', 'formato', r.status);
}

/* GET es idempotente: se reintenta un número LIMITADO de veces si falla la conexión o el
   servidor responde 502/503/504 (por ejemplo, mientras Render lo despierta). POST, PATCH y
   DELETE nunca se reintentan solos: podrían duplicar una acción. */
async function pedir(metodo, ruta, cuerpo, tiempo = TIEMPO_MAXIMO_MS, reintentos = metodo === 'GET' ? 2 : 0) {
  for (let i = 0; ; i++) {
    try {
      return await intento(metodo, ruta, cuerpo, tiempo);
    } catch (e) {
      const transitorio = e instanceof ErrorApi && ['conexion', 'no_disponible'].includes(e.tipo);
      if (!transitorio || i >= reintentos) throw e;
      await dormir(1500 * (i + 1));
    }
  }
}

/* Arranque en frío: espera a que el backend responda en /api/health, con un tope de tiempo,
   informando del estado. Estados: conectando → despertando → listo | no_disponible |
   sin_conexion | tiempo_agotado. */
export async function esperarServidor(alCambiar, { tope = 90_000 } = {}) {
  const inicio = Date.now();
  alCambiar({ estado: 'conectando', segundos: 0 });
  let ultimo = null;
  while (Date.now() - inicio < tope) {
    try {
      await intento('GET', '/api/health', undefined, 15_000);
      alCambiar({ estado: 'listo', segundos: Math.round((Date.now() - inicio) / 1000) });
      return true;
    } catch (e) {
      ultimo = e;
      const segundos = Math.round((Date.now() - inicio) / 1000);
      alCambiar({ estado: segundos >= 3 ? 'despertando' : 'conectando', segundos, error: e.message });
      await dormir(Math.min(5000, 1000 + segundos * 100));
    }
  }
  const tipo = ultimo?.tipo;
  alCambiar({
    estado: tipo === 'no_disponible' ? 'no_disponible' : tipo === 'tiempo' ? 'tiempo_agotado' : 'sin_conexion',
    segundos: Math.round((Date.now() - inicio) / 1000), error: ultimo?.message,
  });
  return false;
}

export const api = {
  get: (ruta) => pedir('GET', ruta),
  getSinReintentos: (ruta) => pedir('GET', ruta, undefined, TIEMPO_MAXIMO_MS, 0),
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
