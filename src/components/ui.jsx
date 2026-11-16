/* Piezas de interfaz. Todos los colores salen de las variables del tema. */
import { useState } from 'react';
import { ESTADOS } from '../lib/api';

export function Panel({ children, className = '', titulo, accion }) {
  return (
    <section className={`min-w-0 bg-surface border border-line rounded-panel p-4 sm:p-5 ${className}`}>
      {(titulo || accion) && (
        <div className="flex items-center justify-between gap-3 mb-3">
          {titulo && <h2 className="text-base font-semibold tracking-tight">{titulo}</h2>}
          {accion}
        </div>
      )}
      {children}
    </section>
  );
}

export function Nota({ children, className = '' }) {
  return <p className={`text-sm leading-relaxed text-muted ${className}`}>{children}</p>;
}

export function Dato({ etiqueta, valor, acento = false, ayuda }) {
  return (
    <div className="bg-surface2 border border-line rounded-xl px-3 py-2" title={ayuda}>
      <div className="text-xs text-muted">{etiqueta}</div>
      <div className={`text-lg font-semibold tabular-nums ${acento ? 'text-accent' : ''}`}>{valor}</div>
    </div>
  );
}

const VARIANTES = {
  normal: 'bg-surface2 text-ink border-line hover:bg-line',
  primario: 'bg-accent text-on-accent border-accent hover:brightness-110 font-medium',
  peligro: 'bg-danger text-on-danger border-danger hover:brightness-110 font-medium',
};

export function Boton({ variante = 'normal', className = '', ...props }) {
  return (
    <button {...props}
      className={`px-3 py-1.5 rounded-lg border text-sm transition disabled:opacity-40
        disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`} />
  );
}

export function Campo({ etiqueta, ayuda, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="block text-xs text-muted mb-1" title={ayuda}>{etiqueta}</span>
      {children}
    </label>
  );
}

const ENTRADA = 'w-full bg-surface2 border border-line rounded-lg px-2 py-1.5 text-sm text-ink';

export function Numero({ valor, cambiar, min, max, paso = 1 }) {
  return <input type="number" className={ENTRADA} value={valor} min={min} max={max} step={paso}
    onChange={(e) => cambiar(e.target.value === '' ? '' : Number(e.target.value))} />;
}

export function Selector({ valor, cambiar, opciones }) {
  return (
    <select className={ENTRADA} value={valor ?? ''} onChange={(e) => cambiar(e.target.value)}>
      {Object.entries(opciones).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select>
  );
}

export function Interruptor({ valor, cambiar, etiqueta }) {
  return (
    <label className="inline-flex items-center gap-2 text-sm cursor-pointer select-none">
      <input type="checkbox" checked={!!valor} onChange={(e) => cambiar(e.target.checked)}
        className="accent-[var(--accent)] w-4 h-4" />
      {etiqueta}
    </label>
  );
}

export function Segmentado({ opciones, valor, cambiar }) {
  return (
    <div className="inline-flex flex-wrap max-w-full bg-surface2 border border-line rounded-lg p-0.5">
      {Object.entries(opciones).map(([k, v]) => (
        <button key={k} onClick={() => cambiar(k)}
          className={`px-3 py-1 text-sm rounded-md transition ${valor === k ? 'bg-accent text-on-accent' : 'text-muted hover:text-ink'}`}>
          {v}
        </button>
      ))}
    </div>
  );
}

export function Insignia({ children, tono = 'normal', title }) {
  const tonos = {
    normal: 'border-line text-muted',
    acento: 'border-accent text-accent bg-accent/10',
    peligro: 'border-danger text-danger bg-danger/10',
    ok: 'border-snake text-snake bg-snake/10',
    aviso: 'border-food/60 text-food bg-food/10',
  };
  return <span title={title} className={`inline-flex items-center px-2 py-0.5 rounded-md border text-xs font-medium ${tonos[tono]}`}>{children}</span>;
}

export function InsigniaEstado({ estado }) {
  const tono = { validado: 'ok', evaluado: 'acento', entrenado: 'acento', preentrenado: 'ok', pendiente: 'normal' }[estado] || 'normal';
  return <Insignia tono={tono}>{ESTADOS[estado] || estado}</Insignia>;
}

export function NivelE({ nivel, record }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <Insignia tono="acento" title="Nivel de la partida actual">E{nivel ?? 0}</Insignia>
      {record !== undefined && <Insignia title="Mejor nivel histórico">récord E{record ?? 0}</Insignia>}
    </span>
  );
}

export function Aviso({ error }) {
  if (!error) return null;
  return <div className="text-sm text-danger border border-danger/40 bg-danger/10 rounded-lg px-3 py-2">{error}</div>;
}

export function Vacio({ children }) {
  return <div className="text-sm text-muted border border-dashed border-line rounded-xl px-4 py-6 text-center">{children}</div>;
}

export function Progreso({ trabajo, cancelar }) {
  if (!trabajo) return null;
  const p = trabajo.total ? trabajo.hechos / trabajo.total : 0;
  return (
    <div className="bg-surface2 border border-line rounded-xl p-3 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span>Trabajo <b>{trabajo.tipo}</b> · {trabajo.estado.replace('_', ' ')} · {trabajo.hechos}/{trabajo.total || '?'} · {trabajo.segundos} s</span>
        {trabajo.estado === 'en_curso' && cancelar && <Boton onClick={cancelar}>Cancelar</Boton>}
      </div>
      <div className="h-1.5 bg-line rounded-full overflow-hidden"><div className="h-full bg-accent transition-all" style={{ width: `${p * 100}%` }} /></div>
      {trabajo.ultimo && <div className="text-xs text-muted">Último episodio: {trabajo.ultimo.manzanas} manzanas · {trabajo.ultimo.pasos} pasos · E{trabajo.ultimo.nivel} · fin: {trabajo.ultimo.causa_fin}</div>}
      {trabajo.error && <Aviso error={trabajo.error} />}
    </div>
  );
}

export function Plegable({ titulo, children, abierto = false }) {
  const [a, setA] = useState(abierto);
  return (
    <div className="border border-line rounded-xl">
      <button onClick={() => setA(!a)} className="w-full text-left px-3 py-2 text-sm font-medium flex justify-between">
        {titulo}<span className="text-muted">{a ? '−' : '+'}</span>
      </button>
      {a && <div className="px-3 pb-3">{children}</div>}
    </div>
  );
}
