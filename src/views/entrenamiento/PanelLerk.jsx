/* LERK: base de conocimiento editable, inducción, generalización, validación y conflictos. */
import { useState } from 'react';
import { DIFICULTADES, api, fmt, pct } from '../../lib/api';
import { useDatos } from '../../lib/hooks';
import { Aviso, Boton, Campo, Dato, Insignia, Nota, Numero, Panel, Selector, Vacio } from '../../components/ui';

const ORIGEN = { usuario: 'tuya', induccion: 'inducida', correccion: 'corrección', experiencia: 'experiencia', generalizacion: 'generalizada' };

export default function PanelLerk({ m, recargar, lanzar, ocupado, config }) {
  const e = m.entrenamiento;
  const [informe, setInforme] = useState(null);
  const [error, setError] = useState(null);
  const [conflictos, recargarConf] = useDatos('/api/lerk/conflictos', [m.version]);
  const [dif, setDif] = useState('medio');
  const [episodios, setEpisodios] = useState(50);
  const [epsilon, setEpsilon] = useState(0.2);
  const [tol, setTol] = useState(0);

  const hacer = async (fn, titulo) => {
    setError(null);
    try { const r = await fn(); setInforme({ titulo, r }); recargar(); recargarConf(); } catch (err) { setError(err.message); }
  };
  const raices = e.reglas.filter((r) => !r.padre);
  const hijos = (id) => e.reglas.filter((r) => r.padre === id);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Panel titulo={`Conocimiento adquirido (${e.reglas.length} reglas)`}>
          <div className="flex flex-wrap gap-1 mb-2">{Object.entries(e.por_origen).map(([k, v]) => <Insignia key={k}>{ORIGEN[k] || k}: {v}</Insignia>)}</div>
          {raices.length === 0 && <Vacio>LERK empieza vacío. Crea reglas, aporta casos (Simulador → Demostrar con LERK) o déjalo aprender de la experiencia.</Vacio>}
          <div className="space-y-2 max-h-[32rem] overflow-auto">
            {raices.map((r) => <Regla key={r.id} r={r} hijos={hijos} hacer={hacer} />)}
          </div>
        </Panel>
        <div className="space-y-4">
          <NuevaRegla config={config} reglas={e.reglas} hacer={hacer} />
          <Panel titulo="Aprendizaje simbólico">
            <div className="grid grid-cols-3 gap-2">
              <Dato etiqueta="Casos tuyos" valor={e.casos.aprobados} />
              <Dato etiqueta="Experiencia" valor={fmt(e.experiencia, 0)} ayuda="Pasos con resultado objetivo del simulador" />
              <Dato etiqueta="Conflictos" valor={conflictos?.length ?? '—'} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Boton disabled={!e.casos.aprobados} onClick={() => hacer(() => api.post('/api/lerk/inducir'), 'Inducción desde tus casos')}>Inducir reglas de mis casos</Boton>
              <Boton disabled={!e.casos.aprobados} onClick={() => hacer(() => api.post('/api/lerk/validar'), 'Validación')}>Validar</Boton>
            </div>
            <div className="mt-2 flex items-end gap-2">
              <Campo etiqueta="Tolerancia de generalización" ayuda="Pérdida de precisión admitida al quitar condiciones"><Numero valor={tol} cambiar={setTol} min={0} max={0.2} paso={0.01} /></Campo>
              <Boton disabled={!e.casos.aprobados} onClick={() => hacer(() => api.post(`/api/lerk/generalizar?tolerancia=${tol}`), 'Generalización')}>Generalizar</Boton>
            </div>
            <div className="mt-4 border-t border-line pt-3 space-y-2">
              <div className="text-sm font-medium">Modo automático: aprender de la experiencia</div>
              <Nota>LERK juega; el simulador aporta los hechos objetivos (morir en ≤ 4 pasos, comer, acercarse y sobrevivir) y de ellos se inducen prohibiciones y preferencias. Tus reglas y correcciones no se tocan.</Nota>
              <div className="grid grid-cols-3 gap-2">
                <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
                <Campo etiqueta="Episodios"><Numero valor={episodios} cambiar={setEpisodios} min={10} /></Campo>
                <Campo etiqueta="ε (exploración)"><Numero valor={epsilon} cambiar={setEpsilon} min={0} max={1} paso={0.05} /></Campo>
              </div>
              <Boton variante="primario" disabled={ocupado} onClick={() => lanzar('automatico', { dificultad: dif, episodios, epsilon, bloque: 10 })}>Aprender jugando</Boton>
            </div>
            <Aviso error={error} />
          </Panel>
        </div>
      </div>
      {informe && <Informe informe={informe} />}
      {conflictos?.length > 0 && (
        <Panel titulo="Conflictos detectados en tus casos">
          <table className="tabla"><thead><tr><th>Tipo</th><th>Reglas</th><th className="num">Casos</th></tr></thead>
            <tbody>{conflictos.map((c, i) => <tr key={i}><td>{c.tipo.replaceAll('_', ' ')}</td><td>{c.reglas.join(' ⟷ ')}</td><td className="num">{c.casos}</td></tr>)}</tbody></table>
        </Panel>
      )}
      <Nota>Para corregir una inferencia: Simulador → Observar a LERK → «¿No estás de acuerdo?». La corrección crea una excepción (Ripple-Down Rules) a la regla responsable.</Nota>
    </div>
  );
}

function Regla({ r, hijos, hacer, nivel = 0 }) {
  const [prio, setPrio] = useState(r.prioridad);
  return (
    <div className={`border border-line rounded-lg p-2 text-sm ${!r.activa ? 'opacity-50' : ''}`} style={{ marginLeft: nivel * 16 }}>
      <div className="flex flex-wrap items-center gap-1">
        <Insignia tono={r.conclusion === 'prohibir' ? 'peligro' : r.conclusion === 'anular' ? 'normal' : 'ok'}>{r.conclusion}</Insignia>
        <Insignia>{ORIGEN[r.origen] || r.origen}</Insignia>
        <span className="text-xs text-muted">conf. {pct(r.confianza, 0)} · soporte {r.soporte} · prioridad {r.prioridad}</span>
      </div>
      <div className="mt-1 font-mono text-xs">{r.texto}</div>
      {r.nota && <div className="text-xs text-muted">{r.nota}</div>}
      <div className="mt-1 flex flex-wrap gap-1 items-center">
        <input type="number" value={prio} onChange={(e) => setPrio(Number(e.target.value))} className="w-14 bg-surface2 border border-line rounded px-1 text-xs" />
        <Boton className="!py-0.5 text-xs" onClick={() => hacer(() => api.patch(`/api/lerk/reglas/${r.id}`, { prioridad: prio }), 'Prioridad cambiada')}>Fijar prioridad</Boton>
        <Boton className="!py-0.5 text-xs" onClick={() => hacer(() => api.patch(`/api/lerk/reglas/${r.id}`, { activa: !r.activa }), r.activa ? 'Regla desactivada' : 'Regla activada')}>{r.activa ? 'Desactivar' : 'Activar'}</Boton>
        <Boton className="!py-0.5 text-xs" onClick={() => hacer(() => api.del(`/api/lerk/reglas/${r.id}`), 'Regla eliminada')}>Eliminar</Boton>
      </div>
      {hijos(r.id).map((h) => <div key={h.id} className="mt-2"><Regla r={h} hijos={hijos} hacer={hacer} nivel={1} /></div>)}
    </div>
  );
}

function NuevaRegla({ config, reglas, hacer }) {
  const [lits, setLits] = useState({});
  const [conclusion, setConclusion] = useState('preferir');
  const [accion, setAccion] = useState('');
  const [prioridad, setPrioridad] = useState(0);
  const [padre, setPadre] = useState('');
  const ciclo = (p) => setLits({ ...lits, [p]: lits[p] === '+' ? '-' : lits[p] === '-' ? undefined : '+' });
  const condiciones = Object.entries(lits).filter(([, v]) => v).map(([p, v]) => (v === '+' ? p : `!${p}`));
  const crear = () => hacer(() => api.post('/api/lerk/reglas', { condiciones, conclusion, accion: accion || null, prioridad, padre: padre || null }), 'Regla creada');
  return (
    <Panel titulo="Crear regla">
      <Nota>Pulsa un predicado: verde = debe cumplirse, rojo = NO debe cumplirse. X es la acción candidata.</Nota>
      <div className="mt-2 flex flex-wrap gap-1">
        {Object.entries(config.predicados).map(([p, desc]) => (
          <button key={p} title={desc} onClick={() => ciclo(p)}
            className={`px-2 py-0.5 rounded border text-xs ${lits[p] === '+' ? 'border-snake text-snake bg-snake/10' : lits[p] === '-' ? 'border-danger text-danger bg-danger/10' : 'border-line text-muted'}`}>
            {lits[p] === '-' ? 'NO ' : ''}{p}(X)
          </button>
        ))}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <Campo etiqueta="Conclusión"><Selector valor={conclusion} cambiar={setConclusion} opciones={{ preferir: 'preferir X', prohibir: 'prohibir X', ...(padre ? { anular: 'anular (excepción)' } : {}) }} /></Campo>
        <Campo etiqueta="Solo para la acción"><Selector valor={accion} cambiar={setAccion} opciones={{ '': 'cualquiera (X)', arriba: 'arriba', abajo: 'abajo', izquierda: 'izquierda', derecha: 'derecha' }} /></Campo>
        <Campo etiqueta="Prioridad"><Numero valor={prioridad} cambiar={setPrioridad} /></Campo>
        <Campo etiqueta="Excepción de"><Selector valor={padre} cambiar={setPadre} opciones={{ '': '— (regla raíz)', ...Object.fromEntries(reglas.filter((r) => r.activa).map((r) => [r.id, r.texto.slice(0, 60)])) }} /></Campo>
      </div>
      <div className="mt-2 font-mono text-xs">SI {condiciones.map((c) => (c.startsWith('!') ? `NO ${c.slice(1)}(X)` : `${c}(X)`)).join(' Y ') || 'SIEMPRE'}{accion ? ` Y X = ${accion}` : ''} ENTONCES {conclusion} X</div>
      <Boton className="mt-2" variante="primario" onClick={crear}>Crear</Boton>
    </Panel>
  );
}

function Informe({ informe }) {
  const r = informe.r;
  return (
    <Panel titulo={informe.titulo}>
      {r.exactitud !== undefined && <div className="text-sm">Casos: {r.casos} · exactitud de LERK: {pct(r.exactitud)} · cobertura (alguna regla aplica): {pct(r.cobertura)}</div>}
      {r.reglas && <div className="text-sm">Reglas inducidas: {r.reglas.length}<ul className="ml-4 list-disc text-xs font-mono">{r.reglas.map((x) => <li key={x.id}>{x.texto} (conf. {pct(x.confianza, 0)})</li>)}</ul></div>}
      {r.cambios && <div className="text-sm">{r.cambios.length ? <ul className="ml-4 list-disc text-xs">{r.cambios.map((c) => <li key={c.regla}>{c.antes.join(' ∧ ')} → {c.despues.join(' ∧ ')} (precisión {fmt(c.precision, 3)}, cobertura {c.cobertura})</li>)}</ul> : 'Ninguna regla se pudo generalizar sin perder precisión.'}</div>}
      {r.texto && <div className="text-sm font-mono">{r.texto}</div>}
      {r.eliminadas && <div className="text-sm">Eliminadas: {r.eliminadas.join(', ')}</div>}
    </Panel>
  );
}
