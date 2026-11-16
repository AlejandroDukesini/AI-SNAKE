/* CLARK: integración de tres componentes propios. */
import { useEffect, useState } from 'react';
import { DIFICULTADES, api, fmt, pct } from '../../lib/api';
import { Distribucion } from '../../components/Distribucion';
import { Aviso, Boton, Campo, Dato, Insignia, Nota, Numero, Panel, Plegable, Selector } from '../../components/ui';

export default function PanelClark({ m, recargar, lanzar, ocupado, visor }) {
  const e = m.entrenamiento;
  const [cfg, setCfg] = useState(e.config);
  const [error, setError] = useState(null);
  const [dif, setDif] = useState('medio');
  const [episodios, setEpisodios] = useState(150);
  const [semilla, setSemilla] = useState(0);
  useEffect(() => setCfg(e.config), [e.config]);
  const ultima = (m.sesiones || []).find((s) => s.tipo === 'entrenamiento_automatico');
  const res = ultima ? JSON.parse(ultima.resumen) : null;

  const guardar = async () => {
    setError(null);
    try { await api.post('/api/clark/config', cfg); recargar(); } catch (err) { setError(err.message); }
  };

  const controles = (
    <>
      <Panel titulo="Entrenamiento automático">
        <Nota>Cada componente aprende con su propio mecanismo: la tabla Q en cada paso, y el Random Forest y las reglas al final de cada bloque de episodios.</Nota>
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
          <Campo etiqueta="Episodios"><Numero valor={episodios} cambiar={setEpisodios} min={10} /></Campo>
          <Campo etiqueta="Semilla"><Numero valor={semilla} cambiar={setSemilla} min={0} /></Campo>
        </div>
        <Boton className="mt-3" variante="primario" disabled={ocupado} onClick={() => lanzar('automatico', { dificultad: dif, episodios, semilla, bloque: 25 })}>Iniciar entrenamiento</Boton>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Dato etiqueta="Episodios" valor={fmt(e.episodios_totales, 0)} />
          <Dato etiqueta="ε actual" valor={fmt(e.epsilon_actual, 3)} />
          <Dato etiqueta="Experiencia" valor={fmt(e.experiencia, 0)} />
        </div>
        {res && (
          <div className="mt-3 text-xs space-y-1">
            <div className="font-medium">Última sesión ({res.episodios} episodios)</div>
            <div>Acuerdo de cada componente con la decisión final: {Object.entries(res.acuerdo_con_final).map(([k, v]) => `${k} ${pct(v, 0)}`).join(' · ')}</div>
            <div>Decisiones con algún veto simbólico: {pct(res.decisiones_con_veto, 0)}</div>
          </div>
        )}
      </Panel>
      <Panel titulo="Pesos y parámetros">
        <div className="grid grid-cols-3 gap-2">
          <Campo etiqueta="w_A (ML)"><Numero valor={cfg.peso_ml} paso={0.05} min={0} cambiar={(v) => setCfg({ ...cfg, peso_ml: v })} /></Campo>
          <Campo etiqueta="w_B (simb.)"><Numero valor={cfg.peso_simbolico} paso={0.05} min={0} cambiar={(v) => setCfg({ ...cfg, peso_simbolico: v })} /></Campo>
          <Campo etiqueta="w_C (RL)"><Numero valor={cfg.peso_refuerzo} paso={0.05} min={0} cambiar={(v) => setCfg({ ...cfg, peso_refuerzo: v })} /></Campo>
          <Campo etiqueta="τ softmax"><Numero valor={cfg.temperatura} paso={0.1} min={0.1} cambiar={(v) => setCfg({ ...cfg, temperatura: v })} /></Campo>
          <Campo etiqueta="α"><Numero valor={cfg.alfa} paso={0.01} cambiar={(v) => setCfg({ ...cfg, alfa: v })} /></Campo>
          <Campo etiqueta="γ"><Numero valor={cfg.gamma} paso={0.01} cambiar={(v) => setCfg({ ...cfg, gamma: v })} /></Campo>
          <Campo etiqueta="ε inicial"><Numero valor={cfg.epsilon_inicial} paso={0.05} cambiar={(v) => setCfg({ ...cfg, epsilon_inicial: v })} /></Campo>
          <Campo etiqueta="ε final"><Numero valor={cfg.epsilon_final} paso={0.01} cambiar={(v) => setCfg({ ...cfg, epsilon_final: v })} /></Campo>
          <Campo etiqueta="Decaimiento ε"><Numero valor={cfg.decaimiento} paso={0.001} cambiar={(v) => setCfg({ ...cfg, decaimiento: v })} /></Campo>
        </div>
        <Boton className="mt-3" onClick={guardar}>Guardar</Boton>
        <Aviso error={error} />
      </Panel>
    </>
  );

  return (
    <Distribucion visor={visor} controles={controles}>
      <Panel titulo="Arquitectura de integración">
        <div className="grid gap-3 md:grid-cols-3 text-sm">
          <Componente t="A · Machine Learning" d="Random Forest propio que estima la probabilidad de que cada acción sea buena (no morir en ≤ 4 pasos y comer o acercarse)." ok={e.ml_entrenado} v={e.ml_entrenado ? 'entrenado' : 'sin entrenar'} />
          <Componente t="B · Simbólico" d="Reglas propias: vetos (prohibiciones) y preferencias, inducidas de su experiencia y de tus correcciones." ok={e.reglas.length > 0} v={`${e.reglas.length} reglas`} />
          <Componente t="C · Refuerzo" d="Tabla Q propia, actualizada paso a paso con la recompensa común." ok={e.estados_q > 0} v={`${fmt(e.estados_q, 0)} estados`} />
        </div>
        <ol className="mt-3 text-xs text-muted list-decimal ml-4 space-y-0.5">
          <li>B veta acciones; si las veta todas, se ignoran los vetos (conflicto registrado).</li>
          <li>Si una regla tuya o una corrección tuya prefiere acciones permitidas, la elección se limita a ellas.</li>
          <li>Puntuación = w_A·P_ML + w_B·preferencia + w_C·softmax(Q/τ); gana la mayor.</li>
        </ol>
        <Nota className="mt-2">En el visor verás, en cada paso, la opinión de los tres componentes, cuál habría elegido cada uno por separado y si esa acción habría chocado. Así se distingue el rendimiento de cada componente con datos reales. CLARK no comparte reglas, tabla Q ni datos con LERK o BORK.</Nota>
      </Panel>
      <Plegable titulo={`Reglas del componente simbólico (${e.reglas.length})`}>
        <ul className="text-xs font-mono space-y-1">{e.reglas.map((r) => <li key={r.id}><Insignia>{r.origen}</Insignia> {r.texto} · conf. {pct(r.confianza, 0)}</li>)}</ul>
      </Plegable>
    </Distribucion>
  );
}

function Componente({ t, d, ok, v }) {
  return (
    <div className="bg-surface2 border border-line rounded-xl p-3">
      <div className="flex items-center justify-between gap-2"><b>{t}</b><Insignia tono={ok ? 'ok' : 'normal'}>{v}</Insignia></div>
      <div className="text-xs text-muted mt-1">{d}</div>
    </div>
  );
}
