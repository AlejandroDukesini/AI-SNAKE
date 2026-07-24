/* ============================================================================
   Crear IA — formulario de creación con previsualización del motor
   ----------------------------------------------------------------------------
   Componentes pequeños y desacoplados (PillTag, EngineCard, NeuronVisualizer) que
   se componen en CreateAIPanel. Todo con tokens del tema (nada de colores fijos),
   así funciona en los tres temas y restilizar es trivial.

   IMPORTANTE — qué es y qué NO es esta vista:
   La previsualización (la animación de neuronas) es EDUCATIVA: muestra la forma de
   la red del motor elegido. El entrenamiento REAL no ocurre aquí: "Crear y
   entrenar" lleva el nombre y el motor a la pestaña «Entrenar IA», que es la que
   dispara la evolución de verdad por WebSocket. No hay lógica de juego aquí.
   ============================================================================ */

import { useState } from 'react';

/* -------------------------------------------------------------------------
   PillTag — etiqueta redonda seleccionable (tag cloud de IAs existentes)
   ------------------------------------------------------------------------- */
export function PillTag({ label, count, active = false, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm
        transition max-w-full
        ${active
          ? 'border-accent bg-accent/15 text-ink'
          : 'border-line bg-surface2 text-muted hover:text-ink hover:border-muted'}`}
    >
      <span className="truncate max-w-[11rem]">{label}</span>
      {count != null && (
        <span className="text-xs text-muted tabular-nums shrink-0">({count})</span>
      )}
    </button>
  );
}

/* -------------------------------------------------------------------------
   EngineCard — tarjeta de un nivel de complejidad / motor
   ------------------------------------------------------------------------- */
export function EngineCard({ engine, active = false, onSelect }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(engine.id)}
      aria-pressed={active}
      className={`text-left p-4 rounded-2xl border-2 transition hover:-translate-y-0.5
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
        ${active ? 'border-accent bg-accent/5' : 'border-line bg-surface2'}`}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className={`text-sm font-semibold ${active ? 'text-ink' : 'text-muted'}`}>
          {engine.nivel}
        </span>
        {active && <span className="w-2 h-2 rounded-full bg-accent shrink-0" />}
      </div>
      <div className="text-xs text-accent tabular-nums">{engine.arch}</div>
      <div className="text-xs text-muted mt-1 leading-snug">{engine.label}</div>
    </button>
  );
}

/* -------------------------------------------------------------------------
   NeuronVisualizer — animación de las capas del motor activo
   Dibuja una columna de nodos por capa (desde `layers`) y una onda de
   activación que las recorre: los nodos laten desfasados y un pulso viaja por
   cada conexión. Se redibuja solo al cambiar `layers`. Animaciones en index.css.
   ------------------------------------------------------------------------- */
export function NeuronVisualizer({ layers = [], recurrente = false }) {
  const etiqueta = (i) =>
    i === 0 ? 'Entrada' : i === layers.length - 1 ? 'Salida' : `Oculta ${i}`;

  if (!layers.length) {
    return <p className="text-sm text-muted text-center py-6">Sin motor que previsualizar.</p>;
  }

  return (
    <div className="w-full">
      <div className="w-full overflow-x-auto">
        <div className="flex items-stretch justify-center min-w-max py-3">
          {layers.map((n, i) => (
            <div key={i} className="flex items-stretch">
              {/* Columna de nodos de la capa */}
              <div className="flex flex-col items-center justify-center px-3">
                <div className="text-xs font-medium text-accent tabular-nums mb-2">{n}</div>
                <div className="flex flex-col gap-1.5">
                  {Array.from({ length: Math.min(n, 6) }).map((_, k) => (
                    <span
                      key={k}
                      className="w-3 h-3 rounded-full bg-accent node-glow"
                      style={{ animationDelay: `${i * 0.22 + k * 0.05}s` }}
                    />
                  ))}
                  {n > 6 && (
                    <span className="text-[10px] text-muted text-center leading-none">
                      +{n - 6}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-muted mt-2 whitespace-nowrap">{etiqueta(i)}</div>
              </div>

              {/* Conexión con pulso viajero hacia la capa siguiente */}
              {i < layers.length - 1 && (
                <div className="relative self-center w-8 sm:w-12 h-px bg-line mx-0.5">
                  <span
                    className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full
                               bg-accent flow-dot"
                    style={{ animationDelay: `${i * 0.22}s` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-muted text-center mt-1 leading-relaxed">
        {recurrente
          ? '↻ La capa oculta se realimenta con su estado anterior (memoria W_rec).'
          : 'Feedforward: los datos fluyen en una sola dirección, sin memoria.'}
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------------
   CreateAIPanel — compone todo lo anterior en el flujo de creación
   ------------------------------------------------------------------------- */
// Los tres motores reales mapeados a niveles de complejidad. El orden y las
// etiquetas son de presentación; el `id` es el motor real que entiende el backend.
const NIVEL = { basic: 'Basic', intermated: 'Intermediate', advanced: 'Advanced' };
const ORDEN = ['basic', 'intermated', 'advanced'];

/* Convierte "26 → 20 → 3" en [26, 20, 3]. La fuente es el `arch` que publica el
   backend, así que el diagrama nunca miente sobre la arquitectura real. */
function parseLayers(arch) {
  return String(arch || '')
    .split('→')
    .map((s) => parseInt(s.trim(), 10))
    .filter((n) => Number.isFinite(n));
}

export default function CreateAIPanel({ engines = [], models = [], engine, setEngine, onCreate }) {
  const [nombre, setNombre] = useState('');

  const cards = ORDEN
    .map((id) => engines.find((e) => e.id === id))
    .filter(Boolean)
    .map((e) => ({ id: e.id, nivel: NIVEL[e.id] || e.label, arch: e.arch, label: e.resumen }));

  const activo = cards.find((c) => c.id === engine) || cards[0];
  const layers = activo ? parseLayers(activo.arch) : [];

  const nombreLimpio = nombre.trim();
  const existe = models.some(
    (m) => (m.nombre || '').toLowerCase() === nombreLimpio.toLowerCase());

  if (cards.length === 0) {
    return (
      <p className="text-sm text-muted">
        No hay motores disponibles. Arranca el servidor de la IA para cargarlos.
      </p>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2 items-start">
      {/* --- Formulario --- */}
      <div className="space-y-6">
        <div>
          <label htmlFor="nueva-ia" className="block text-sm text-ink mb-2">
            Nombre de la IA
          </label>
          <input
            id="nueva-ia"
            type="text"
            value={nombre}
            maxLength={40}
            onChange={(e) => setNombre(e.target.value)}
            placeholder="Serpiente_Pro_v1"
            className="w-full bg-surface2 border border-line rounded-xl px-4 py-2.5
                       text-ink placeholder:text-muted focus:outline-2
                       focus:outline-offset-2 focus:outline-accent"
          />
          {nombreLimpio && (
            <p className={`text-xs mt-2 leading-relaxed ${existe ? 'text-accent' : 'text-muted'}`}>
              {existe
                ? 'Ya existe: al entrenar se CONTINUARÁ su linaje (conservando su motor).'
                : 'Nombre nuevo: la IA nacerá desde cero con el motor elegido.'}
            </p>
          )}

          {models.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-muted mb-2">IAs existentes (toca para reutilizar el nombre):</p>
              <div className="flex flex-wrap gap-2">
                {models.slice(0, 12).map((m) => (
                  <PillTag
                    key={m.carpeta}
                    label={m.nombre}
                    count={m.generaciones}
                    active={nombreLimpio.toLowerCase() === (m.nombre || '').toLowerCase()}
                    onClick={() => setNombre(m.nombre)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        <div>
          <p className="text-sm text-ink mb-2">Motor / complejidad de la red</p>
          <div className="grid grid-cols-3 gap-3">
            {cards.map((c) => (
              <EngineCard key={c.id} engine={c} active={engine === c.id} onSelect={setEngine} />
            ))}
          </div>
        </div>
      </div>

      {/* --- Previsualización del motor activo --- */}
      <div className="bg-surface border border-line rounded-panel p-5">
        <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
          <h3 className="font-medium text-ink">Previsualización · {activo?.nivel}</h3>
          <span className="text-xs text-accent tabular-nums">{activo?.arch}</span>
        </div>
        <p className="text-sm text-muted leading-relaxed mb-3">{activo?.label}</p>

        <div className="bg-surface2 border border-line rounded-xl p-3 mb-4">
          <NeuronVisualizer layers={layers} recurrente={engine === 'intermated'} />
        </div>

        <button
          type="button"
          onClick={() => onCreate?.(nombreLimpio, engine)}
          className="w-full px-4 py-2.5 rounded-xl border border-accent bg-accent
                     text-on-accent font-medium transition hover:brightness-110
                     focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          Crear y entrenar esta IA →
        </button>
        <p className="text-xs text-muted mt-2 text-center leading-relaxed">
          Te lleva a «Entrenar IA» con este motor y nombre listos para lanzar la evolución real.
        </p>
      </div>
    </div>
  );
}
