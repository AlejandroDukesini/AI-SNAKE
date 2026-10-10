/* ============================================================================
   MODO BORRADOR — backend simulado en el navegador
   ----------------------------------------------------------------------------
   Netlify solo sirve archivos estaticos: el servidor de Python (FastAPI + NumPy)
   no arranca alli, y cada /api/... o /ws/... devolvia 404. Para no perder la
   vitrina, el modo borrador (VITE_DEMO=true) sustituye ese servidor por este
   archivo, que responde con el MISMO contrato:

     REST  /api/config, /api/models, /api/exists/... (datos fijos de datos.json)
     WS    /ws/play, /ws/demo/{carpeta}, /ws/train   (sockets falsos en memoria)

   Es un BORRADOR: no hay red neuronal ni neuroevolucion real. Los cambios
   (favoritos, renombrar, borrar, entrenar) viven en memoria y se pierden al
   recargar, de modo que cada visita empieza exactamente igual.
   ============================================================================ */

import datos from './datos.json';
import { Snake, rng, semillaDe, nivelDeCobertura } from './snake';

const FPS_PLAY = 12;
const STREAM_FPS = 20;
const SEG_POR_GENERACION = 3;   // Cuanto dura en pantalla cada generacion simulada
const AGENTES_SIMULADOS = 8;    // Partidas reales por generacion (ver prepararGeneracion)

const THEMES = ['oscura', 'minimalista', 'verde'];
const GRIDS = [8, 10, 15];
const LIMITS = {
  min_generations: 1, max_generations: 100,
  min_agents: 4, max_agents: 100, default_agents: 25,
  min_elite: 1, default_elite: 3,
};
const ENGINES = [
  { id: 'advanced', label: 'Advanced', arch: '26 → 16 → 3',
    resumen: 'Feedforward compacto de una sola capa oculta (LeakyReLU, ~483 pesos). Sin profundidad que estorbe: mas evaluaciones/segundo y mejor convergencia en tiempo limitado.' },
  { id: 'intermated', label: 'Intermated', arch: '26 → 20 → 3',
    resumen: 'Algoritmo genetico clasico (el de siempre): recurrente y compacto. ADN pequeno, aprende con muy poca CPU.' },
  { id: 'basic', label: 'Basic', arch: '26 → 52 → 26 → 1',
    resumen: 'Teorico/expansivo: primera capa oculta duplica la entrada y una salida por rangos. Mucha expresividad, muta mas lento.' },
];
const DEFAULT_ENGINE = 'intermated';

/* Estado en memoria: copia profunda para que recargar siempre parta de cero. */
const estado = {
  config: { ...datos.config },
  models: structuredClone(datos.models),
};

const clamp = (v, min, max, def) => {
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) ? Math.max(min, Math.min(max, n)) : def;
};
const clampGrid = (g) => (GRIDS.includes(Number(g)) ? Number(g) : 8);

const NAME_A = ['Alpha', 'Cerebro', 'Neo', 'Viper', 'Cobra', 'Quantum', 'Titan',
  'Nova', 'Omega', 'Zenith', 'Hydra', 'Pixel', 'Turbo', 'Mamba'];
const NAME_B = ['Snake', 'Mind', 'Core', 'Brain', 'Genoma', 'Reptil', 'IA', 'Neura'];
const randomName = () => {
  const r = Math.random;
  return `${NAME_A[Math.floor(r() * NAME_A.length)]}-${NAME_B[Math.floor(r() * NAME_B.length)]}-V${1 + Math.floor(r() * 99)}`;
};

/* Port de storage.slugify. */
export function slugify(nombre) {
  const s = String(nombre ?? '').trim()
    .replace(/\s+/g, '_')
    .replace(/[^A-Za-z0-9_-]/g, '')
    .replace(/^[._-]+|[._-]+$/g, '')
    .slice(0, 40);
  return s || randomName();
}

const ahora = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
       + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};
const buscar = (carpeta) => estado.models.find((m) => m.carpeta === carpeta);
const ordenar = () => estado.models.sort((a, b) => b.fitness - a.fitness);
const resumen = (m) => structuredClone(m);

class HttpError extends Error {
  constructor(status, detail) { super(detail); this.status = status; }
}

/* ---------------------------------------------------------------------------
   REST
   --------------------------------------------------------------------------- */
function rutear(metodo, url, body) {
  const { pathname, searchParams } = new URL(url, 'http://borrador');
  const partes = pathname.split('/').filter(Boolean).map(decodeURIComponent); // ['api', ...]

  if (pathname === '/api/config' && metodo === 'GET') {
    return {
      config: { ...estado.config },
      themes: THEMES, grids: GRIDS, engines: ENGINES,
      default_engine: DEFAULT_ENGINE, limits: LIMITS,
      pop_size: LIMITS.default_agents,
    };
  }
  if (pathname === '/api/config' && metodo === 'PUT') {
    if (THEMES.includes(body.theme)) estado.config.theme = body.theme;
    if (body.generations != null) {
      estado.config.generations = clamp(body.generations, LIMITS.min_generations,
        LIMITS.max_generations, estado.config.generations);
    }
    if (body.grid != null) estado.config.grid = clampGrid(body.grid);
    return { config: { ...estado.config } };
  }
  if (pathname === '/api/models' && metodo === 'GET') {
    const soloFav = searchParams.get('favorites') === 'true';
    return { models: estado.models.filter((m) => !soloFav || m.favorito).map(resumen) };
  }
  if (pathname === '/api/models' && metodo === 'DELETE') {
    const conservar = searchParams.get('keep_favorites') !== 'false';
    const antes = estado.models.length;
    estado.models = estado.models.filter((m) => conservar && m.favorito);
    return { deleted: antes - estado.models.length };
  }
  if (partes[1] === 'exists' && metodo === 'GET') {
    const carpeta = slugify(partes[2]);
    const m = buscar(carpeta);
    return { carpeta, existe: !!m, model: m ? resumen(m) : null };
  }
  if (partes[1] === 'models' && partes[2]) {
    const carpeta = slugify(partes[2]);
    const m = buscar(carpeta);
    if (!m) throw new HttpError(404, 'Especimen no encontrado');

    if (partes[3] === 'favorite' && metodo === 'PUT') {
      m.favorito = !!body.favorito;
      return { model: resumen(m) };
    }
    if (metodo === 'PATCH') {
      const nombre = String(body.nombre ?? '').trim();
      if (!nombre) throw new HttpError(400, 'El nombre no puede estar vacío');
      const nueva = slugify(nombre);
      if (nueva !== carpeta && buscar(nueva)) throw new HttpError(409, 'Ya existe una IA con ese nombre');
      m.nombre = nombre;
      m.carpeta = nueva;
      return { model: resumen(m) };
    }
    if (metodo === 'GET') return { model: resumen(m) };
    if (metodo === 'DELETE') {
      estado.models = estado.models.filter((x) => x !== m);
      return { deleted: carpeta };
    }
  }
  throw new HttpError(404, 'Not Found');
}

/* Imita a `fetch`: devuelve un objeto con ok/status/json(). */
export async function demoFetch(url, options = {}) {
  const metodo = (options.method || 'GET').toUpperCase();
  const body = options.body ? JSON.parse(options.body) : {};
  await new Promise((r) => setTimeout(r, 60));   // Latencia minima, como una red real
  try {
    const data = rutear(metodo, url, body);
    return { ok: true, status: 200, json: async () => data };
  } catch (e) {
    const status = e.status || 500;
    return { ok: false, status, json: async () => ({ detail: e.message }) };
  }
}

/* ---------------------------------------------------------------------------
   WEBSOCKET FALSO
   Implementa lo que usan useSocket y TrainView: onopen/onmessage/onclose/
   onerror, addEventListener, send, close y readyState.
   --------------------------------------------------------------------------- */
class DemoSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(path) {
    this.path = path;
    this.readyState = DemoSocket.CONNECTING;
    this.listeners = {};
    this.timers = [];
    setTimeout(() => {
      if (this.readyState !== DemoSocket.CONNECTING) return;
      this.readyState = DemoSocket.OPEN;
      // La sesion va ANTES de 'open': TrainView envia su 'start' dentro de onopen.
      this.sesion = crearSesion(path, this);
      if (this.readyState === DemoSocket.OPEN) this.emitir('open', {});
    }, 30);
  }

  addEventListener(tipo, fn) { (this.listeners[tipo] ||= []).push(fn); }
  removeEventListener(tipo, fn) {
    this.listeners[tipo] = (this.listeners[tipo] || []).filter((f) => f !== fn);
  }

  emitir(tipo, ev) {
    this[`on${tipo}`]?.(ev);
    (this.listeners[tipo] || []).forEach((fn) => fn(ev));
  }

  /* Servidor -> cliente. */
  enviar(data) {
    if (this.readyState !== DemoSocket.OPEN) return;
    this.emitir('message', { data: JSON.stringify(data) });
  }

  /* Cliente -> servidor. */
  send(texto) {
    if (this.readyState !== DemoSocket.OPEN) return;
    try { this.sesion?.recibir(JSON.parse(texto)); } catch { /* ignorar */ }
  }

  intervalo(fn, ms) { const id = setInterval(fn, ms); this.timers.push(id); return id; }

  close() {
    if (this.readyState === DemoSocket.CLOSED) return;
    this.readyState = DemoSocket.CLOSED;
    this.timers.forEach(clearInterval);
    this.sesion?.cerrar?.();
    setTimeout(() => this.emitir('close', {}), 0);
  }
}

export function demoSocket(path) {
  return new DemoSocket(path);
}

function crearSesion(path, ws) {
  if (path === '/ws/play') return sesionPlay(ws);
  if (path.startsWith('/ws/demo/')) return sesionDemo(ws, decodeURIComponent(path.slice(9)));
  if (path === '/ws/train') return sesionTrain(ws);
  ws.close();
  return null;
}

/* /ws/play — partida manual. Arranca detenida hasta recibir 'start'. */
function sesionPlay(ws) {
  const nueva = () => new Snake({ grid: clampGrid(estado.config.grid), useEnergy: false,
                                  random: rng(semillaDe('jugar')) });
  let snake = nueva();
  let jugando = false;
  let dir = null;

  ws.intervalo(() => {
    if (jugando && snake.alive) {
      if (dir !== null) { snake.setAbsoluteDirection(dir); dir = null; }
      snake.advance();
    }
    if (!snake.alive) jugando = false;
    ws.enviar({ type: 'state', snake: snake.toState(), jugando });
  }, 1000 / FPS_PLAY);

  return {
    recibir(msg) {
      if (msg.action === 'dir' && Number.isInteger(msg.dir) && msg.dir >= 0 && msg.dir <= 3) dir = msg.dir;
      else if (msg.action === 'start') jugando = true;
      else if (msg.action === 'restart') { snake = nueva(); dir = null; jugando = false; }
    },
  };
}

/* Error de decision segun el nivel guardado: una IA con mas nivel se equivoca menos. */
const errorPorNivel = (nivel = 0) => Math.max(0.01, 0.12 - nivel * 0.03);

/* /ws/demo/{carpeta} — ver jugar a un especimen guardado, en bucle. */
function sesionDemo(ws, carpeta) {
  const m = buscar(slugify(carpeta));
  if (!m) {
    ws.enviar({ type: 'error', detail: 'Especimen no encontrado' });
    ws.close();
    return null;
  }
  const grid = clampGrid(estado.config.grid);
  const random = rng(semillaDe(m.carpeta));
  const error = errorPorNivel(m.nivel);
  let snake = new Snake({ grid, random });
  let espera = 0;

  ws.enviar({ type: 'info', model: resumen(m) });
  ws.intervalo(() => {
    if (snake.alive) snake.stepAI(error);
    else if ((espera += 1) > FPS_PLAY * 0.7) { snake = new Snake({ grid, random }); espera = 0; }
    ws.enviar({ type: 'state', snake: snake.toState() });
  }, 1000 / FPS_PLAY);
  return { recibir() {} };
}

/* /ws/train — "entrenamiento" simulado. Cada generacion juega `agents` partidas
   con la heuristica; la probabilidad de error baja con las generaciones, asi que
   la curva de fitness sube como en la evolucion real. Se reproduce a ritmo fijo
   (SEG_POR_GENERACION) para que se vea, no a la velocidad de la CPU. */
function sesionTrain(ws) {
  let ctx = null;
  let pausado = false;
  let parar = false;

  function iniciar(p) {
    const infinito = !!p.infinite;
    const generations = clamp(p.generations ?? estado.config.generations,
      LIMITS.min_generations, LIMITS.max_generations, 5);
    const grid = clampGrid(p.grid ?? estado.config.grid);
    const agents = clamp(p.agents, LIMITS.min_agents, LIMITS.max_agents, LIMITS.default_agents);
    const elite = clamp(p.elite, 1, agents - 1, LIMITS.default_elite);
    const nombre = p.nombre || randomName();
    const carpeta = slugify(nombre);
    const previo = buscar(carpeta);
    const engine = previo?.engine
      ?? (ENGINES.some((e) => e.id === p.engine) ? p.engine : DEFAULT_ENGINE);

    ws.enviar({ type: 'info', carpeta, nombre, continua: !!previo, grid,
                generations: infinito ? 0 : generations, infinito, agents, elite, engine });

    ctx = {
      infinito, generations, grid, agents, nombre, carpeta, previo, engine,
      random: rng(semillaDe(`${carpeta}|${grid}|${agents}|${engine}`)),
      genBase: previo?.generaciones ?? 0,
      gen: 0, frame: 0, best: null,
      frames: [], cursor: 0, porTick: 1,
    };
    prepararGeneracion();
  }

  /* Simula de golpe las partidas de la generacion y guarda sus fotogramas. */
  function prepararGeneracion() {
    ctx.gen += 1;
    const total = ctx.genBase + ctx.gen;
    const error = Math.max(0.01, 0.55 * Math.exp(-total / 6));
    const fitnesses = [];
    const lengths = [];
    ctx.frames = [];
    // Solo se juegan de verdad unas pocas partidas por generacion (repartidas
    // entre los indices de agente): con 100 agentes en 15x15 simularlas todas
    // en el hilo principal congelaria la pestana, y para un borrador basta.
    const muestras = Math.min(ctx.agents, AGENTES_SIMULADOS);
    for (let i = 1; i <= muestras; i += 1) {
      const agente = Math.round((i * ctx.agents) / muestras);
      const s = new Snake({ grid: ctx.grid, random: ctx.random });
      const e = error * (0.5 + ctx.random());
      while (s.alive && s.steps < ctx.grid * ctx.grid * 6) {
        s.stepAI(e);
        ctx.frames.push({ agente, snake: s.toState(), fitness: s.fitness() });
      }
      fitnesses.push(s.fitness());
      lengths.push(s.length);
      if (!ctx.best || s.fitness() > ctx.best.fitness) {
        ctx.best = { fitness: s.fitness(), frutas: s.fruits, pasos: s.steps, length: s.length };
      }
    }
    ctx.genStats = { fitnesses, lengths };
    ctx.cursor = 0;
    ctx.porTick = Math.max(1, Math.ceil(ctx.frames.length / (SEG_POR_GENERACION * STREAM_FPS)));
  }

  function cerrarGeneracion() {
    const { fitnesses, lengths } = ctx.genStats;
    const info = nivelDeCobertura(ctx.best.length, ctx.grid);
    ws.enviar({
      type: 'gen', generation: ctx.gen, generations: ctx.generations, infinito: ctx.infinito,
      best: Math.max(...fitnesses),
      avg: fitnesses.reduce((a, b) => a + b, 0) / fitnesses.length,
      best_length: Math.max(...lengths),
      cobertura: info.cobertura, nivel: info.nivel, nivel_etiqueta: info.etiqueta,
      mutation_std: Math.round(0.3 * Math.exp(-ctx.gen / 40) * 10000) / 10000,
    });
  }

  function guardar() {
    const b = ctx.best;
    const info = nivelDeCobertura(b.length, ctx.grid);
    const sesion = { fecha: ahora(), generaciones: ctx.gen, fitness: b.fitness, frutas: b.frutas,
      pasos: b.pasos, length: b.length, grid: ctx.grid, cobertura: info.cobertura,
      nivel: info.nivel, nivel_etiqueta: info.etiqueta, record: false };

    let m = ctx.previo && buscar(ctx.carpeta);
    if (m) {
      m.generaciones += ctx.gen;
      m.fecha_actualizacion = sesion.fecha;
      if (b.fitness > m.fitness) {
        Object.assign(m, { fitness: b.fitness, frutas: b.frutas, pasos: b.pasos,
                           length: b.length, grid: ctx.grid });
        sesion.record = true;
      }
      if (info.cobertura > (m.record_cobertura ?? 0)) {
        Object.assign(m, { record_cobertura: info.cobertura, cobertura: info.cobertura,
                           nivel: info.nivel, nivel_etiqueta: info.etiqueta });
      }
      m.sesiones = [...(m.sesiones || []), sesion];
    } else {
      sesion.record = true;
      m = { carpeta: ctx.carpeta, nombre: ctx.nombre, fecha_creacion: sesion.fecha,
        fecha_actualizacion: sesion.fecha, generaciones: ctx.gen, fitness: b.fitness,
        frutas: b.frutas, pasos: b.pasos, length: b.length, grid: ctx.grid, favorito: false,
        record_cobertura: info.cobertura, engine: ctx.engine, cobertura: info.cobertura,
        nivel: info.nivel, nivel_etiqueta: info.etiqueta, sesiones: [sesion] };
      estado.models.push(m);
    }
    ordenar();
    return resumen(m);
  }

  ws.intervalo(() => {
    if (!ctx || pausado) return;

    ctx.cursor = Math.min(ctx.frames.length, ctx.cursor + ctx.porTick);
    ctx.frame += ctx.porTick;
    const f = ctx.frames[ctx.cursor - 1];
    if (f) {
      ws.enviar({ type: 'step', generation: ctx.gen, generations: ctx.generations,
        infinito: ctx.infinito, agent: f.agente, pop_size: ctx.agents,
        best_fitness: ctx.best.fitness, frame: ctx.frame, snake: f.snake });
    }
    if (ctx.cursor < ctx.frames.length) return;

    cerrarGeneracion();
    const fin = parar || (!ctx.infinito && ctx.gen >= ctx.generations);
    if (!fin) { prepararGeneracion(); return; }

    ws.enviar({ type: 'done', model: guardar(), continua: !!ctx.previo, detenido: parar });
    ctx = null;
    ws.close();
  }, 1000 / STREAM_FPS);

  return {
    recibir(msg) {
      if (!ctx) { if (msg.action === 'start') iniciar(msg); return; }
      if (msg.action === 'cancel') { ws.enviar({ type: 'cancelled' }); ctx = null; ws.close(); }
      else if (msg.action === 'stop') { parar = true; pausado = false; ws.enviar({ type: 'stopping' }); }
      else if (msg.action === 'pause') { pausado = true; ws.enviar({ type: 'paused', paused: true }); }
      else if (msg.action === 'resume') { pausado = false; ws.enviar({ type: 'paused', paused: false }); }
    },
  };
}
