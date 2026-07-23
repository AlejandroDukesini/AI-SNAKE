/* ============================================================================
   CLIENTE DE LA API
   ----------------------------------------------------------------------------
   Todas las llamadas al servidor de Python, en un solo sitio. Los componentes
   nunca hacen fetch directamente: asi cambiar una ruta se toca aqui y ya.

   Las rutas son RELATIVAS a proposito. En desarrollo el proxy de Vite las
   reenvia al puerto 8000; en un despliegue MONOLITICO (el mismo servidor sirve
   web + API, como en Render con run.py --prod) tambien valen tal cual.

   Pero en un despliegue PARTIDO (frontend en Vercel/Netlify, backend en Render)
   el frontend vive en OTRO dominio: una ruta relativa como /api/config pega
   contra Vercel, que no tiene backend, y devuelve 404. Para ese caso se define
   VITE_BACKEND_URL con la URL del backend de Render y se antepone a cada ruta.
   ============================================================================ */

/* Base de las peticiones HTTP.
   - Con VITE_BACKEND_URL definida: esa URL, sin la barra final (evita el //
     duplicado al concatenar con rutas que empiezan por /).
   - Sin definir: cadena vacia => rutas relativas, comportamiento local/monolitico. */
const API_BASE = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/+$/, '');

async function req(url, options) {
  const res = await fetch(API_BASE + url, options);
  if (!res.ok) {
    // El detalle lo pone FastAPI; si la respuesta no es JSON, no reventar aqui.
    const detalle = await res.json().catch(() => ({}));
    throw new Error(detalle.detail || `Error ${res.status}`);
  }
  return res.json();
}

const json = (metodo, body) => ({
  method: metodo,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  getConfig: () => req('/api/config'),
  saveConfig: (patch) => req('/api/config', json('PUT', patch)),

  listModels: (soloFavoritos = false) =>
    req(`/api/models${soloFavoritos ? '?favorites=true' : ''}`),

  /* Comprueba si un nombre ya tiene carpeta. Es lo que permite avisar de si se
     va a CREAR un especimen nuevo o CONTINUAR el linaje de uno existente. */
  checkName: (nombre) => req(`/api/exists/${encodeURIComponent(nombre)}`),

  setFavorite: (carpeta, favorito) =>
    req(`/api/models/${encodeURIComponent(carpeta)}/favorite`, json('PUT', { favorito })),

  /* Renombra una IA sin perder su entrenamiento. El servidor mueve la carpeta
     si el nombre nuevo cambia el slug; devuelve 409 si ya existe otra igual. */
  renameModel: (carpeta, nombre) =>
    req(`/api/models/${encodeURIComponent(carpeta)}`, json('PATCH', { nombre })),

  deleteModel: (carpeta) =>
    req(`/api/models/${encodeURIComponent(carpeta)}`, { method: 'DELETE' }),

  clearHistory: () => req('/api/models?keep_favorites=true', { method: 'DELETE' }),
};

/* URL absoluta de WebSocket.
   - Con VITE_BACKEND_URL (despliegue partido): se apunta al backend de Render,
     convirtiendo el esquema HTTP a su equivalente WebSocket:
         https://  ->  wss://      http://  ->  ws://
     Sin convertir el esquema, el navegador rechaza abrir el socket.
   - Sin VITE_BACKEND_URL (local o monolitico): se deriva de la pagina actual,
     asi funciona igual en localhost (ws://) que tras el HTTPS de un hosting (wss://).

   Fuente unica de la URL de WS: la usan tanto useSocket como TrainView, que abre
   su socket de entrenamiento directamente. */
export function wsURL(path) {
  const base = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/+$/, '');
  if (base) {
    if (base.startsWith('https://')) return `wss://${base.slice('https://'.length)}${path}`;
    if (base.startsWith('http://'))  return `ws://${base.slice('http://'.length)}${path}`;
    // Ya venia como ws:// o wss:// (o sin esquema): usarla tal cual.
    return `${base}${path}`;
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}${path}`;
}
