/* Los tres sentidos tal como los recibe cada modelo. */
import { FLECHA, fmt } from '../lib/api';

export function SentidoCuerpo({ cuerpo }) {
  const m = cuerpo.matriz;
  const lado = m.length;
  const pequeno = lado > 8;
  return (
    <div className="space-y-2">
      <div className="text-xs font-medium">Sentido 1 · Cuerpo</div>
      <div className="inline-grid gap-px bg-line p-px rounded font-mono" style={{ gridTemplateColumns: `repeat(${m[0].length}, minmax(0,1fr))` }}>
        {m.flatMap((fila, y) => fila.map((v, x) => {
          const cabeza = cuerpo.cabeza[0] === x && cuerpo.cabeza[1] === y;
          return (
            <span key={`${x}-${y}`} className={`${pequeno ? 'w-3 h-3 text-[0px]' : 'w-5 h-5 text-[10px]'} flex items-center justify-center
              ${v ? (cabeza ? 'bg-head text-bg' : 'bg-snake/70 text-bg') : 'bg-surface2 text-muted'}`}>{v}</span>
          );
        }))}
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <dt className="text-muted">Cabeza</dt><dd>({cuerpo.cabeza.join(', ')})</dd>
        <dt className="text-muted">Cola</dt><dd>({cuerpo.cola.join(', ')})</dd>
        <dt className="text-muted">Longitud</dt><dd>{cuerpo.longitud}</dd>
        <dt className="text-muted">Dirección</dt><dd>{FLECHA[cuerpo.direccion]} {cuerpo.direccion}</dd>
        <dt className="text-muted">Casillas libres</dt><dd>{cuerpo.casillas_libres}</dd>
      </dl>
      <table className="tabla">
        <thead><tr><th>Acción</th><th>Colisión</th><th className="num">Espacio</th><th>Cola</th></tr></thead>
        <tbody>
          {Object.keys(cuerpo.colision_por_accion).map((a) => (
            <tr key={a} className={cuerpo.acciones_disponibles.includes(a) ? '' : 'opacity-40'}>
              <td>{FLECHA[a]} {a}</td>
              <td className={cuerpo.colision_por_accion[a] ? 'text-danger' : 'text-snake'}>{cuerpo.colision_por_accion[a] || 'libre'}</td>
              <td className="num">{cuerpo.espacio_por_accion?.[a] ?? '—'}</td>
              <td>{cuerpo.cola_alcanzable_por_accion?.[a] ? 'alcanzable' : 'no'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-xs text-muted">Segmentos (cabeza→cola): {cuerpo.segmentos.map((s) => `(${s.join(',')})`).join(' ')}</div>
    </div>
  );
}

export function SentidoManzana({ manzana }) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium">Sentido 2 · Manzana</div>
      {!manzana ? <div className="text-xs text-muted">Sin manzana (tablero completo).</div> : (
        <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
          <dt className="text-muted">Coordenadas</dt><dd>({manzana.x}, {manzana.y})</dd>
          <dt className="text-muted">Δx · Δy</dt><dd>{manzana.dx} · {manzana.dy}</dd>
          <dt className="text-muted">Dirección relativa</dt><dd>{manzana.direccion_relativa.join(' / ')}</dd>
          <dt className="text-muted">Manhattan</dt><dd>|Δx| + |Δy| = {manzana.manhattan}</dd>
        </dl>
      )}
    </div>
  );
}

export function SentidoMuros({ muros }) {
  return (
    <div className="space-y-1">
      <div className="text-xs font-medium">Sentido 3 · Muros</div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        {['arriba', 'abajo', 'izquierda', 'derecha'].map((k) => (
          <FragmentoMuro key={k} k={k} d={muros[k]} choque={muros.colision_limite_por_accion[k]} />
        ))}
        <dt className="text-muted">Espacio libre</dt><dd>{fmt(muros.espacio_libre)} casillas</dd>
      </dl>
    </div>
  );
}

function FragmentoMuro({ k, d, choque }) {
  return (<><dt className="text-muted">Límite {k}</dt><dd className={choque ? 'text-danger' : ''}>{d} {choque ? '· choque inmediato' : ''}</dd></>);
}
