/* Entrenamiento: un panel propio por modelo (su metodología) + sección común de
   evaluación, versiones y persistencia. */
import { useState } from 'react';
import { DIFICULTADES, api, archivoABase64, descargar, fmt } from '../lib/api';
import { useDatos, useTrabajo } from '../lib/hooks';
import { Aviso, Boton, Campo, InsigniaEstado, Nota, Numero, Panel, Plegable, Progreso, Segmentado, Selector } from '../components/ui';
import Grafica, { mediaMovil } from '../components/Grafica';
import PanelArkis from './entrenamiento/PanelArkis';
import PanelLerk from './entrenamiento/PanelLerk';
import PanelBork from './entrenamiento/PanelBork';
import PanelClark from './entrenamiento/PanelClark';

const MODELOS = { arkis: 'ARKIS', lerk: 'LERK', bork: 'BORK', clark: 'CLARK', mabu: 'MABU' };
const PANELES = { arkis: PanelArkis, lerk: PanelLerk, bork: PanelBork, clark: PanelClark };

export default function EntrenamientoView({ modelo, setModelo, tema, config }) {
  const [m, recargar] = useDatos(modelo === 'mabu' ? null : `/api/modelos/${modelo}`, [modelo]);
  const [trabajo, setTrabajo] = useTrabajo(() => recargar());
  const [error, setError] = useState(null);

  const lanzar = async (tipo, parametros) => {
    setError(null);
    try { setTrabajo(await api.post(`/api/modelos/${modelo}/trabajos`, { tipo, parametros })); } catch (e) { setError(e.message); }
  };
  const cancelar = () => trabajo && api.post(`/api/trabajos/${trabajo.id}/cancelar`);
  const PanelModelo = PANELES[modelo];
  const actual = trabajo?.modelo === modelo ? trabajo : m?.trabajo;

  return (
    <div className="space-y-4">
      <Segmentado opciones={MODELOS} valor={modelo} cambiar={setModelo} />
      {modelo === 'mabu' && (
        <Panel titulo="MABU · pendiente">
          <Nota>MABU es el modelo experimental principal. Según la especificación, su arquitectura se presentará para tu aprobación en la Etapa 5, y su preentrenamiento real y verificable se hará al final (decisión D4). Todavía no existe ningún artefacto de MABU, y la interfaz no simula uno.</Nota>
        </Panel>
      )}
      {m && PanelModelo && (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-xl font-semibold">{m.nombre}</div>
            <InsigniaEstado estado={m.estado} />
            <span className="text-sm text-muted">{m.metodologia} · versión {m.version || '—'}</span>
          </div>
          <Aviso error={error} />
          <Progreso trabajo={actual} cancelar={cancelar} />
          <PanelModelo m={m} recargar={recargar} lanzar={lanzar} ocupado={actual?.estado === 'en_curso'} tema={tema} config={config} />
          <Comun m={m} recargar={recargar} lanzar={lanzar} ocupado={actual?.estado === 'en_curso'} />
        </>
      )}
    </div>
  );
}

function Comun({ m, recargar, lanzar, ocupado }) {
  const [dif, setDif] = useState('medio');
  const [n, setN] = useState(30);
  const [conjunto, setConjunto] = useState('validacion');
  const [eps] = useDatos(`/api/modelos/${m.clave}/episodios?limite=1000`, [m.version, m.episodios]);
  const [msg, setMsg] = useState(null);

  const importar = async (e) => {
    const archivo = e.target.files[0];
    if (!archivo) return;
    try {
      const r = await api.post(`/api/modelos/${m.clave}/importar`, { zip_base64: await archivoABase64(archivo) });
      setMsg(`Importadas: ${r.importadas.join(', ')}.${r.bloqueado ? ' El artefacto ML importado está bloqueado hasta que confirmes que confías en su origen.' : ''}`);
      recargar();
    } catch (err) { setMsg(err.message); }
  };

  const evals = m.evaluaciones || [];
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel titulo="Evaluación con semillas fijas">
        <Nota>Juega partidas con semillas que nunca se usan para entrenar y compara con el azar en las mismas semillas. El estado pasa a «validado» solo si el IC 95 % supera al del azar.</Nota>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
          <Campo etiqueta="Partidas"><Numero valor={n} cambiar={setN} min={5} max={500} /></Campo>
          <Campo etiqueta="Semillas"><Selector valor={conjunto} cambiar={setConjunto} opciones={{ validacion: 'Validación', prueba: 'Prueba' }} /></Campo>
        </div>
        <Boton className="mt-3" variante="primario" disabled={ocupado} onClick={() => lanzar('evaluar', { dificultad: dif, episodios: n, conjunto })}>Evaluar</Boton>
        {evals.length > 0 && (
          <table className="tabla mt-3">
            <thead><tr><th>Versión</th><th>Dificultad</th><th className="num">Manzanas [IC95]</th><th className="num">Azar</th><th className="num">Mejor E</th><th>Supera azar</th></tr></thead>
            <tbody>{[...evals].reverse().slice(0, 8).map((e) => (
              <tr key={e.id}><td>{e.version}</td><td>{DIFICULTADES[e.dificultad]}</td>
                <td className="num">{fmt(e.manzanas.media)} [{fmt(e.manzanas.ic95[0])}–{fmt(e.manzanas.ic95[1])}]</td>
                <td className="num">{fmt(e.azar.media)}</td><td className="num">E{e.mejor_nivel}</td><td>{e.supera_azar ? '✓' : '✗'}</td></tr>
            ))}</tbody>
          </table>
        )}
      </Panel>

      <Panel titulo="Historial de episodios">
        {eps && eps.length > 1 ? (
          <Grafica series={[
            { nombre: 'manzanas', color: 'var(--muted)', opacidad: 0.4, grosor: 1, puntos: eps.map((e, i) => [i + 1, e.manzanas]) },
            { nombre: 'media móvil (20)', color: 'var(--accent)', grosor: 2, puntos: mediaMovil(eps.map((e) => e.manzanas)).map((v, i) => [i + 1, v]) },
          ]} />
        ) : <Nota>Aún no hay episodios registrados.</Nota>}
        <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
          {Object.entries(m.episodios || {}).map(([d, r]) => (
            <div key={d} className="bg-surface2 border border-line rounded-lg p-2">
              <div className="font-medium">{DIFICULTADES[d]}</div>
              <div>{r.n} episodios · media {fmt(r.media)}</div>
              <div>long. máx {r.lmax} · ocup. máx {fmt(r.omax, 1)} %</div>
              <div>victorias {r.victorias} · colisiones {r.colisiones}</div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel titulo="Versiones y persistencia">
        <Nota>Cada entrenamiento crea una versión nueva; ninguna se sobrescribe. Restaurar solo cambia cuál es la actual.</Nota>
        <div className="mt-3 max-h-64 overflow-auto">
          <table className="tabla">
            <thead><tr><th>Versión</th><th>Fecha</th><th>Motivo</th><th /></tr></thead>
            <tbody>{[...(m.versiones || [])].reverse().map((v) => (
              <tr key={v.version} className={v.version === m.version ? 'text-accent' : ''}>
                <td>{v.version}</td><td className="whitespace-nowrap">{v.fecha?.replace('T', ' ')}</td><td>{v.motivo}</td>
                <td>{v.version !== m.version && <Boton disabled={ocupado} onClick={async () => { await api.post(`/api/modelos/${m.clave}/restaurar`, { version: v.version }); recargar(); }}>Restaurar</Boton>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 items-center">
          <Boton onClick={() => descargar(`/api/modelos/${m.clave}/exportar`, `${m.clave}.zip`)}>Exportar (.zip)</Boton>
          <label className="px-3 py-1.5 rounded-lg border text-sm bg-surface2 border-line cursor-pointer hover:bg-line">Importar…<input type="file" accept=".zip" className="hidden" onChange={importar} /></label>
          <Boton onClick={async () => setMsg(`Copia creada: ${(await api.post(`/api/modelos/${m.clave}/copia`)).ruta}`)}>Copia de seguridad</Boton>
          {m.entrenamiento?.bloqueado && <Boton variante="peligro" onClick={async () => { await api.post(`/api/modelos/${m.clave}/confiar`); recargar(); }}>Confío en el origen del artefacto importado</Boton>}
        </div>
        {msg && <Nota className="mt-2">{msg}</Nota>}
      </Panel>

      <Panel titulo="Sesiones registradas">
        <div className="max-h-64 overflow-auto">
          <table className="tabla">
            <thead><tr><th>Fecha</th><th>Tipo</th><th>Versión</th></tr></thead>
            <tbody>{(m.sesiones || []).map((s) => (
              <tr key={s.id}><td className="whitespace-nowrap">{s.fecha.replace('T', ' ')}</td><td>{s.tipo}</td><td>{s.version_inicial || '—'} → {s.version_final || '—'}</td></tr>
            ))}</tbody>
          </table>
        </div>
        <Plegable titulo="Récord por dificultad">
          <pre className="codigo">{JSON.stringify(m.records, null, 1)}</pre>
        </Plegable>
      </Panel>
    </div>
  );
}
