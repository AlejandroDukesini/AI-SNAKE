/* ============================================================================
   CLIENTE DE LA API
   ----------------------------------------------------------------------------
   Todas las llamadas al servidor de Python, en un solo sitio. Los componentes
   nunca hacen fetch directamente: asi cambiar una ruta se toca aqui y ya.

   Las rutas son RELATIVAS a proposito. En desarrollo el proxy de Vite las
   reenvia al puerto 8000; en produccion las sirve ese mismo servidor. Ninguna
   URL escrita a mano, y el mismo build vale en local y en un hosting con HTTPS.
   ============================================================================ */

async function req(url, options) {
  const res = await fetch(url, options);
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

/* URL absoluta de WebSocket a partir de la pagina actual: funciona igual en
   localhost (ws://) que detras del HTTPS de un hosting (wss://). */
export function wsURL(path) {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}${path}`;
}
