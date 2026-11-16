/* BORK: hiperparámetros, recompensas, entrenamiento por episodios, curva y tabla Q. */
import { useEffect, useState } from 'react';
import { DIFICULTADES, api, fmt, pct } from '../../lib/api';
import { useDatos } from '../../lib/hooks';
import Grafica, { mediaMovil } from '../../components/Grafica';
import { Distribucion } from '../../components/Distribucion';
import { Aviso, Boton, Campo, Dato, Nota, Numero, Panel, Plegable, Selector } from '../../components/ui';

const PARAMS = {
  alfa: ['α (aprendizaje)', 0.01], gamma: ['γ (descuento)', 0.01],
  epsilon_inicial: ['ε inicial', 0.05], epsilon_final: ['ε final', 0.01], decaimiento: ['Decaimiento ε', 0.001],
};

export default function PanelBork({ m, recargar, lanzar, ocupado, visor }) {
  const e = m.entrenamiento;
  const [cfg, setCfg] = useState(e.config);
  const [error, setError] = useState(null);
  const [dif, setDif] = useState('medio');
  const [episodios, setEpisodios] = useState(300);
  const [semilla, setSemilla] = useState(0);
  const [velocidad, setVelocidad] = useState('');
  const [tabla, recargarTabla] = useDatos('/api/bork/tabla?limite=30', [m.version]);
  useEffect(() => setCfg(e.config), [e.config]);

  const guardar = async () => {
    setError(null);
    try { await api.post('/api/bork/config', cfg); recargar(); } catch (err) { setError(err.message); }
  };
  const curva = e.curva || [];

  const controles = (
    <>
      <Panel titulo="Entrenar por episodios">
        <div className="grid grid-cols-2 gap-2">
          <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
          <Campo etiqueta="Episodios"><Numero valor={episodios} cambiar={setEpisodios} min={1} max={100000} /></Campo>
          <Campo etiqueta="Semilla"><Numero valor={semilla} cambiar={setSemilla} min={0} /></Campo>
          <Campo etiqueta="Velocidad del juego (mov/s)" ayuda="Define cuántos pasos son 30 s de juego (regla de ciclos)"><Numero valor={velocidad} cambiar={setVelocidad} min={1} /></Campo>
        </div>
        <Boton className="mt-3" variante="primario" disabled={ocupado} onClick={() => lanzar('entrenar', { dificultad: dif, episodios, semilla, velocidad: velocidad || null, guardar_cada: 0 })}>Iniciar entrenamiento</Boton>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Dato etiqueta="Episodios totales" valor={fmt(e.episodios_totales, 0)} />
          <Dato etiqueta="ε actual" valor={fmt(e.epsilon_actual, 3)} />
          <Dato etiqueta="Estados visitados" valor={fmt(e.estados, 0)} />
          <Dato etiqueta="Cobertura de la tabla" valor={pct(e.estados / e.estados_posibles, 2)} />
        </div>
      </Panel>
      <Panel titulo="Configuración del Q-Learning">
        <div className="text-xs font-mono mb-2">Q(s,a) ← Q(s,a) + α [ r + γ · max Q(s′,a′) − Q(s,a) ]</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(PARAMS).map(([k, [et, paso]]) => <Campo key={k} etiqueta={et}><Numero valor={cfg[k]} paso={paso} cambiar={(v) => setCfg({ ...cfg, [k]: v })} /></Campo>)}
          <Campo etiqueta="Estado"><Selector valor={cfg.representacion} cambiar={(v) => setCfg({ ...cfg, representacion: v })} opciones={{ completa: 'Completo (36 864)', basica: 'Básico (144)' }} /></Campo>
        </div>
        <div className="mt-2"><Plegable titulo="Recompensas y penalizaciones">
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(cfg.recompensa).map(([k, v]) => (
              <Campo key={k} etiqueta={k.replaceAll('_', ' ')}><Numero valor={v} paso={0.01} cambiar={(x) => setCfg({ ...cfg, recompensa: { ...cfg.recompensa, [k]: x } })} /></Campo>
            ))}
          </div>
        </Plegable></div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Boton onClick={guardar}>Guardar configuración</Boton>
          <Boton variante="peligro" disabled={ocupado} onClick={async () => { await api.post('/api/bork/reiniciar'); recargar(); }} title="Empieza una tabla vacía; las versiones anteriores se conservan">Reiniciar tabla</Boton>
        </div>
        <Aviso error={error} />
      </Panel>
    </>
  );

  return (
    <Distribucion visor={visor} controles={controles}>
      <Panel titulo="Curva de aprendizaje (todas las sesiones)">
        {curva.length > 1 ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <Grafica series={[
              { nombre: 'manzanas', color: 'var(--muted)', opacidad: 0.35, grosor: 1, puntos: curva.map((p) => [p.episodio, p.manzanas]) },
              { nombre: 'media móvil (50)', color: 'var(--accent)', grosor: 2, puntos: mediaMovil(curva.map((p) => p.manzanas), 50).map((v, i) => [curva[i].episodio, v]) },
            ]} />
            <Grafica series={[
              { nombre: 'retorno (media 50)', color: 'var(--snake)', grosor: 2, puntos: mediaMovil(curva.map((p) => p.retorno), 50).map((v, i) => [curva[i].episodio, v]) },
              { nombre: 'ε × 10', color: 'var(--food)', grosor: 1.5, puntos: curva.map((p) => [p.episodio, p.epsilon * 10]) },
            ]} />
          </div>
        ) : <Nota>Entrena para ver la curva.</Nota>}
        <Nota className="mt-2">El retorno es propio de BORK y de su función de recompensa: no se compara con otros modelos (para eso está la pestaña Comparación, con métricas de juego).</Nota>
      </Panel>
      <Panel titulo="Tabla Q: estados más visitados" accion={<Boton onClick={recargarTabla}>Actualizar</Boton>}>
        <Nota>Formato del estado: peligro|encierro|cola por acción (↑↓←→) | signo de Δx y Δy de la manzana.</Nota>
        <div className="max-h-80 overflow-auto mt-2">
          <table className="tabla"><thead><tr><th>Estado</th><th className="num">Visitas ↑↓←→</th><th className="num">Q ↑</th><th className="num">Q ↓</th><th className="num">Q ←</th><th className="num">Q →</th></tr></thead>
            <tbody>{(tabla || []).map((f) => (
              <tr key={f.estado}><td className="font-mono">{f.estado}</td><td className="num">{f.visitas.join(' ')}</td>{f.q.map((q, i) => <td key={i} className={`num ${q === Math.max(...f.q) ? 'text-accent' : ''}`}>{fmt(q, 2)}</td>)}</tr>
            ))}</tbody></table>
        </div>
      </Panel>
    </Distribucion>
  );
}
