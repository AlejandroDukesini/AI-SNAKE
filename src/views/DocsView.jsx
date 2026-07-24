/* ============================================================================
   Documentación Técnica — "Sí funciona, y está construido así"
   ----------------------------------------------------------------------------
   Evidencia de funcionamiento navegable: explica, con el código real del
   proyecto, cómo percibe la IA, cómo evoluciona, cómo el runtime sostiene el
   streaming en vivo y cómo se protege el estado. No hay lógica de juego aquí:
   es una vista de solo lectura que reutiliza el sistema de diseño (ui.jsx) para
   ir siempre a juego con los tres temas.
   ============================================================================ */

import { useState } from 'react';
import { Panel, Title, Hint, Stat } from '../components/ui';

/* -------------------------------------------------------------------------
   Piezas locales de esta vista (no se reutilizan fuera de Documentación)
   ------------------------------------------------------------------------- */

/* Insignia de estado. `tono` mapea a un color del tema, nunca a uno fijo. */
function Badge({ children, tono = 'ok' }) {
  const tonos = {
    ok:   'border-snake text-snake bg-snake/10',
    info: 'border-accent text-accent bg-accent/10',
    warn: 'border-food text-food bg-food/10',
    mute: 'border-line text-muted bg-surface2',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border
      text-xs font-medium whitespace-nowrap ${tonos[tono]}`}>
      {children}
    </span>
  );
}

/* Bloque de código. Desplaza en horizontal dentro de su caja (nunca empuja el
   ancho de la página) y respeta la tipografía monoespaciada del tema. */
function Code({ children, caption }) {
  return (
    <figure className="my-3">
      <pre className="bg-surface2 border border-line rounded-xl p-4 overflow-x-auto
                      text-xs leading-relaxed text-ink font-mono">
        <code>{children}</code>
      </pre>
      {caption && (
        <figcaption className="text-xs text-muted mt-1.5 leading-relaxed">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}

/* Tarjeta de información con encabezado opcional. */
function Card({ title, badge, children, className = '' }) {
  return (
    <Panel className={className}>
      {(title || badge) && (
        <div className="flex items-center justify-between gap-3 mb-3">
          {title && <h3 className="font-medium text-ink">{title}</h3>}
          {badge}
        </div>
      )}
      {children}
    </Panel>
  );
}

/* Navegación por módulos: reutiliza el patrón "segmented", pero con scroll
   horizontal para que en móvil los cuatro nombres no se apelmacen. */
function ModuleTabs({ modulos, activo, onChange }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <div className="inline-flex p-1 bg-surface2 border border-line rounded-xl gap-1 min-w-full sm:min-w-0">
        {modulos.map((m) => (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            aria-pressed={activo === m.id}
            className={`px-4 py-2 rounded-lg text-sm whitespace-nowrap transition
              ${activo === m.id
                ? 'bg-accent text-on-accent font-medium'
                : 'text-muted hover:text-ink'}`}
          >
            <span className="mr-1.5">{m.icon}</span>{m.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ===========================================================================
   MÓDULO 1 — EL CEREBRO
   =========================================================================== */

/* Las 26 entradas, agrupadas por origen. La suma se muestra viva para que el
   número nunca se desincronice de la lista (24 + 1 + 1 = 26). */
const ENTRADAS = [
  {
    id: 'rayos',
    n: 24,
    titulo: '8 rayos egocéntricos × 3 rasgos',
    detalle:
      'La serpiente lanza 8 rayos relativos a hacia dónde mira (frente, diagonales y ' +
      'laterales). En cada rayo mide tres cosas: distancia a la pared, proximidad de su ' +
      'propio cuerpo y alineación con la manzana. 8 × 3 = 24 sensores.',
  },
  {
    id: 'tamano',
    n: 1,
    titulo: 'Tamaño propio (propioceptivo)',
    detalle:
      'Cuánto mide su cuerpo, normalizado por el área del tablero. Le dice "cuánto ocupo", ' +
      'que es lo que cambia el riesgo de encerrarse a medida que crece.',
  },
  {
    id: 'floodfill',
    n: 1,
    titulo: 'Espacio libre alcanzable (flood-fill)',
    detalle:
      'Un flood-fill desde la cabeza mide qué fracción del tablero puede todavía recorrer. ' +
      'Es la señal que le enseña a NO encerrarse: si un giro reduce mucho el espacio libre, ' +
      'lo evita. Es también el sensor más caro de calcular (ver Runtime).',
  },
];

function ModuloCerebro() {
  const [sel, setSel] = useState('rayos');
  const activa = ENTRADAS.find((e) => e.id === sel);

  return (
    <div className="space-y-5">
      <Card
        title="Arquitectura de la red: 26 → 20 → 3"
        badge={<Badge tono="ok">✅ En producción</Badge>}
      >
        <Hint className="mb-4">
          Cada serpiente lleva su propia red neuronal recurrente. Percibe con 26
          entradas, piensa en una capa oculta de 20 neuronas con memoria y decide
          una de 3 acciones.
        </Hint>

        <div className="grid grid-cols-3 gap-3 text-center">
          {[
            { n: 26, t: 'Entradas', s: 'percepción', tono: 'text-accent' },
            { n: 20, t: 'Ocultas', s: 'recurrentes (W_rec)', tono: 'text-snake' },
            { n: 3,  t: 'Salidas', s: 'recto · izq · der', tono: 'text-food' },
          ].map((c) => (
            <div key={c.t} className="bg-surface2 border border-line rounded-xl px-2 py-4">
              <div className={`text-3xl font-semibold tabular-nums ${c.tono}`}>{c.n}</div>
              <div className="text-sm text-ink mt-1">{c.t}</div>
              <div className="text-xs text-muted mt-0.5">{c.s}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card
        title="Las 26 entradas, desglosadas"
        badge={<Badge tono="info">interactivo</Badge>}
      >
        <Hint className="mb-4">
          Toca cada bloque para ver qué mide. La suma es siempre{' '}
          <span className="text-ink font-medium tabular-nums">24 + 1 + 1 = 26</span>.
        </Hint>

        <div className="grid gap-3 sm:grid-cols-3 mb-4">
          {ENTRADAS.map((e) => (
            <button
              key={e.id}
              onClick={() => setSel(e.id)}
              aria-pressed={sel === e.id}
              className={`text-left p-4 rounded-panel border-2 transition
                hover:-translate-y-0.5
                ${sel === e.id ? 'border-accent' : 'border-line'}`}
            >
              <div className="text-2xl font-semibold tabular-nums text-ink">{e.n}</div>
              <div className="text-xs text-muted mt-1 leading-snug">{e.titulo}</div>
            </button>
          ))}
        </div>

        <div className="bg-surface2 border border-line rounded-xl p-4">
          <div className="text-sm font-medium text-ink mb-1">{activa.titulo}</div>
          <p className="text-sm text-muted leading-relaxed">{activa.detalle}</p>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="¿Por qué NumPy puro y no PyTorch/TensorFlow?" badge={<Badge tono="ok">decisión</Badge>}>
          <Hint className="mb-3">
            El modelo es una red diminuta (26→20→3) que se <em>evoluciona</em>, no se
            entrena por gradiente. Un framework de deep learning sería peso muerto:
          </Hint>
          <ul className="space-y-2 text-sm text-muted leading-relaxed">
            <li>▸ Sin autograd ni GPU: el forward es un puñado de multiplicaciones de matrices que NumPy hace de sobra en CPU.</li>
            <li>▸ Instalación mínima: <code className="text-ink">numpy · fastapi · uvicorn</code>. Sin CUDA, sin ruedas de 2&nbsp;GB.</li>
            <li>▸ Cero caja negra: coherente con el objetivo educativo del proyecto: se puede leer cada operación.</li>
          </ul>
        </Card>

        <Card title="Memoria recurrente (W_rec)" badge={<Badge tono="ok">✅ mecanismo listo</Badge>}>
          <Hint className="mb-3">
            La capa oculta se realimenta a sí misma: en cada turno ve las entradas del
            momento <span className="text-ink">y su propio estado del turno anterior</span>.
            Eso le da memoria dentro de una partida —recordar por dónde venía—, el
            ingrediente de la planificación emergente.
          </Hint>
          <Code caption="Nace a cero: se comporta como una feedforward y la mutación va introduciendo la memoria, así que añadirla no degrada nada de lo aprendido.">
{`# estado oculto que persiste entre pasos
h = tanh(W1 @ x + W_rec @ h_prev + b1)
salida = W2 @ h + b2      # recto | izq | der`}
          </Code>
        </Card>
      </div>
    </div>
  );
}

/* ===========================================================================
   MÓDULO 2 — SELECCIÓN NATURAL
   =========================================================================== */

const NIVELES = [
  { n: 'N0', nombre: 'Supervivencia refleja', cob: '< 10 %', tono: 'mute' },
  { n: 'N1', nombre: 'Forrajeo básico',       cob: '10–20 %', tono: 'mute' },
  { n: 'N2', nombre: 'Forrajeo fiable',       cob: '20–35 %', tono: 'ok' },
  { n: 'N3', nombre: 'Conciencia espacial',   cob: '35–55 %', tono: 'ok' },
  { n: 'N4', nombre: 'Planificación emergente', cob: '55–80 %', tono: 'info' },
  { n: 'N5', nombre: 'Casi óptimo',           cob: '> 80 %', tono: 'warn' },
];

const OPERADORES = [
  { t: 'Elitismo', d: 'Las 3 mejores redes pasan intactas a la siguiente generación. El buen material nunca se pierde.' },
  { t: 'Selección por torneo (k=3)', d: 'Se cogen 3 al azar y gana el de mayor fitness. Presiona hacia lo bueno sin descartar del todo la diversidad.' },
  { t: 'Cruce uniforme', d: 'El hijo hereda cada peso de uno u otro padre. Recombina soluciones parciales de dos linajes.' },
  { t: 'Mutación gaussiana adaptativa', d: 'Un 5 % de los pesos se perturba. Si la población se estanca, la intensidad baja sola (recocido): pasa de explorar a afinar.' },
];

function ModuloGenetico() {
  return (
    <div className="space-y-5">
      <Card title="Aprende sin gradiente ni datos supervisados" badge={<Badge tono="ok">✅ funciona</Badge>}>
        <Hint>
          No hay <em>backpropagation</em> ni dataset. Se evoluciona una población de 25
          serpientes: la Generación 2 se entrena <span className="text-ink">literalmente
          sobre los mejores hijos de la 1</span>. Los pesos aleatorios del inicio se
          convierten en comportamiento por pura selección natural.
        </Hint>
        <Code caption="Fitness = recompensa densa. Crecer vale mil veces más que sobrevivir; el shaping orienta a las que aún no han comido.">
{`fitness = pasos + (tamaño − 3) × 1000 + shaping_de_acercamiento`}
        </Code>
      </Card>

      <Card title="Los cuatro operadores de la evolución">
        <div className="grid gap-3 sm:grid-cols-2">
          {OPERADORES.map((o, i) => (
            <div key={o.t} className="bg-surface2 border border-line rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="w-6 h-6 grid place-items-center rounded-md bg-accent/10
                                 border border-accent text-accent text-xs font-semibold tabular-nums">
                  {i + 1}
                </span>
                <span className="text-sm font-medium text-ink">{o.t}</span>
              </div>
              <p className="text-sm text-muted leading-relaxed">{o.d}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card title="La métrica objetiva: Cobertura" badge={<Badge tono="info">medida, no declarada</Badge>}>
        <Hint className="mb-3">
          La inteligencia se mide con una sola regla independiente del tamaño de tablero,
          así que compara 8×8, 10×10 y 15×15 de forma justa. El nivel <span className="text-ink">solo
          puede subir</span> entrenamiento a entrenamiento (récord monótono).
        </Hint>
        <Code>{`cobertura = longitud / (grid × grid)      # fracción del tablero ocupada`}</Code>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[420px]">
            <thead>
              <tr className="text-left text-xs text-muted border-b border-line">
                <th className="py-2 pr-3 font-medium">Nivel</th>
                <th className="py-2 pr-3 font-medium">Capacidad</th>
                <th className="py-2 font-medium">Cobertura</th>
              </tr>
            </thead>
            <tbody>
              {NIVELES.map((l) => (
                <tr key={l.n} className="border-b border-line/60">
                  <td className="py-2 pr-3"><Badge tono={l.tono}>🧠 {l.n}</Badge></td>
                  <td className="py-2 pr-3 text-muted">{l.nombre}</td>
                  <td className="py-2 text-ink tabular-nums">{l.cob}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Hint className="mt-3 text-xs">
          Honestidad: tener el <em>mecanismo</em> de un nivel (p. ej. memoria para N4) no es
          lo mismo que alcanzar su cobertura. El nivel sale del resultado real de cada
          entrenamiento. N5 (visión global por CNN) es línea de I+D documentada.
        </Hint>
      </Card>
    </div>
  );
}

/* ===========================================================================
   MÓDULO 3 — RUNTIME, CONCURRENCIA Y PERFORMANCE
   =========================================================================== */

function ModuloRuntime() {
  return (
    <div className="space-y-5">
      <Card title="Cómputo pesado sin congelar el servidor" badge={<Badge tono="ok">✅ estable</Badge>}>
        <Hint>
          La neuroevolución es CPU-intensiva y bloquearía el bucle asíncrono de FastAPI.
          Por eso corre en un <span className="text-ink">hilo dedicado</span> (patrón
          productor/consumidor): el hilo produce, el bucle asyncio solo drena colas y
          emite por WebSocket a ritmo fijo.
        </Hint>
        <div className="grid gap-3 sm:grid-cols-2 mt-4">
          <div className="bg-surface2 border border-line rounded-xl p-4">
            <div className="text-sm font-medium text-ink mb-1">🧵 Hilo de neuroevolución</div>
            <p className="text-sm text-muted leading-relaxed">
              Simula miles de pasos por segundo. Daemon: si el cliente se va, se señaliza
              y se cierra con <code className="text-ink">join(timeout)</code> acotado — nunca
              congela el servidor.
            </p>
          </div>
          <div className="bg-surface2 border border-line rounded-xl p-4">
            <div className="text-sm font-medium text-ink mb-1">⚡ Bucle asyncio (FastAPI)</div>
            <p className="text-sm text-muted leading-relaxed">
              Atiende el WebSocket, escucha órdenes (pause/stop/cancel) y emite fotogramas
              a 20&nbsp;fps. Nunca hace trabajo pesado.
            </p>
          </div>
        </div>
      </Card>

      <Card title="Control de backpressure: sobrescribir, no encolar" badge={<Badge tono="info">clave</Badge>}>
        <Hint className="mb-2">
          El núcleo produce miles de pasos/segundo; al cliente solo le importa el más
          reciente. Encolarlos todos agotaría memoria y saturaría la red. Solución: el
          último fotograma se <span className="text-ink">sobrescribe</span> en una casilla;
          solo los eventos que no se pueden perder (<code className="text-ink">gen</code>,
          <code className="text-ink"> done</code>) usan cola real.
        </Hint>
        <Code caption="El streaming va a STREAM_FPS constante, independiente de lo rápido que simule el hilo. Cero backpressure.">
{`# productor (hilo):  el frame nuevo PISA al anterior
ultimo["step"] = datos

# consumidor (asyncio):  emite a ritmo fijo, no acumula
await asyncio.sleep(1.0 / STREAM_FPS)     # 20 fps
if ultimo["step"] is not None:
    await ws.send_json({"type": "step", **ultimo["step"]})
    ultimo["step"] = None`}
        </Code>
      </Card>

      <Card title="Métricas reales (medidas, reproducibles)" badge={<Badge tono="ok">benchmarks/</Badge>}>
        <Hint className="mb-4">
          Motor 8×8, población 25, <code className="text-ink">bench_core.py</code> ·
          Lighthouse sobre el build de Vite en Chrome headless.
        </Hint>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat label="Pasos simulados / s" value="≈ 4.000" accent />
          <Stat label="Tiempo por generación" value="≈ 380 ms" />
          <Stat label="Streaming WebSocket" value="20 fps" />
          <Stat label="Lighthouse desktop" value="100" accent />
        </div>
        <div className="grid grid-cols-3 gap-3 mt-3">
          <Stat label="LCP (desktop)" value="0,5 s" />
          <Stat label="TBT" value="0 ms" />
          <Stat label="CLS" value="0,016" />
        </div>
        <Hint className="mt-3 text-xs">
          El flood-fill que da la inteligencia espacial es el punto más caliente y el más
          difícil de vectorizar: por eso el siguiente salto (evaluación por lotes en NumPy)
          es un rediseño del simulador, no un cambio de una línea.
        </Hint>
      </Card>
    </div>
  );
}

/* ===========================================================================
   MÓDULO 4 — SEGURIDAD Y PERSISTENCIA
   =========================================================================== */

function ModuloSeguridad() {
  return (
    <div className="space-y-5">
      <Card title="Path traversal cerrado en origen: slugify" badge={<Badge tono="ok">✅ mitigado</Badge>}>
        <Hint className="mb-2">
          El nombre de una IA lo escribe el usuario y se convierte en nombre de carpeta.
          Sin filtro, un nombre como <code className="text-ink">../../algo</code> escribiría
          fuera de <code className="text-ink">historial/</code>. <span className="text-ink">
          slugify</span> es la única barrera entre esa entrada y el sistema de ficheros:
          solo deja letras, números, guion y guion bajo.
        </Hint>
        <Code caption="storage.py — también quita puntos guía y recorta a 40 caracteres. Si no queda nada usable, genera un nombre aleatorio.">
{`def slugify(nombre):
    nombre = re.sub(r"\\s+", "_", nombre)             # espacios -> _
    nombre = re.sub(r"[^A-Za-z0-9_\\-]", "", nombre)  # fuera todo lo demás
    nombre = nombre.strip("._-")[:40]                # sin puntos guía; máx 40
    return nombre or ml.random_name()`}
        </Code>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Cero pérdida de progreso" badge={<Badge tono="ok">récord monótono</Badge>}>
          <ul className="space-y-2 text-sm text-muted leading-relaxed">
            <li>▸ Cada IA es una <span className="text-ink">carpeta</span>: <code className="text-ink">modelo.json</code> (mejor linaje) + <code className="text-ink">sesiones.json</code> (histórico).</li>
            <li>▸ Reentrenar acumula generaciones, pero los pesos <span className="text-ink">solo se sustituyen si se batió el récord</span>. La evolución tiene azar: una mala racha nunca degrada tu IA.</li>
            <li>▸ <code className="text-ink">record_cobertura</code> es monótono: el nivel solo sube o se mantiene.</li>
          </ul>
        </Card>

        <Card title="Lectura tolerante a fallos" badge={<Badge tono="info">robusto</Badge>}>
          <Hint className="mb-3">
            Los archivos del historial son editables a mano y pueden corromperse. La lectura
            nunca revienta el servidor: ante un JSON inválido devuelve un valor por defecto.
          </Hint>
          <Code>
{`def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default   # nunca tumba el servidor`}
          </Code>
        </Card>
      </div>

      <Card title="Superficie mínima en el cliente" badge={<Badge tono="ok">✅ sin XSS por inyección</Badge>}>
        <ul className="space-y-2 text-sm text-muted leading-relaxed">
          <li>▸ El estado y el consentimiento viven en <code className="text-ink">localStorage</code>, no en cookies: sin CSRF por cookie (<code className="text-ink">allow_credentials=False</code>).</li>
          <li>▸ CORS por lista blanca de orígenes conocidos + regex acotado para las previews de Vercel.</li>
          <li>▸ Los scripts de terceros se inyectan con <code className="text-ink">createElement + .src</code> (nunca <code className="text-ink">innerHTML</code>/<code className="text-ink">eval</code>) y solo desde URLs https en lista blanca.</li>
        </ul>
      </Card>
    </div>
  );
}

/* ===========================================================================
   VISTA
   =========================================================================== */

const MODULOS = [
  { id: 'cerebro',    icon: '🧠', label: 'El Cerebro',     render: ModuloCerebro },
  { id: 'genetico',   icon: '🧬', label: 'Selección Natural', render: ModuloGenetico },
  { id: 'runtime',    icon: '⚙️', label: 'Runtime',        render: ModuloRuntime },
  { id: 'seguridad',  icon: '🔒', label: 'Seguridad',      render: ModuloSeguridad },
];

export default function DocsView() {
  const [activo, setActivo] = useState('cerebro');
  const Modulo = MODULOS.find((m) => m.id === activo).render;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Title>Documentación Técnica</Title>
          <Badge tono="ok">✅ Sí funciona</Badge>
        </div>
        <Hint>
          Evidencia de funcionamiento con el código real del proyecto: cómo percibe la IA,
          cómo evoluciona, cómo el runtime sostiene el streaming en vivo y cómo se protege
          el estado. Cuatro módulos, todo rastreable a un archivo.
        </Hint>
      </div>

      <ModuleTabs modulos={MODULOS} activo={activo} onChange={setActivo} />

      <Modulo />

      <p className="text-xs text-muted text-center pt-2">
        Fuentes: <code className="text-ink">snake_neuroevolution.py</code> ·{' '}
        <code className="text-ink">ai_server.py</code> ·{' '}
        <code className="text-ink">storage.py</code>. Detalle completo en{' '}
        <code className="text-ink">TECHNICAL_PROOF.md</code> y{' '}
        <code className="text-ink">PLANNING.md</code>.
      </p>
    </div>
  );
}
