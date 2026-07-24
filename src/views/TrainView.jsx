/* ============================================================================
   Entrenar IA
   ----------------------------------------------------------------------------
   El selector de carpeta es el corazon de esta vista: si el nombre YA existe se
   continua ese linaje (hereda sus pesos y le suma generaciones); si es nuevo,
   nace un especimen desde cero. Se avisa antes de entrenar para que nadie
   sobrescriba su mejor serpiente por accidente.

   Encima de eso hay tres cosas mas:

   - COLA. Se pueden marcar varias IAs y entrenarlas en orden, una detras de
     otra. La cola la gestiona `useTrainingQueue`; aqui solo se ejecuta. Cada IA
     abre su PROPIA conexion `/ws/train`, que es lo que hace que el servidor no
     necesite saber nada de colas: sigue atendiendo un entrenamiento por socket,
     exactamente como antes.

   - PARAMETROS. Agentes, generaciones y herencias viajan al servidor y los usa
     el algoritmo de verdad (ver `snake_neuroevolution.train`).

   - MODO INFINITO. Sin tope de generaciones. La diferencia importante esta en
     como se termina: "Detener y guardar" cierra la generacion en curso y guarda;
     "Descartar" tira el trabajo, que es lo que hacia siempre el boton Cancelar.
   ============================================================================ */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Board from '../components/Board';
import AIQueue from '../components/AIQueue';
import { Panel, Title, Hint, Stat, Button, Field, LevelBadge, RangeField, Toggle, Segmented }
  from '../components/ui';
import { api, wsURL } from '../lib/api';
import { useLocalState } from '../lib/useLocalState';
import { useTrainingQueue } from '../lib/useTrainingQueue';

const MAX_LOG = 60;   // Ver nota en `anotar`

/* Tiempo transcurrido en formato corto. En modo infinito una tanda puede durar
   horas, asi que la hora aparece solo cuando hace falta. */
function duracion(ms) {
  if (!ms || ms < 0) return '0:00';
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const dosDigitos = (n) => String(n).padStart(2, '0');
  return h > 0 ? `${h}:${dosDigitos(m)}:${dosDigitos(s)}` : `${m}:${dosDigitos(s)}`;
}

export default function TrainView({ theme, config, limits = {}, engines = [],
                                   defaultEngine, models, onSaved }) {
  const [nombre, setNombre] = useState('');
  const [generaciones, setGeneraciones] = useState(config.generations);
  const [existente, setExistente] = useState(null);   // Modelo si el nombre ya existe
  const [entrenando, setEntrenando] = useState(false);
  const [pausado, setPausado] = useState(false);
  const [deteniendo, setDeteniendo] = useState(false);
  const [snake, setSnake] = useState(null);
  const [progreso, setProgreso] = useState(null);
  const [nivel, setNivel] = useState(null);         // {nivel, etiqueta, cobertura} en vivo
  const [log, setLog] = useState([]);
  const [estado, setEstado] = useState('Elige un nombre y entrena.');
  const [enCurso, setEnCurso] = useState(null);     // Nombre de la IA que se entrena
  const [restantes, setRestantes] = useState(0);    // IAs que quedan en la cola
  const [inicio, setInicio] = useState(null);
  const [ahora, setAhora] = useState(Date.now());

  /* Parametros del algoritmo. Se recuerdan entre sesiones porque son decisiones
     de trabajo, no configuracion del servidor (ver useLocalState). Las
     generaciones NO se persisten aqui a proposito: ya tienen su sitio en
     Configuracion y el servidor manda sobre ellas. */
  const [agentes, setAgentes] = useLocalState('entrenar-agentes',
    limits.default_agents ?? config.pop_size ?? 25);
  const [herencias, setHerencias] = useLocalState('entrenar-herencias',
    limits.default_elite ?? 3);
  const [infinito, setInfinito] = useState(false);

  /* Motor de red (arquitectura del cerebro) para los especimenes NUEVOS. Se
     recuerda entre sesiones como el resto de decisiones de trabajo. Al continuar
     un linaje existente NO se usa: cada IA conserva la arquitectura con la que
     nacio (el servidor lo impone), asi que aqui solo manda para IAs nuevas. */
  const [engine, setEngine] = useLocalState('entrenar-engine',
    defaultEngine || 'intermated');
  const engineSel = engines.find((e) => e.id === engine);

  const cola = useTrainingQueue(models);
  const { seleccionadas } = cola;

  const wsRef        = useRef(null);
  const pendientesRef = useRef([]);   // Nombres que faltan por entrenar
  const abortadoRef  = useRef(false); // "Descartar" corta tambien el resto de la cola
  const siguienteRef = useRef(() => {});

  // Limites efectivos: si el servidor no los publica (version anterior), se usan
  // los mismos numeros que el nucleo aplicaria de todos modos.
  const minAgentes = limits.min_agents ?? 4;
  const maxAgentes = limits.max_agents ?? 100;
  // La elite no puede ocupar la poblacion entera o no habria descendencia y la
  // evolucion se pararia en seco. El nucleo lo recorta igual; aqui se impide
  // ademas que el control llegue a ofrecer el valor imposible.
  const maxHerencias = Math.max(1, agentes - 1);
  const herenciasEfectivas = Math.min(Math.max(1, herencias), maxHerencias);

  useEffect(() => setGeneraciones(config.generations), [config.generations]);

  /* Consulta si el nombre ya tiene carpeta, con retardo para no lanzar una
     peticion por cada tecla pulsada. */
  useEffect(() => {
    if (!nombre.trim()) { setExistente(null); return undefined; }
    const t = setTimeout(async () => {
      try {
        const r = await api.checkName(nombre.trim());
        setExistente(r.existe ? r.model : null);
      } catch { setExistente(null); }
    }, 300);
    return () => clearTimeout(t);
  }, [nombre]);

  /* Al elegir una IA que ya existe se muestra SU nivel guardado, sin necesidad
     de entrenarla: deja claro que su entrenamiento se conserva. Si es un nombre
     nuevo (y no se esta entrenando) no hay nivel todavia. */
  useEffect(() => {
    if (existente) {
      setNivel({ nivel: existente.nivel, etiqueta: existente.nivel_etiqueta,
                 cobertura: existente.cobertura });
    } else if (!entrenando) {
      setNivel(null);
    }
  }, [existente, entrenando]);

  /* Cronometro. El intervalo solo existe mientras se entrena y se limpia al
     parar o al desmontar: un setInterval huerfano seguiria despertando a React
     cada segundo con la vista ya cerrada. */
  useEffect(() => {
    if (!entrenando) return undefined;
    const id = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(id);
  }, [entrenando]);

  // Al desmontar hay que cerrar el socket, o el entrenamiento seguiria
  // quemando CPU en el servidor con la vista ya cerrada. Se vacia tambien la
  // cola: nadie va a recoger el 'done' de la IA siguiente.
  useEffect(() => () => {
    abortadoRef.current = true;
    pendientesRef.current = [];
    wsRef.current?.close();
  }, []);

  /* El registro de generaciones se recorta. En modo infinito esto crece sin
     techo -una generacion por segundo durante horas- y era la unica fuga de
     memoria real de la vista: miles de nodos en el DOM y un array que nunca
     deja de crecer. Sesenta lineas es mas de lo que cabe en pantalla. */
  const anotar = useCallback((msg) => {
    setLog((l) => [msg, ...l].slice(0, MAX_LOG));
  }, []);

  /* Abre UNA sesion de entrenamiento. Al terminar (por lo que sea) pasa el
     testigo a la siguiente IA de la cola a traves de `siguienteRef`. */
  const abrirSesion = useCallback((nombreIA) => {
    const ws = new WebSocket(wsURL('/ws/train'));
    wsRef.current = ws;
    setEnCurso(nombreIA || '(nombre automático)');
    setPausado(false);
    setDeteniendo(false);
    setProgreso(null);
    setLog([]);
    // El nivel NO se borra: si la IA ya existe se mantiene su nivel guardado
    // visible durante la tanda (solo puede subir, nunca baja).
    setEstado('Conectando…');

    ws.onopen = () => {
      ws.send(JSON.stringify({
        action: 'start',
        nombre: nombreIA || null,
        generations: generaciones,
        grid: config.grid,
        agents: agentes,
        elite: herenciasEfectivas,
        infinite: infinito,
        // Solo se aplica a IAs nuevas: si el nombre ya existe, el servidor
        // conserva el motor del linaje e ignora este valor.
        engine,
      }));
    };

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);

      if (msg.type === 'info') {
        const cuantas = msg.infinito
          ? 'sin límite de generaciones'
          : `${msg.generations} generaciones`;
        setEstado(msg.continua
          ? `Continuando el linaje de ${msg.nombre} (${cuantas}, ${msg.agents} agentes)…`
          : `Evolucionando a ${msg.nombre} desde cero (${cuantas}, ${msg.agents} agentes)…`);

      } else if (msg.type === 'step') {
        setSnake(msg.snake);
        setProgreso(msg);

      } else if (msg.type === 'gen') {
        anotar(msg);
        setNivel({ nivel: msg.nivel, etiqueta: msg.nivel_etiqueta, cobertura: msg.cobertura });

      } else if (msg.type === 'paused') {
        setPausado(msg.paused);

      } else if (msg.type === 'stopping') {
        setDeteniendo(true);
        setEstado('Cerrando la generación en curso para guardar…');

      } else if (msg.type === 'done') {
        const m = msg.model;
        if (m.nivel != null) setNivel({ nivel: m.nivel, etiqueta: m.nivel_etiqueta, cobertura: m.cobertura });
        const nivelTxt = m.nivel_etiqueta ? ` · ${m.nivel_etiqueta}` : '';
        setEstado(msg.continua
          ? `${m.nombre} acumula ya ${m.generaciones} generaciones · récord ${m.fitness}${nivelTxt}`
          : `${m.nombre} guardada en historial/${m.carpeta}/ · récord ${m.fitness}${nivelTxt}`);
        onSaved?.();

      } else if (msg.type === 'cancelled') {
        setEstado('Entrenamiento descartado. No se guardó nada.');

      } else if (msg.type === 'error') {
        setEstado(`Error: ${msg.detail}`);
      }
    };

    // Un solo punto de relevo: pase lo que pase (fin, descarte o error de red),
    // el socket acaba cerrandose y es ahi donde arranca la IA siguiente. Encadenar
    // desde 'done' dejaria la cola colgada si la conexion se cae.
    ws.onclose = () => {
      wsRef.current = null;
      setPausado(false);
      setDeteniendo(false);
      siguienteRef.current();
    };
    ws.onerror = () => setEstado('Error de conexión con el servidor de la IA.');
  }, [generaciones, config.grid, agentes, herenciasEfectivas, infinito, engine, onSaved, anotar]);

  /* Toma la siguiente IA pendiente. Si no queda ninguna (o se abortó), cierra
     el ciclo y devuelve los controles. */
  const siguiente = useCallback(() => {
    const quedan = pendientesRef.current;
    if (abortadoRef.current || quedan.length === 0) {
      pendientesRef.current = [];
      setRestantes(0);
      setEntrenando(false);
      setEnCurso(null);
      return;
    }
    const nombreIA = quedan.shift();
    setRestantes(quedan.length);
    abrirSesion(nombreIA);
  }, [abrirSesion]);

  // Se refresca en cada render para que `ws.onclose` -creado en un render
  // anterior- siempre llame a la version actual, sin reabrir el socket.
  siguienteRef.current = siguiente;

  const lanzar = useCallback((lista) => {
    if (entrenando || lista.length === 0) return;
    abortadoRef.current = false;
    pendientesRef.current = [...lista];
    setEntrenando(true);
    setInicio(Date.now());
    setAhora(Date.now());
    siguiente();
  }, [entrenando, siguiente]);

  const entrenarCola = () => lanzar(seleccionadas.map((m) => m.nombre));
  const entrenarUna  = () => lanzar([nombre.trim()]);

  const enviar = (accion) => wsRef.current?.send(JSON.stringify({ action: accion }));

  const alternarPausa = () => enviar(pausado ? 'resume' : 'pause');

  /* Detener: cierra la generacion en curso, GUARDA y pasa a la siguiente IA. */
  const detener = () => {
    setDeteniendo(true);
    setEstado('Deteniendo… se guardará al cerrar la generación en curso.');
    enviar('stop');
  };

  /* Descartar: tira el trabajo de la IA actual Y cancela el resto de la cola.
     Son dos efectos, y por eso el boton no comparte nombre con "Detener". */
  const descartar = () => {
    abortadoRef.current = true;
    pendientesRef.current = [];
    setRestantes(0);
    setEstado('Descartando…');
    enviar('cancel');
  };

  const pct = useMemo(() => {
    if (!progreso || progreso.infinito || !progreso.generations) return 0;
    return Math.min(100, ((progreso.generation - 1 + progreso.agent / progreso.pop_size)
      / progreso.generations) * 100);
  }, [progreso]);

  const generacionTxt = progreso
    ? (progreso.infinito ? `${progreso.generation} · ∞` : `${progreso.generation}/${progreso.generations}`)
    : '—';

  const puedeCola = seleccionadas.length > 0;
  const horas = infinito
    ? 'Sin tope: evoluciona hasta que pulses «Detener y guardar».'
    : `Se evolucionarán ${generaciones} generación${generaciones === 1 ? '' : 'es'}.`;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,560px)_1fr] items-start">
      {/* Mismo limite responsivo que en Jugar: el tablero cuadrado nunca debe
          desbordar el alto del dispositivo (ver PlayView). */}
      <div className="w-full max-w-[min(100%,calc(100svh-13rem))] mx-auto">
        <Board snake={snake} grid={config.grid} theme={theme} />
      </div>

      <Panel>
        <Title>Entrenar IA</Title>
        <Hint className="mt-2 mb-5">
          Cada espécimen vive en su carpeta. Los mejores hijos de una generación
          son la base de la siguiente.
        </Hint>

        <Field
          label="Carpeta del espécimen"
          help={
            existente
              ? `Ya existe: se CONTINUARÁ su linaje. Lleva ${existente.generaciones ?? '?'} generaciones y su récord es ${existente.fitness}.`
              : nombre.trim()
                ? 'Nombre nuevo: se creará una carpeta y la IA nacerá desde cero.'
                : 'Escribe un nombre o marca IAs en la cola. Si lo dejas vacío se genera uno.'
          }
        >
          <input
            type="text"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            disabled={entrenando}
            maxLength={40}
            placeholder="Serpiente_Pro_v1"
            className="w-full bg-surface2 border border-line rounded-xl px-4 py-2.5
                       text-ink placeholder:text-muted focus:outline-2
                       focus:outline-offset-2 focus:outline-accent
                       disabled:opacity-40"
          />
        </Field>

        {/* --- Motor de red: la arquitectura del cerebro que evolucionara ---
            Solo elegible para especimenes NUEVOS. Al continuar un linaje se
            muestra el suyo, heredado: no se puede cambiar de arquitectura a
            medias sin tirar todo lo aprendido. */}
        {engines.length > 0 && (
          <Field
            label="Motor de red"
            help={
              existente
                ? 'Este linaje conserva su motor: no se puede cambiar la arquitectura de una IA a medias.'
                : engineSel
                  ? `${engineSel.arch} — ${engineSel.resumen}`
                  : 'Arquitectura del cerebro que evolucionará.'
            }
          >
            {existente ? (
              <div className="inline-flex items-center gap-2 bg-surface2 border border-line
                              rounded-xl px-4 py-2.5 text-sm text-ink">
                🧠 {engines.find((e) => e.id === (existente.engine || 'intermated'))?.label
                     || 'Intermated'}
                <span className="text-muted text-xs">· heredado</span>
              </div>
            ) : (
              <div className={entrenando ? 'opacity-40 pointer-events-none' : ''}>
                <Segmented
                  value={engine}
                  onChange={setEngine}
                  options={engines.map((e) => ({ value: e.id, label: e.label }))}
                />
              </div>
            )}
          </Field>
        )}

        {/* Administracion de IAs: seleccion, orden, renombrado y borrado. */}
        <AIQueue cola={cola} bloqueada={entrenando} onCambiado={onSaved} />

        {/* --- Parametros del algoritmo --- */}
        <RangeField
          label={`Agentes por generación: ${agentes}`}
          help={`Cuántas serpientes compiten a la vez. Más agentes exploran más soluciones por generación, pero cada generación tarda proporcionalmente más. Entre ${minAgentes} y ${maxAgentes}.`}
          value={agentes}
          min={minAgentes}
          max={maxAgentes}
          disabled={entrenando}
          onChange={setAgentes}
        />

        <RangeField
          label={`Generaciones: ${generaciones}`}
          help={infinito
            ? 'Ignorado en modo infinito: no hay número máximo de generaciones.'
            : `Tablero ${config.grid}×${config.grid}. ${horas}`}
          value={generaciones}
          min={limits.min_generations ?? 1}
          max={limits.max_generations ?? 100}
          disabled={entrenando || infinito}
          onChange={setGeneraciones}
        />

        <RangeField
          label={`Herencias por generación: ${herenciasEfectivas}`}
          help={`Cuántos cerebros pasan INTACTOS a la generación siguiente, sin cruce ni mutación (élite). Más herencias conservan lo aprendido y convergen antes; menos exploran más a riesgo de perder buenas soluciones. Máximo ${maxHerencias} con ${agentes} agentes: si heredara la población entera no nacería ningún hijo y la evolución se detendría.`}
          value={herenciasEfectivas}
          min={1}
          max={maxHerencias}
          disabled={entrenando}
          onChange={setHerencias}
        />

        <Toggle
          checked={infinito}
          onChange={setInfinito}
          disabled={entrenando}
          label="Entrenar infinitamente"
          help="La evolución no se detiene sola: sigue generación tras generación hasta que pulses «Detener y guardar», que cierra la generación en curso y conserva todo lo aprendido."
        />

        {/* --- Controles --- */}
        <div className="flex flex-wrap gap-2 mb-5">
          {!entrenando ? (
            <>
              {puedeCola && (
                <Button variant="primary" onClick={entrenarCola}>
                  {infinito
                    ? `Entrenar cola sin límite (${seleccionadas.length})`
                    : `Entrenar cola (${seleccionadas.length})`}
                </Button>
              )}
              <Button
                variant={puedeCola ? 'ghost' : 'primary'}
                onClick={entrenarUna}
              >
                {puedeCola
                  ? `Solo ${nombre.trim() || 'una nueva'}`
                  : existente ? 'Seguir entrenando' : 'Entrenar nueva IA'}
              </Button>
            </>
          ) : (
            <>
              <Button onClick={alternarPausa} disabled={deteniendo}>
                {pausado ? '▶ Continuar' : '⏸ Pausar'}
              </Button>
              <Button variant="primary" onClick={detener} disabled={deteniendo}>
                {deteniendo ? 'Deteniendo…' : 'Detener y guardar'}
              </Button>
              <Button variant="danger" onClick={descartar}>Descartar</Button>
            </>
          )}
        </div>

        {/* --- Indicadores de estado --- */}
        {entrenando && (
          <div className="flex flex-wrap items-center gap-2 mb-4 text-xs">
            <span className="px-2 py-1 rounded-md bg-accent/10 border border-accent
                             text-accent font-medium">
              {enCurso}
            </span>
            {infinito && (
              <span className="px-2 py-1 rounded-md bg-surface2 border border-line text-muted">
                ∞ modo infinito
              </span>
            )}
            {pausado && (
              <span className="px-2 py-1 rounded-md bg-surface2 border border-line text-ink">
                ⏸ en pausa
              </span>
            )}
            {restantes > 0 && (
              <span className="px-2 py-1 rounded-md bg-surface2 border border-line text-muted">
                {restantes} en cola
              </span>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 mb-4">
          <Stat label="Generación" value={generacionTxt} />
          <Stat label="Mejor fitness" value={progreso?.best_fitness ?? 0} accent />
          <Stat label="Agentes activos"
                value={progreso ? `${progreso.agent}/${progreso.pop_size}` : '—'} />
          {/* `ahora` deja de refrescarse al parar, asi que el cronometro se
              congela solo en el tiempo final: no hace falta guardarlo aparte. */}
          <Stat label="Tiempo" value={inicio ? duracion(ahora - inicio) : '—'} />
        </div>

        {/* Nivel de inteligencia alcanzado (ver plan.txt): sube con la cobertura. */}
        <div className="flex items-center justify-between gap-3 bg-surface2 border
                        border-line rounded-xl px-4 py-3 mb-4">
          <div>
            <div className="text-xs text-muted">Nivel de inteligencia</div>
            <div className="text-sm text-ink mt-0.5">
              {nivel?.etiqueta ?? 'Aún sin entrenar'}
              {nivel?.cobertura != null &&
                <span className="text-muted"> · cobertura {(nivel.cobertura * 100).toFixed(1)}%</span>}
            </div>
          </div>
          {nivel && <LevelBadge nivel={nivel.nivel} etiqueta={nivel.etiqueta} />}
        </div>

        {/* En modo infinito no hay porcentaje que mostrar -no existe un final-,
            asi que la barra late en vez de mentir con un progreso inventado. */}
        <div className="h-1.5 bg-surface2 rounded-full overflow-hidden mb-5">
          {progreso?.infinito ? (
            <div className="h-full w-full bg-accent/60 animate-pulse" />
          ) : (
            <div className="h-full bg-accent transition-[width] duration-300"
                 style={{ width: `${pct}%` }} />
          )}
        </div>

        {log.length > 0 && (
          <div className="max-h-40 overflow-y-auto space-y-1 mb-4">
            {log.map((g) => (
              <div key={g.generation}
                   className="text-xs text-muted bg-surface2 rounded-lg px-3 py-1.5">
                Gen {g.generation} · mejor <b className="text-accent">{g.best}</b>
                {' '}· promedio {g.avg.toFixed(1)} · tamaño máx {g.best_length}
              </div>
            ))}
          </div>
        )}

        <p className="text-xs text-muted leading-relaxed">{estado}</p>
      </Panel>
    </div>
  );
}
