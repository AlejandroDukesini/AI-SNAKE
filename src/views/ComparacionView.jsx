/* Comparación de los modelos en condiciones equivalentes (mismas semillas de prueba). */
import { useState } from 'react';
import { DIFICULTADES, api, fmt } from '../lib/api';
import { useTrabajo } from '../lib/hooks';
import { Aviso, Boton, Campo, Insignia, Nota, Numero, Panel, Progreso, Selector } from '../components/ui';

export default function ComparacionView() {
  const [dif, setDif] = useState('medio');
  const [n, setN] = useState(30);
  const [error, setError] = useState(null);
  const [trabajo, setTrabajo] = useTrabajo();
  const r = trabajo?.resultado;

  const comparar = async () => {
    setError(null);
    try { setTrabajo(await api.post('/api/comparar', { dificultad: dif, episodios: n })); } catch (e) { setError(e.message); }
  };
  const mejor = r ? Math.max(...r.filas.map((f) => f.manzanas.media)) : 0;

  return (
    <div className="space-y-4">
      <Panel titulo="Comparar en condiciones equivalentes">
        <Nota>Todos los modelos (en su versión actual) y las dos líneas base sin aprendizaje juegan las MISMAS partidas: mismas semillas de prueba, mismo motor, misma dificultad. Solo se comparan métricas de juego; las recompensas de algoritmos distintos no son equivalentes y no se comparan.</Nota>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
          <Campo etiqueta="Partidas por modelo"><Numero valor={n} cambiar={setN} min={5} max={500} /></Campo>
          <Boton variante="primario" onClick={comparar} disabled={trabajo?.estado === 'en_curso'}>Comparar</Boton>
        </div>
        <div className="mt-3"><Aviso error={error} /><Progreso trabajo={trabajo} cancelar={() => api.post(`/api/trabajos/${trabajo.id}/cancelar`)} /></div>
      </Panel>
      {r && (
        <Panel titulo={`${DIFICULTADES[r.dificultad]} · ${r.episodios} partidas · semillas ${r.semillas[0]}–${r.semillas[1]}`}>
          <div className="overflow-x-auto">
            <table className="tabla">
              <thead><tr><th>Modelo</th><th>Versión</th><th className="num">Manzanas media</th><th className="num">IC 95 %</th><th className="num">Mediana</th><th className="num">Ocupación máx. media</th><th className="num">Pasos medios</th><th className="num">Mejor E</th><th className="num">Victorias</th><th>Causas de fin</th></tr></thead>
              <tbody>{r.filas.map((f) => (
                <tr key={f.clave} className={f.clave.startsWith('base_') ? 'text-muted' : ''}>
                  <td>{f.nombre} {f.manzanas.media === mejor && <Insignia tono="ok">mejor</Insignia>}</td>
                  <td>{f.version || (f.clave.startsWith('base_') ? 'sin aprendizaje' : 'sin entrenar')}</td>
                  <td className="num">{fmt(f.manzanas.media)}</td>
                  <td className="num">{fmt(f.manzanas.ic95[0])}–{fmt(f.manzanas.ic95[1])}</td>
                  <td className="num">{fmt(f.manzanas.mediana, 1)}</td>
                  <td className="num">{fmt(f.ocupacion_max.media, 1)} %</td>
                  <td className="num">{fmt(f.pasos.media, 0)}</td>
                  <td className="num">E{f.mejor_nivel}</td>
                  <td className="num">{f.victorias}</td>
                  <td className="text-xs">{Object.entries(f.causas_fin).map(([k, v]) => `${k}: ${v}`).join(' · ')}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <Nota className="mt-2">Dos intervalos que no se solapan indican una diferencia clara; si se solapan, la diferencia puede deberse al azar de las partidas.</Nota>
        </Panel>
      )}
    </div>
  );
}
