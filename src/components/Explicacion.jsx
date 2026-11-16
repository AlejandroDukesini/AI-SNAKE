/* Explicación de una decisión, con la forma propia de cada metodología. */
import { FLECHA, fmt } from '../lib/api';

export default function Explicacion({ decision }) {
  if (!decision) return <div className="text-xs text-muted">Sin decisión (partida terminada o modo manual).</div>;
  const e = decision.explicacion || {};
  return (
    <div className="space-y-2 text-sm">
      <div>Decide: <b>{FLECHA[decision.accion]} {decision.accion}</b></div>
      <div className="text-xs text-muted">{e.texto}</div>
      {e.tipo === 'probabilidades' && <Barras valores={decision.puntuaciones} titulo="P(acción) del Random Forest" />}
      {e.tipo === 'valores_q' && (
        <>
          <div className="text-xs">Estado: <code>{e.estado}</code> · {e.estado_conocido ? 'visitado' : 'nunca visto'} · {e.modo}</div>
          <table className="tabla"><thead><tr><th>Acción</th><th className="num">Q(s,a)</th><th className="num">Visitas</th></tr></thead>
            <tbody>{Object.entries(decision.puntuaciones).map(([a, q], i) => (
              <tr key={a} className={a === decision.accion ? 'text-accent' : ''}><td>{FLECHA[a]} {a}</td><td className="num">{fmt(q, 3)}</td><td className="num">{e.visitas?.[i]}</td></tr>
            ))}</tbody></table>
        </>
      )}
      {e.tipo === 'cadena_inferencia' && <CadenaLerk e={e} />}
      {e.tipo === 'hibrido' && <Hibrido e={e} decision={decision} />}
    </div>
  );
}

function Barras({ valores, titulo }) {
  return (
    <div className="space-y-1">
      <div className="text-xs text-muted">{titulo}</div>
      {Object.entries(valores).map(([a, v]) => (
        <div key={a} className="flex items-center gap-2 text-xs">
          <span className="w-20">{FLECHA[a]} {a}</span>
          <div className="flex-1 h-2 bg-line rounded"><div className="h-2 bg-accent rounded" style={{ width: `${Math.max(0, Math.min(1, v)) * 100}%` }} /></div>
          <span className="w-12 text-right tabular-nums">{fmt(v, 3)}</span>
        </div>
      ))}
    </div>
  );
}

function CadenaLerk({ e }) {
  return (
    <div className="space-y-2 text-xs">
      <div><b>1 · Hechos</b>
        <ul className="ml-3">{Object.entries(e.hechos).map(([a, h]) => <li key={a}>{FLECHA[a]} {a}: {h.join(', ') || '—'}</li>)}</ul>
      </div>
      <div><b>2 · Reglas disparadas</b>
        {e.disparos.length ? <ul className="ml-3">{e.disparos.map((d, i) => (
          <li key={i}>[{d.accion}] {d.texto} → <i>{d.conclusion}</i>{d.excepcion && <> (excepción: {d.excepcion})</>}</li>))}</ul>
          : <div className="ml-3 text-muted">ninguna</div>}
      </div>
      {e.prohibidas.length > 0 && <div><b>3 · Prohibidas:</b> {e.prohibidas.join(', ')}</div>}
      {e.conflictos.length > 0 && <div><b>Conflictos:</b><ul className="ml-3">{e.conflictos.map((c, i) => <li key={i}>{c}</li>)}</ul></div>}
    </div>
  );
}

function Hibrido({ e, decision }) {
  const acciones = Object.keys(decision.puntuaciones);
  return (
    <div className="space-y-2 text-xs">
      <table className="tabla">
        <thead><tr><th>Acción</th><th className="num">A · ML ×{e.pesos.ml}</th><th className="num">B · Simb. ×{e.pesos.simbolico}</th><th className="num">C · RL ×{e.pesos.refuerzo}</th><th className="num">Total</th></tr></thead>
        <tbody>{acciones.map((a) => (
          <tr key={a} className={a === decision.accion ? 'text-accent' : e.vetos.includes(a) ? 'text-danger' : ''}>
            <td>{FLECHA[a]} {a}{e.vetos.includes(a) ? ' (vetada)' : ''}</td>
            <td className="num">{fmt(e.componentes.ml[a], 3)}</td><td className="num">{fmt(e.componentes.simbolico[a], 3)}</td>
            <td className="num">{fmt(e.componentes.refuerzo[a], 3)}</td><td className="num">{fmt(decision.puntuaciones[a], 3)}</td>
          </tr>))}</tbody>
      </table>
      <div>Acuerdo con la decisión: {Object.entries(e.acuerdo).map(([k, v]) => `${k} ${v ? '✓' : '✗'}`).join(' · ')}</div>
      {e.restriccion_usuario?.length > 0 && <div>Restringido por tu conocimiento a: {e.restriccion_usuario.join(', ')}</div>}
      {e.conflictos.length > 0 && <div><b>Conflictos:</b> {e.conflictos.join('; ')}</div>}
      {!e.ml_entrenado && <div className="text-muted">El componente ML aún no está entrenado (aporta 0,5 a todas).</div>}
    </div>
  );
}
