/* ============================================================================
   Entrenar IA
   ----------------------------------------------------------------------------
   El selector de carpeta es el corazon de esta vista: si el nombre YA existe se
   continua ese linaje (hereda sus pesos y le suma generaciones); si es nuevo,
   nace un especimen desde cero. Se avisa antes de entrenar para que nadie
   sobrescriba su mejor serpiente por accidente.
   ============================================================================ */

import { useCallback, useEffect, useRef, useState } from 'react';
import Board from '../components/Board';
import { Panel, Title, Hint, Stat, Button, Field, LevelBadge } from '../components/ui';
import { api, wsURL } from '../lib/api';

export default function TrainView({ theme, config, models, onSaved }) {
  const [nombre, setNombre] = useState('');
  const [generaciones, setGeneraciones] = useState(config.generations);
  const [existente, setExistente] = useState(null);   // Modelo si el nombre ya existe
  const [entrenando, setEntrenando] = useState(false);
  const [snake, setSnake] = useState(null);
  const [progreso, setProgreso] = useState(null);
  const [nivel, setNivel] = useState(null);         // {nivel, etiqueta, cobertura} en vivo
  const [log, setLog] = useState([]);
  const [estado, setEstado] = useState('Elige un nombre y entrena.');
  const wsRef = useRef(null);

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

  // Al desmontar hay que cerrar el socket, o el entrenamiento seguiria
  // quemando CPU en el servidor con la vista ya cerrada.
  useEffect(() => () => wsRef.current?.close(), []);

  const entrenar = useCallback(() => {
    if (entrenando) return;
    const ws = new WebSocket(wsURL('/ws/train'));
    wsRef.current = ws;
    setEntrenando(true);
    setLog([]);
    setProgreso(null);
    setNivel(null);
    setEstado('Conectando…');

    ws.onopen = () => {
      ws.send(JSON.stringify({
        action: 'start',
        nombre: nombre.trim() || null,
        generations: generaciones,
        grid: config.grid,
      }));
    };

    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);

      if (msg.type === 'info') {
        setEstado(msg.continua
          ? `Continuando el linaje de ${msg.nombre} (${msg.generations} generaciones más)…`
          : `Evolucionando a ${msg.nombre} desde cero (${msg.generations} generaciones)…`);

      } else if (msg.type === 'step') {
        setSnake(msg.snake);
        setProgreso(msg);

      } else if (msg.type === 'gen') {
        setLog((l) => [msg, ...l]);
        setNivel({ nivel: msg.nivel, etiqueta: msg.nivel_etiqueta, cobertura: msg.cobertura });

      } else if (msg.type === 'done') {
        const m = msg.model;
        if (m.nivel != null) setNivel({ nivel: m.nivel, etiqueta: m.nivel_etiqueta, cobertura: m.cobertura });
        const nivelTxt = m.nivel_etiqueta ? ` · ${m.nivel_etiqueta}` : '';
        setEstado(msg.continua
          ? `${m.nombre} acumula ya ${m.generaciones} generaciones · récord ${m.fitness}${nivelTxt}`
          : `${m.nombre} guardada en historial/${m.carpeta}/ · récord ${m.fitness}${nivelTxt}`);
        setEntrenando(false);
        onSaved?.();

      } else if (msg.type === 'cancelled') {
        setEstado('Entrenamiento cancelado. No se guardó nada.');
        setEntrenando(false);

      } else if (msg.type === 'error') {
        setEstado(`Error: ${msg.detail}`);
        setEntrenando(false);
      }
    };

    ws.onclose = () => { setEntrenando(false); wsRef.current = null; };
    ws.onerror = () => setEstado('Error de conexión con el servidor de la IA.');
  }, [entrenando, nombre, generaciones, config.grid, onSaved]);

  const cancelar = () => {
    wsRef.current?.send(JSON.stringify({ action: 'cancel' }));
    setEstado('Cancelando…');
  };

  const pct = progreso
    ? Math.min(100, ((progreso.generation - 1 + progreso.agent / progreso.pop_size)
        / progreso.generations) * 100)
    : 0;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,560px)_1fr] items-start">
      <Board snake={snake} grid={config.grid} theme={theme} />

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
                : 'Escribe un nombre o elige uno de abajo. Si lo dejas vacío se genera uno.'
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
                       focus:outline-offset-2 focus:outline-accent"
          />
        </Field>

        {models.length > 0 && (
          <Field label="…o abre una carpeta existente">
            <div className="flex flex-wrap gap-2">
              {models.slice(0, 6).map((m) => (
                <button
                  key={m.carpeta}
                  onClick={() => setNombre(m.nombre)}
                  disabled={entrenando}
                  className="px-3 py-1.5 rounded-lg border border-line bg-surface2
                             text-xs text-muted hover:text-ink hover:border-accent
                             transition disabled:opacity-40"
                >
                  {m.nombre}
                </button>
              ))}
            </div>
          </Field>
        )}

        <Field
          label={`Generaciones: ${generaciones}`}
          help={`Se evolucionarán ${generaciones} generación${generaciones === 1 ? '' : 'es'} de ${config.pop_size ?? 25} agentes en un tablero ${config.grid}×${config.grid}.`}
        >
          <input
            type="range"
            min={1}
            max={100}
            value={generaciones}
            disabled={entrenando}
            onChange={(e) => setGeneraciones(Number(e.target.value))}
            className="w-full accent-accent"
          />
        </Field>

        <div className="flex gap-2 mb-5">
          {!entrenando ? (
            <Button variant="primary" onClick={entrenar}>
              {existente ? 'Seguir entrenando' : 'Entrenar nueva IA'}
            </Button>
          ) : (
            <Button variant="danger" onClick={cancelar}>Cancelar</Button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 mb-4">
          <Stat label="Generación"
                value={progreso ? `${progreso.generation}/${progreso.generations}` : '—'} />
          <Stat label="Mejor fitness" value={progreso?.best_fitness ?? 0} accent />
          <Stat label="Agente"
                value={progreso ? `${progreso.agent}/${progreso.pop_size}` : '—'} />
          <Stat label="Tamaño actual" value={snake?.length ?? '—'} />
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

        <div className="h-1.5 bg-surface2 rounded-full overflow-hidden mb-5">
          <div className="h-full bg-accent transition-[width] duration-300"
               style={{ width: `${pct}%` }} />
        </div>

        {log.length > 0 && (
          <div className="max-h-40 overflow-y-auto space-y-1 mb-4">
            {log.map((g, i) => (
              <div key={i} className="text-xs text-muted bg-surface2 rounded-lg px-3 py-1.5">
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
