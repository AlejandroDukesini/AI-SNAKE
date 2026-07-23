/* ============================================================================
   GESTOR DE CONSENTIMIENTO DE COOKIES  (nucleo, sin React)
   ----------------------------------------------------------------------------
   Toda la logica de consentimiento RGPD vive aqui, separada de la interfaz: el
   componente solo pinta y llama a estas funciones. Asi la misma logica sirve
   aunque la UI cambie, y se puede probar sin montar React.

   Principios que respeta este modulo:
     - CONSENTIMIENTO EXPLICITO Y PREVIO: ningun script de terceros se carga
       hasta que el usuario acepta SU categoria. Sin decision => nada se carga.
     - GRANULARIDAD: cuatro categorias independientes (RGPD art. 7).
     - REVOCABLE: se puede reabrir el panel y cambiar la decision cuando sea.
     - SEGURIDAD: los scripts se inyectan con createElement + propiedad .src
       (nunca innerHTML/eval) y solo desde URLs https absolutas en lista blanca,
       de modo que no hay superficie de XSS por inyeccion de <script>.
   ============================================================================ */

/* Version del esquema de categorias. Si en el futuro se anade o quita una
   categoria, subir este numero INVALIDA los consentimientos guardados y vuelve
   a preguntar: nadie queda "consintiendo" algo que no existia cuando decidio. */
const SCHEMA_VERSION = 1;
const STORAGE_KEY = 'snake-cookie-consent';

/* Las categorias, en el orden en que se muestran. `necessary` es obligatoria:
   cubre lo imprescindible para que la web funcione (tema, sesion, el propio
   consentimiento) y por eso no se puede desactivar ni requiere permiso. */
export const CATEGORIES = [
  {
    id: 'necessary',
    required: true,
    label: 'Necesarias',
    desc: 'Imprescindibles para que la web funcione: recordar el tema elegido y ' +
          'esta misma decision de cookies. No se pueden desactivar.',
  },
  {
    id: 'analytics',
    required: false,
    label: 'Analiticas',
    desc: 'Nos ayudan a entender de forma agregada y anonima como se usa la web ' +
          'para mejorarla (p. ej. Google Analytics).',
  },
  {
    id: 'advertising',
    required: false,
    label: 'Publicitarias',
    desc: 'Permiten mostrar y medir anuncios relevantes (p. ej. Meta Pixel). ' +
          'Pueden compartir datos con terceros.',
  },
  {
    id: 'preferences',
    required: false,
    label: 'Preferencias',
    desc: 'Recuerdan opciones no esenciales para personalizar tu experiencia ' +
          '(idioma, disposicion, contenidos ya vistos).',
  },
];

/* Objeto de categorias con todo apagado salvo las obligatorias, y con todo
   encendido. Se derivan de CATEGORIES para no repetir la lista. */
const allDenied  = () => Object.fromEntries(CATEGORIES.map((c) => [c.id, !!c.required]));
const allGranted = () => Object.fromEntries(CATEGORIES.map((c) => [c.id, true]));

/* -------------------------------------------------------------------------
   PUB/SUB minimalista
   Dos canales: 'change' (cambio el consentimiento) y 'open' (alguien pide
   abrir el panel de preferencias). El componente React se suscribe a ambos.
   ------------------------------------------------------------------------- */
const listeners = { change: new Set(), open: new Set() };

export function on(event, fn) {
  (listeners[event] ??= new Set()).add(fn);
  return () => listeners[event].delete(fn);   // devuelve el "de-suscriptor"
}

function emit(event, payload) {
  listeners[event]?.forEach((fn) => {
    try { fn(payload); } catch (e) { console.error('[consent] listener fallo:', e); }
  });
}

/* -------------------------------------------------------------------------
   PERSISTENCIA
   Se usa localStorage: el consentimiento solo lo lee el propio navegador para
   decidir que cargar; no hace falta enviarlo al servidor en cada peticion, asi
   que una cookie no aporta nada y si mas superficie. (Si algun dia el backend
   necesitara leerlo, ver la nota de "cookie" al pie de este archivo.)
   ------------------------------------------------------------------------- */
function read() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Version distinta => tratar como "sin decidir" y volver a preguntar.
    if (!parsed || parsed.v !== SCHEMA_VERSION) return null;
    return parsed;
  } catch {
    // localStorage puede fallar (modo privado, cuota, storage bloqueado):
    // ante la duda, "sin decidir" es la opcion mas conservadora.
    return null;
  }
}

function write(categories) {
  const payload = {
    v: SCHEMA_VERSION,
    ts: Date.now(),                              // sella CUANDO se consintio
    // `necessary` siempre true, pase lo que pase, para que un objeto manipulado
    // no pueda desactivar lo que la web necesita para arrancar.
    categories: { ...allDenied(), ...categories, necessary: true },
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch (e) {
    console.error('[consent] no se pudo persistir la decision:', e);
  }
  state = payload;
  applyGatedScripts();     // carga de inmediato lo que se acabe de permitir
  emit('change', payload);
  return payload;
}

/* Estado en memoria: cache de lo persistido para no tocar localStorage a cada
   `isAllowed`. `null` = el usuario aun no ha decidido. */
let state = read();

/* -------------------------------------------------------------------------
   API DE CONSULTA
   ------------------------------------------------------------------------- */
export function getConsent()  { return state; }
export function hasDecision() { return state !== null; }
export function isAllowed(category) { return !!state?.categories?.[category]; }

/* -------------------------------------------------------------------------
   API DE DECISION
   ------------------------------------------------------------------------- */
export const acceptAll          = () => write(allGranted());
export const rejectNonEssential = () => write(allDenied());
export const savePreferences    = (categories) => write(categories);

/* Pide abrir el panel (lo usa el boton del footer y window.CookieConsent.open). */
export const openPreferences = () => emit('open');

/* Borra la decision y vuelve a preguntar. Util para "cambiar mi consentimiento"
   desde cero o para pruebas. No des-ejecuta scripts ya cargados (imposible):
   basta recargar para partir limpio. */
export function resetConsent() {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* nada que hacer */ }
  state = null;
  emit('change', null);
  emit('open');
}

/* ============================================================================
   REGISTRO Y BLOQUEO CONDICIONAL DE SCRIPTS DE TERCEROS
   ----------------------------------------------------------------------------
   En vez de escribir <script> de Google/Meta/Hotjar directamente en el HTML
   (donde se ejecutarian SIEMPRE), se REGISTRAN aqui con su categoria. El script
   solo se inyecta cuando esa categoria esta consentida. Un mismo script no se
   carga dos veces.
   ============================================================================ */
const registry = new Map();   // id -> definicion
const loaded   = new Set();   // ids ya inyectados

/* Solo se admiten URLs https absolutas y sin caracteres que permitan romper el
   contexto. La fuente SIEMPRE la fija el desarrollador (nunca entrada de
   usuario), pero validarla es una defensa en profundidad barata contra que un
   `src` mal construido (o interpolado con datos) introduzca algo raro. */
const SAFE_SRC = /^https:\/\/[\w.-]+(:\d+)?(\/[^\s"'<>]*)?$/i;

/**
 * Registra un script de terceros para carga condicionada al consentimiento.
 * @param {object} def
 * @param {string} def.id        Identificador unico (evita duplicados).
 * @param {string} def.category  Categoria que debe estar consentida.
 * @param {string} [def.src]     URL https del script externo. Si se omite, solo
 *                               se ejecuta `onLoad` (util para inicializar una
 *                               libreria ya presente sin cargar nada).
 * @param {object} [def.attrs]   { async, defer, dataset } aplicados de forma segura.
 * @param {Function} [def.onLoad]     Se llama tras cargar el script (o al momento
 *                                    si no hay `src`). Aqui va el init (gtag, etc.).
 * @param {Function} [def.beforeLoad] Se llama justo antes de inyectar.
 */
export function registerScript(def) {
  if (!def?.id || !def?.category) {
    throw new Error('registerScript: "id" y "category" son obligatorios');
  }
  registry.set(def.id, def);
  applyGatedScripts();     // por si su categoria ya estaba consentida
}

function injectScript(def) {
  if (loaded.has(def.id)) return;
  loaded.add(def.id);      // marcar YA: evita doble carga si se reentra

  try {
    def.beforeLoad?.();

    // Sin src: solo logica de inicializacion, nada que descargar de la red.
    if (!def.src) { def.onLoad?.(); return; }

    if (!SAFE_SRC.test(def.src)) {
      console.error(`[consent] src rechazado para "${def.id}" (debe ser https absoluto):`, def.src);
      loaded.delete(def.id);
      return;
    }

    // createElement + propiedad .src  => el navegador trata el valor como URL,
    // nunca como HTML. No hay innerHTML ni eval en ningun punto: sin XSS.
    const el = document.createElement('script');
    el.src   = def.src;
    el.async = def.attrs?.async ?? true;
    el.defer = def.attrs?.defer ?? false;
    // Atributos data-* con setAttribute y valores forzados a string.
    for (const [k, v] of Object.entries(def.attrs?.dataset ?? {})) {
      el.dataset[k] = String(v);
    }
    el.addEventListener('load',  () => def.onLoad?.());
    el.addEventListener('error', () => {
      loaded.delete(def.id);   // permitir reintento en una futura re-aplicacion
      console.error(`[consent] fallo al cargar el script "${def.id}"`);
    });
    document.head.appendChild(el);
  } catch (e) {
    loaded.delete(def.id);
    console.error(`[consent] error inyectando "${def.id}":`, e);
  }
}

/* Recorre el registro y carga lo que este permitido y aun no cargado. Se llama
   tras cada decision y tras cada registro. Sin decision, no hace nada. */
function applyGatedScripts() {
  if (!state) return;
  for (const def of registry.values()) {
    if (state.categories[def.category] && !loaded.has(def.id)) injectScript(def);
  }
}

/* ============================================================================
   API GLOBAL
   ----------------------------------------------------------------------------
   Expuesta en window para poder reabrir el panel o consultar el estado desde
   cualquier sitio (un enlace en el footer, la consola, un tag manager...).
   ============================================================================ */
if (typeof window !== 'undefined') {
  window.CookieConsent = {
    open: openPreferences,
    get: getConsent,
    isAllowed,
    acceptAll,
    rejectNonEssential,
    reset: resetConsent,
  };
}

/* ----------------------------------------------------------------------------
   NOTA — ¿y si prefieres una COOKIE en vez de localStorage?
   Si el backend necesitara leer el consentimiento (p. ej. para no servir cierto
   HTML), sustituye read/write por una cookie con atributos seguros:

     document.cookie = `${STORAGE_KEY}=${encodeURIComponent(JSON.stringify(payload))}` +
       `; Max-Age=15552000; Path=/; SameSite=Lax; Secure`;

   - SameSite=Lax  -> no se envia en peticiones cross-site (defensa CSRF).
   - Secure        -> solo viaja por HTTPS.
   - 15552000 s    -> ~180 dias; el RGPD recomienda re-pedir consentimiento
                      pasado un tiempo razonable (6-12 meses).
   No pongas HttpOnly: el JS de esta pagina necesita leerla para decidir que
   cargar. El resto de la logica de este archivo no cambia.
   -------------------------------------------------------------------------- */
