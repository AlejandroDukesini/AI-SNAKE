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

/* ---------------------------------------------------------------------------
   Los motores de red REALES del proyecto (los tres que de verdad corren en
   snake_neuroevolution.py). Todos comparten los 26 sensores y el algoritmo
   genético: lo que cambia es la topología del cerebro y cómo su salida se
   traduce en un giro, y eso hace que cada uno APRENDA distinto.

   Estructura extensible: para documentar un motor nuevo basta con añadir una
   entrada aquí (su `layers`, `salida`, cifras y explicación); el selector, el
   diagrama y la ficha se generan solos, sin tocar el JSX. `orden` fija la
   posición en el selector.
   --------------------------------------------------------------------------- */
const MOTORES = {
  intermated: {
    orden: 1,
    label: 'RNN Recurrente (NumPy)',
    arch: '26 → 20 → 3',
    layers: [26, 20, 3],
    recurrente: true,
    enfoque: 'Algoritmo genético clásico · motor por defecto',
    salida: 'argmax de 3 · recto / izquierda / derecha',
    pesos: '≈ 1.003',
    cpu: 'Baja',
    muta: 'Muy eficiente',
    aprende:
      'Aprende con MEMORIA intra-partida: la capa oculta se realimenta con su ' +
      'estado del turno anterior (W_rec), así "recuerda por dónde venía". Su ADN ' +
      'compacto reduce el espacio de búsqueda, de modo que el genético converge ' +
      'con pocas evaluaciones y muy poca CPU. Es el único con especímenes previos.',
    codigo:
`# La capa oculta ve la entrada Y su propio estado anterior (memoria)
h = relu(W1 @ x + b1 + W_rec @ h_prev)
o = W2 @ h + b2
acción = argmax(o)          # recto | izquierda | derecha`,
  },
  advanced: {
    orden: 2,
    label: 'Compact FF (NumPy)',
    arch: '26 → 16 → 3',
    layers: [26, 16, 3],
    recurrente: false,
    enfoque: 'Feedforward compacto · 1 capa oculta',
    salida: 'argmax de 3 · recto / izquierda / derecha',
    pesos: '≈ 483',
    cpu: 'Baja-media',
    muta: 'Rápida (espacio de búsqueda pequeño)',
    aprende:
      'Una SOLA capa oculta (LeakyReLU). En neuroevolución la profundidad estorba: ' +
      'cada capa extra agranda el espacio de búsqueda y la mutación compone ruido ' +
      'capa a capa, así que una red profunda evoluciona más lento y peor en tiempo ' +
      'limitado. Compacta = más evaluaciones/segundo y convergencia antes; LeakyReLU ' +
      'evita neuronas muertas.',
    codigo:
`h = leaky_relu(W1 @ x + b1)   # 16 neuronas
o = W2 @ h + b2               # 3 salidas
acción = argmax(o)            # recto | izq | der`,
  },
  basic: {
    orden: 3,
    label: 'Wide FF (NumPy)',
    arch: '26 → 52 → 26 → 1',
    layers: [26, 52, 26, 1],
    recurrente: false,
    enfoque: 'Teórico / expansivo',
    salida: '1 valor por rangos · <1/3 izq · medio recto · >2/3 der',
    pesos: '≈ 2.809',
    cpu: 'Alta',
    muta: 'Lenta (más genes que ajustar)',
    aprende:
      'Sigue la regla teórica de que la primera capa oculta DUPLICA la entrada. ' +
      'Con una sola salida, decide el giro por rangos sobre su valor aplastado a ' +
      '[0,1]. Máxima expresividad, pero un espacio de búsqueda enorme: el genético ' +
      'tarda más en afinar. Útil como referencia teórica frente a los otros dos.',
    codigo:
`h1 = relu(W1 @ x  + b1)          # 52 = el doble de la entrada
h2 = relu(W2 @ h1 + b2)          # 26
v  = sigmoide(W3 @ h2 + b3)      # UNA salida -> [0, 1]
acción = izq si v<1/3, der si v>2/3, si no recto`,
  },
};

const MOTORES_ORDENADOS = Object.entries(MOTORES)
  .map(([id, m]) => ({ id, ...m }))
  .sort((a, b) => a.orden - b.orden);

/* Diagrama de la red del motor activo. Dibuja una columna de nodos por capa a
   partir de `layers`, así que se redibuja solo al cambiar de motor. */
function NetworkDiagram({ layers, recurrente }) {
  const etiqueta = (i) =>
    i === 0 ? 'Entrada' : i === layers.length - 1 ? 'Salida' : `Oculta ${i}`;
  return (
    <div>
      <div className="flex items-start justify-between gap-1 overflow-x-auto py-1">
        {layers.map((n, i) => (
          <div key={i} className="flex items-center gap-1 shrink-0">
            <div className="flex flex-col items-center gap-1 min-w-[56px]">
              <div className="text-xl font-semibold tabular-nums text-accent">{n}</div>
              <div className="flex flex-col gap-1">
                {Array.from({ length: Math.min(n, 5) }).map((_, k) => (
                  <span key={k} className="w-2 h-2 rounded-full bg-accent/40" />
                ))}
                {n > 5 && <span className="text-[10px] text-muted leading-none">⋮</span>}
              </div>
              <div className="text-[11px] text-muted mt-1">{etiqueta(i)}</div>
            </div>
            {i < layers.length - 1 && <span className="text-muted text-lg self-center">→</span>}
          </div>
        ))}
      </div>
      <p className="text-xs text-muted mt-2 leading-relaxed">
        {recurrente
          ? '↻ La capa oculta se realimenta con su estado anterior: memoria (W_rec).'
          : 'Feedforward puro: la información fluye en una sola dirección, sin memoria.'}
      </p>
    </div>
  );
}

function ModuloCerebro() {
  const [sel, setSel] = useState('rayos');
  const [motor, setMotor] = useState('intermated');   // selectedEngine
  const activa = ENTRADAS.find((e) => e.id === sel);
  const m = MOTORES[motor];

  return (
    <div className="space-y-5">
      {/* ---- Selector de motor: gobierna TODA la sección del Cerebro ---- */}
      <Card title="Motor de la IA" badge={<Badge tono="ok">✅ 3 motores reales</Badge>}>
        <Hint className="mb-4">
          Cada IA se crea con un motor, y cada motor es una red neuronal distinta: por eso
          <span className="text-ink"> aprenden de forma diferente</span>. El juego y los 26
          sensores son los mismos; cambia la topología del cerebro. Elige uno y toda esta
          sección se actualiza:
        </Hint>

        {/* Selector muy visible: tabs a lo ancho, estado activo y badge. */}
        <div className="flex flex-col sm:flex-row gap-2 mb-5" role="tablist"
             aria-label="Motor de red">
          {MOTORES_ORDENADOS.map((x) => {
            const activo = motor === x.id;
            return (
              <button
                key={x.id}
                role="tab"
                aria-selected={activo}
                onClick={() => setMotor(x.id)}
                className={`flex-1 text-left p-4 rounded-panel border-2 transition
                  hover:-translate-y-0.5
                  ${activo ? 'border-accent bg-accent/5' : 'border-line'}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm font-semibold ${activo ? 'text-ink' : 'text-muted'}`}>
                    {x.label}
                  </span>
                  {activo && <Badge tono="ok">activo</Badge>}
                </div>
                <div className="text-xs text-accent tabular-nums mt-1">{x.arch}</div>
              </button>
            );
          })}
        </div>

        {/* Definición del motor activo — cambia con `motor` (selectedEngine). */}
        <div className="bg-surface2 border border-line rounded-xl p-4 mb-4">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-1">
            <div className="text-base font-semibold text-ink">{m.label}</div>
            <Badge tono="info">{m.enfoque}</Badge>
          </div>
          <NetworkDiagram layers={m.layers} recurrente={m.recurrente} />
        </div>

        <p className="text-sm text-muted leading-relaxed mb-4">{m.aprende}</p>

        <Code caption={`Cómo «${m.label}» decide un giro (forward de su red).`}>
          {m.codigo}
        </Code>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
          {[
            { k: 'Entrada → Salida', v: `26 → ${m.layers[m.layers.length - 1]}` },
            { k: 'Pesos (ADN)', v: m.pesos },
            { k: 'Uso de CPU', v: m.cpu },
            { k: 'Velocidad de mutación', v: m.muta },
          ].map((s) => (
            <div key={s.k} className="bg-surface2 border border-line rounded-xl px-3 py-2">
              <div className="text-xs text-muted">{s.k}</div>
              <div className="text-sm text-ink mt-0.5">{s.v}</div>
            </div>
          ))}
        </div>

        <div className="mt-3 text-sm text-ink">
          <span className="text-muted">Salida:</span> {m.salida}
        </div>

        <Hint className="mt-4 text-xs">
          Se elige en <span className="text-ink">Entrenar IA → Motor de red</span> antes de
          evolucionar. La identidad de cada IA guardada es su <span className="text-ink">nombre</span>,
          su <span className="text-ink">motor</span> y su <span className="text-ink">nivel</span>
          {' '}actual (visibles en el Historial). Continuar un linaje conserva su motor: no se
          cambia la arquitectura a medias.
        </Hint>
      </Card>

      {/* ---- Percepción: común a todos los motores ---- */}
      <Card
        title="Las 26 entradas · percepción común a todos los motores"
        badge={<Badge tono="info">interactivo</Badge>}
      >
        <Hint className="mb-4">
          Todos los motores ven el tablero con estos mismos 26 sensores; lo que cambia es cómo
          los procesan. Toca cada bloque. La suma es siempre{' '}
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
            Los tres motores se <em>evolucionan</em>, no se entrenan por gradiente. Sin
            <em> backpropagation</em>, un framework de deep learning sería peso muerto:
          </Hint>
          <ul className="space-y-2 text-sm text-muted leading-relaxed">
            <li>▸ Sin autograd ni GPU: el forward es un puñado de multiplicaciones de matrices que NumPy hace de sobra en CPU.</li>
            <li>▸ Instalación mínima: <code className="text-ink">numpy · fastapi · uvicorn</code>. Sin CUDA, sin ruedas de 2&nbsp;GB.</li>
            <li>▸ Cero caja negra: coherente con el objetivo educativo del proyecto: se puede leer cada operación.</li>
          </ul>
        </Card>

        {/* Memoria: solo el motor recurrente la tiene; la tarjeta cambia con él. */}
        {m.recurrente ? (
          <Card title="Memoria recurrente (W_rec)" badge={<Badge tono="ok">✅ en este motor</Badge>}>
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
        ) : (
          <Card title="Sin memoria recurrente" badge={<Badge tono="mute">feedforward</Badge>}>
            <Hint>
              El motor <span className="text-ink">{m.label}</span> es feedforward puro: cada
              decisión depende solo de lo que ve en ese turno, sin arrastrar estado del
              anterior. Gana simplicidad y velocidad de mutación; renuncia a la memoria
              intra-partida. Para planificación que dependa de "por dónde venía", el motor{' '}
              <span className="text-ink">RNN Recurrente</span> es el indicado.
            </Hint>
          </Card>
        )}
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
        <code className="text-ink">TECHNICAL_PROOF.md</code>,{' '}
        <code className="text-ink">ENGINES.md</code> y{' '}
        <code className="text-ink">PLANNING.md</code>.
      </p>
    </div>
  );
}
