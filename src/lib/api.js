/* Cliente del servidor del laboratorio. Rutas relativas: en desarrollo Vite hace de
   proxy hacia el puerto 8000; en producción el mismo servidor sirve la web. */

async function pedir(metodo, ruta, cuerpo) {
  const r = await fetch(ruta, {
    method: metodo,
    headers: cuerpo !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); msg = j.detail ? (typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)) : msg; } catch { /* sin cuerpo */ }
    throw new Error(msg);
  }
  const tipo = r.headers.get('content-type') || '';
  return tipo.includes('application/json') ? r.json() : r.blob();
}

export const api = {
  get: (ruta) => pedir('GET', ruta),
  post: (ruta, cuerpo = {}) => pedir('POST', ruta, cuerpo),
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
