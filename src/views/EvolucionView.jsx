/* Evolución E0–E8 por modelo y dificultad (récord histórico, nunca disminuye). */
import { DIFICULTADES } from '../lib/api';
import { useDatos } from '../lib/hooks';
import EscalaE from '../components/Evolucion';
import { Nota, Panel } from '../components/ui';

export default function EvolucionView({ config }) {
  const [modelos] = useDatos('/api/modelos');
  return (
    <div className="space-y-4">
      <Panel titulo="Cómo se mide">
        <Nota>Ocupación = longitud / casillas × 100. El nivel E_n se alcanza al ocupar C(E_n) = techo(n·N/8) casillas, y exige haber comido al menos una manzana (la longitud inicial no regala niveles). E0 = no alcanzar E1. El récord histórico es el mejor nivel de cualquier episodio, separado por modelo y dificultad, y nunca disminuye.</Nota>
        <table className="tabla mt-3">
          <thead><tr><th>Dificultad</th><th>Long. inicial</th>{[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <th key={n} className="num">E{n}</th>)}</tr></thead>
          <tbody>{Object.entries(config.dificultades).map(([k, d]) => (
            <tr key={k}><td>{DIFICULTADES[k]} ({d.casillas})</td><td>{d.longitud_inicial}</td>{d.umbrales.slice(1).map((u, i) => <td key={i} className="num">{u}</td>)}</tr>
          ))}</tbody>
        </table>
      </Panel>
      {modelos?.filter((m) => !m.pendiente).map((m) => (
        <Panel key={m.clave} titulo={`${m.nombre} · ${m.metodologia}`}>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(config.dificultades).map(([k, d]) => (
              <div key={k}>
                <div className="text-sm mb-1">{DIFICULTADES[k]} · récord <b>E{m.records?.[k]?.nivel ?? 0}</b>{m.records?.[k] ? ` (${m.records[k].manzanas} manzanas, ${m.records[k].version || 'sin versión'})` : ''}</div>
                <EscalaE umbrales={d.umbrales} nivel={-1} record={m.records?.[k]?.nivel ?? 0} />
              </div>
            ))}
          </div>
        </Panel>
      ))}
      <Nota>El nivel de una partida en curso se ve en el Simulador, junto al récord, para distinguirlos.</Nota>
    </div>
  );
}
