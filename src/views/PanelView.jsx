/* Panel principal: los cinco modelos. */
import { DIFICULTADES, fmt } from '../lib/api';
import { useDatos } from '../lib/hooks';
import { Boton, Insignia, InsigniaEstado, Nota, Panel } from '../components/ui';

export default function PanelView({ ir }) {
  const [modelos, recargar] = useDatos('/api/modelos');
  if (!modelos) return <Nota>Cargando…</Nota>;
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Nota>Cada modelo resuelve el mismo Snake con una metodología distinta. Los estados solo cambian con evidencia: entrenar, evaluar con semillas fijas y superar al azar.</Nota>
        <Boton onClick={recargar}>Actualizar</Boton>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {modelos.map((m) => <Tarjeta key={m.clave} m={m} ir={ir} />)}
      </div>
    </div>
  );
}

function Tarjeta({ m, ir }) {
  const ev = m.ultima_evaluacion;
  const totalEp = Object.values(m.episodios || {}).reduce((s, e) => s + e.n, 0);
  return (
    <Panel className={m.pendiente ? 'opacity-70' : ''}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xl font-semibold tracking-tight">{m.nombre}</div>
          <div className="text-xs text-muted">{m.metodologia}</div>
        </div>
        <InsigniaEstado estado={m.estado} />
      </div>
      <Nota className="mt-2">{m.descripcion}</Nota>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        {Object.entries(DIFICULTADES).map(([k, v]) => (
          <div key={k} className="bg-surface2 border border-line rounded-lg py-1.5">
            <div className="text-[11px] text-muted">{v}</div>
            <div className="text-sm font-semibold">récord E{m.records?.[k]?.nivel ?? 0}</div>
            <div className="text-[11px] text-muted">{m.records?.[k] ? `${m.records[k].manzanas} manzanas` : 'sin partidas'}</div>
          </div>
        ))}
      </div>
      <div className="mt-3 text-xs text-muted space-y-0.5">
        <div>Versión: {m.version || '—'} · Episodios registrados: {fmt(totalEp, 0)}</div>
        {ev && <div>Última evaluación ({DIFICULTADES[ev.dificultad]}, {ev.episodios} partidas): {fmt(ev.manzanas.media)} manzanas [IC95 {fmt(ev.manzanas.ic95[0])}–{fmt(ev.manzanas.ic95[1])}] · azar {fmt(ev.azar.media)} {ev.supera_azar ? <Insignia tono="ok">supera al azar</Insignia> : <Insignia>no supera al azar</Insignia>}</div>}
        {m.trabajo && <div className="text-accent">Trabajo en curso: {m.trabajo.tipo} {m.trabajo.hechos}/{m.trabajo.total}</div>}
      </div>
      {!m.pendiente && (
        <div className="mt-3 flex gap-2">
          <Boton variante="primario" onClick={() => ir('entrenamiento', m.clave)}>Entrenar</Boton>
          <Boton onClick={() => ir('simulador', m.clave)}>Observar</Boton>
        </div>
      )}
    </Panel>
  );
}
