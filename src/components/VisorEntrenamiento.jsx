/* Visor del entrenamiento REAL. Todo lo que muestra viene de /api/trabajos/{id}/vista:
   el último paso que el modelo ejecutó de verdad (decisión, resultado del motor) y el
   historial de episodios. No hay animaciones ni datos inventados.

   Dos velocidades independientes:
   - Ritmo del entrenamiento (pasos/s, en el servidor): solo añade esperas entre pasos; el
     resultado del entrenamiento es idéntico (probado en tests/test_observacion.py).
   - Refresco de la pantalla: cada cuánto se pide el último paso; no afecta al servidor. */
import { useEffect, useRef, useState } from 'react';
import { FLECHA, api, fmt, pct } from '../lib/api';
import Tablero from './Tablero';
import EscalaE from './Evolucion';
import Explicacion from './Explicacion';
import Grafica, { mediaMovil } from './Grafica';
import { Aviso, Boton, Insignia, Nota, Segmentado } from './ui';

export const RITMOS = { 0: 'Máximo', 200: '200/s', 50: '50/s', 15: '15/s', 4: '4/s' };
const REFRESCOS = { 100: 'Fluido', 300: 'Normal', 1000: 'Ahorro' };
const CON_RECOMPENSA = ['bork', 'clark', 'mabu'];
const MOV = {
  acerca: ['se acerca a la manzana', 'ok'], aleja: ['se aleja de la manzana', 'aviso'],
  igual: ['misma distancia', 'normal'], come: ['¡come la manzana!', 'acento'], colision: ['colisión', 'peligro'],
};
const FASES = { preparando: 'Preparando', entrenando: 'Ajustando el modelo', evaluando: 'Evaluando (jugando con semillas fijas)',
  jugando: 'Jugando', aprendiendo: 'Aprendiendo de lo jugado', terminado: 'Terminado', cancelado: 'Detenido', error: 'Error' };

export default function VisorEntrenamiento({ trabajoId, modelo, tema, alTerminar }) {
  const [v, setV] = useState(null);
  const [error, setError] = useState(null);
  const [refresco, setRefresco] = useState('300');
  const terminadoRef = useRef(false);

  useEffect(() => {
    terminadoRef.current = false;
    let vivo = true;
    let enCurso = false;
    const pedir = async () => {
      if (enCurso) return;                     // nunca dos peticiones a la vez
      enCurso = true;
      try {
        const r = await api.getSinReintentos(`/api/trabajos/${trabajoId}/vista`);
        if (!vivo) return;
        setV(r); setError(null);
        if (r.trabajo.estado !== 'en_curso' && !terminadoRef.current) { terminadoRef.current = true; alTerminar?.(r.trabajo); }
      } catch (e) { if (vivo) setError(e.message); } finally { enCurso = false; }
    };
    pedir();
    const id = setInterval(() => { if (!terminadoRef.current) pedir(); }, Number(refresco));
    return () => { vivo = false; clearInterval(id); };
  }, [trabajoId, refresco, alTerminar]);

  const control = async (cuerpo) => {
    try { await api.post(`/api/trabajos/${trabajoId}/control`, cuerpo); } catch (e) { setError(e.message); }
  };

  if (!v) return <Nota>{error || 'Conectando con el entrenamiento…'}</Nota>;
  const t = v.trabajo;
  const f = v.fotograma;
  const enCurso = t.estado === 'en_curso';
  const p = f?.partida;
  const tr = f?.transicion;
  const mov = tr ? MOV[tr.movimiento] : null;
  const recompensa = CON_RECOMPENSA.includes(modelo);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 justify-between">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <Insignia tono={enCurso ? 'acento' : t.estado === 'terminado' ? 'ok' : 'peligro'}>{FASES[v.fase] || v.fase}</Insignia>
          {v.pausado && <Insignia>En pausa</Insignia>}
          {f && <span>Episodio <b>{f.episodio}</b>{f.total ? ` (${t.hechos}/${f.total} en esta sesión)` : ''}</span>}
          {f?.epsilon !== undefined && <span className="text-muted">ε = {fmt(f.epsilon, 3)}</span>}
        </div>
        <div className="flex flex-wrap gap-2">
          {enCurso && (v.pausado
            ? <Boton variante="primario" onClick={() => control({ accion: 'reanudar' })}>Reanudar</Boton>
            : <Boton onClick={() => control({ accion: 'pausar' })}>Pausar</Boton>)}
          {enCurso && <Boton variante="peligro" onClick={() => control({ accion: 'detener' })}>Detener</Boton>}
        </div>
      </div>
      {enCurso && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted" title="Solo añade esperas entre pasos: no cambia lo que aprende el modelo">Ritmo del entrenamiento</span>
            <Segmentado opciones={RITMOS} valor={String(v.pasos_por_segundo)} cambiar={(x) => control({ pasos_por_segundo: Number(x) })} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted" title="Cada cuánto se pide el último paso al servidor; no afecta al entrenamiento">Refresco de pantalla</span>
            <Segmentado opciones={REFRESCOS} valor={refresco} cambiar={setRefresco} />
          </div>
        </div>
      )}
      {enCurso && v.pasos_por_segundo === 0 && <Nota>Al ritmo máximo verás pasos sueltos (el último en cada refresco). Baja el ritmo para seguir cada movimiento.</Nota>}
      <Aviso error={error || t.error} />

      {!f && <Nota>{v.fase === 'entrenando' ? 'Ajustando el modelo con los ejemplos aprobados…' : 'Aún no hay pasos jugados.'}</Nota>}
      {f && (
        <div className="grid gap-3 grid-cols-[minmax(0,1fr)] md:grid-cols-[minmax(0,300px)_minmax(0,1fr)]">
          <div className="space-y-2">
            <div className="mx-auto w-full" style={{ maxWidth: 'min(300px, 42vh)' }}>
              <Tablero ancho={p.ancho} alto={p.alto} segmentos={p.segmentos} manzana={p.manzana} terminada={tr.terminada} tema={tema} />
            </div>
            <div className="flex flex-wrap gap-1 justify-center text-xs">
              <Insignia>{FLECHA[tr.accion]} {tr.accion}</Insignia>
              {mov && <Insignia tono={mov[1]}>{mov[0]}{tr.distancia_antes !== null && tr.distancia_despues !== null ? ` (${tr.distancia_antes}→${tr.distancia_despues})` : ''}</Insignia>}
              {tr.en_ciclo && <Insignia tono="peligro">en ciclo</Insignia>}
              {tr.terminada && <Insignia tono={tr.causa_fin === 'victoria' ? 'ok' : 'peligro'}>fin: {tr.causa_fin}</Insignia>}
            </div>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <Celda e="Manzanas" v={p.manzanas} />
              <Celda e="Longitud" v={p.longitud} />
              <Celda e="Ocupación" v={`${fmt(f.evolucion.ocupacion, 1)} %`} />
              <Celda e="Pasos" v={p.pasos} />
              <Celda e="Se acercó / alejó" v={`${f.episodio_actual.acerca} / ${f.episodio_actual.aleja}`} />
              {recompensa
                ? <Celda e="Recompensa paso / episodio" v={`${fmt(tr.recompensa, 2)} / ${fmt(f.episodio_actual.retorno, 1)}`} />
                : <Celda e="Exploración (pasos)" v={f.episodio_actual.exploracion} />}
            </div>
            <EscalaE umbrales={f.evolucion.umbrales} nivel={f.evolucion.nivel} record={f.evolucion.nivel_max} />
            {recompensa && Object.keys(tr.componentes).length > 0 && (
              <div className="text-xs text-muted">Recompensa del paso: {Object.entries(tr.componentes).map(([k, x]) => `${k} ${fmt(x, 2)}`).join(' · ')}</div>
            )}
            {!recompensa && <div className="text-xs text-muted">{modelo === 'arkis' ? 'ARKIS no usa recompensas: aprende de tus etiquetas.' : 'LERK no usa recompensas: aprende de hechos y resultados.'}</div>}
          </div>
          <div className="space-y-3 min-w-0">
            <Explicacion decision={f.decision} />
            <DetalleMetodologia modelo={modelo} f={f} contexto={v.contexto} />
          </div>
        </div>
      )}
      <HistorialEpisodios episodios={v.episodios} recompensa={recompensa} modelo={modelo} />
    </div>
  );
}

function Celda({ e, v }) {
  return <div className="bg-surface2 border border-line rounded-lg px-2 py-1"><div className="text-muted">{e}</div><div className="font-semibold tabular-nums">{v}</div></div>;
}

function DetalleMetodologia({ modelo, f, contexto }) {
  const e = f.decision?.explicacion || {};
  if (modelo === 'bork' && e.q_antes) {
    return (
      <div className="text-xs space-y-1">
        <div className="font-medium">Actualización Q de este paso</div>
        <div className="overflow-x-auto"><table className="tabla"><thead><tr><th>Acción</th><th className="num">Q antes</th><th className="num">Q después</th><th className="num">Visitas</th></tr></thead>
          <tbody>{['arriba', 'abajo', 'izquierda', 'derecha'].map((a, i) => (
            <tr key={a} className={a === f.decision.accion ? 'text-accent' : ''}><td>{FLECHA[a]} {a}</td><td className="num">{fmt(e.q_antes[i], 3)}</td><td className="num">{fmt(e.q_despues[i], 3)}</td><td className="num">{e.visitas[i]}</td></tr>
          ))}</tbody></table></div>
        <div className="text-muted">Objetivo r + γ·max Q(s′) = {fmt(e.objetivo, 3)} · error TD = {fmt(e.error_td, 3)} · estados en la tabla: {f.extra?.estados_tabla}</div>
      </div>
    );
  }
  if (modelo === 'clark' && f.extra?.favorita_por_componente) {
    const x = f.extra;
    return (
      <div className="text-xs space-y-1">
        <div className="font-medium">Qué habría hecho cada componente por separado</div>
        <div className="overflow-x-auto"><table className="tabla"><thead><tr><th>Componente</th><th>Su favorita</th><th>¿Chocaría ya?</th><th>Acuerdo (episodio)</th></tr></thead>
          <tbody>{['ml', 'simbolico', 'refuerzo'].map((k) => (
            <tr key={k}><td>{{ ml: 'A · ML', simbolico: 'B · Simbólico', refuerzo: 'C · Refuerzo' }[k]}</td><td>{FLECHA[x.favorita_por_componente[k]]} {x.favorita_por_componente[k]}</td>
              <td className={x.chocaria_por_componente[k] ? 'text-danger' : ''}>{x.chocaria_por_componente[k] ? 'sí' : 'no'}</td>
              <td>{f.episodio_actual.decisiones_integradas ? pct((f.episodio_actual.acuerdo[k] || 0) / f.episodio_actual.decisiones_integradas, 0) : '—'}</td></tr>
          ))}</tbody></table></div>
        <div className="text-muted">Reglas: {x.reglas} · estados Q: {x.estados_q} · ML {x.ml_entrenado ? 'entrenado' : 'sin entrenar (aporta 0,5)'}</div>
        <Aprendizajes lista={contexto.aprendizajes} />
      </div>
    );
  }
  if (modelo === 'lerk') {
    return (
      <div className="text-xs space-y-1">
        <div>Hechos de la acción elegida: {(f.extra?.hechos_accion || []).join(', ') || '—'} · reglas conocidas: {f.extra?.reglas ?? '—'}</div>
        <Aprendizajes lista={contexto.aprendizajes} lerk />
        {contexto.reglas && (
          <details><summary className="cursor-pointer">Base de reglas tras el último aprendizaje ({contexto.reglas.length})</summary>
            <ul className="mt-1 space-y-0.5 font-mono">{contexto.reglas.map((r, i) => <li key={i}>[{r.origen}] {r.texto} · conf. {pct(r.confianza, 0)}</li>)}</ul></details>
        )}
      </div>
    );
  }
  if (modelo === 'arkis') {
    const d = contexto.datos; const m = contexto.metricas; const h = contexto.historial_metricas || [];
    return (
      <div className="text-xs space-y-1">
        {d && <div>Entrenado con <b>{d.aprobados}</b> ejemplos aprobados ({Object.entries(d.distribucion_aprobados).map(([a, n]) => `${FLECHA[a]} ${n}`).join(' · ')}) de {d.recopilados} recopilados.</div>}
        {m && <div>Validación por partidas: accuracy {pct(m.accuracy)} · F1 {pct(m.f1_macro)}</div>}
        {h.length > 1 && (
          <Grafica alto={110} etiquetaX="versión" series={[
            { nombre: 'accuracy por versión', color: 'var(--accent)', grosor: 2, puntos: h.filter((x) => x.accuracy !== null).map((x, i) => [i + 1, x.accuracy]) },
          ]} />
        )}
      </div>
    );
  }
  return null;
}

function Aprendizajes({ lista, lerk }) {
  if (!lista?.length) return null;
  const u = lista[lista.length - 1];
  return (
    <div className="border border-line rounded-lg p-2">
      <div className="font-medium">Último aprendizaje (tras el episodio {u.tras_episodio}, {u.version})</div>
      {lerk ? (
        <div>De {u.instancias} pasos de experiencia ({u.fracasos} fracasos, {u.progresos} progresos) indujo {u.prohibiciones} prohibiciones y {u.preferencias} preferencias.
          {u.reglas_nuevas?.length > 0 && <ul className="font-mono mt-1">{u.reglas_nuevas.map((r, i) => <li key={i}>+ {r}</li>)}</ul>}</div>
      ) : (
        <div>ML: {u.ml?.entrenado ? `reentrenado con ${u.ml.instancias} instancias` : u.ml?.motivo} · simbólico: {u.simbolico?.prohibiciones} prohibiciones y {u.simbolico?.preferencias} preferencias · Q: {u.estados_q} estados</div>
      )}
    </div>
  );
}

function HistorialEpisodios({ episodios, recompensa, modelo }) {
  if (!episodios?.length) return null;
  const n = episodios.length;
  const media = (xs) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null);
  const k = Math.min(10, Math.floor(n / 2));
  const primeros = episodios.slice(0, k); const ultimos = episodios.slice(-k);
  const mejor = episodios.reduce((a, b) => (b.manzanas > a.manzanas ? b : a));
  return (
    <div className="space-y-2 border-t border-line pt-3">
      <div className="text-sm font-medium">Comparación entre episodios ({n} en esta sesión)</div>
      <Grafica alto={130} series={[
        { nombre: 'manzanas', color: 'var(--muted)', opacidad: 0.4, grosor: 1, puntos: episodios.map((e, i) => [i + 1, e.manzanas]) },
        { nombre: 'media móvil', color: 'var(--accent)', grosor: 2, puntos: mediaMovil(episodios.map((e) => e.manzanas), Math.max(3, Math.round(n / 15))).map((x, i) => [i + 1, x]) },
        ...(recompensa ? [{ nombre: 'retorno / 10', color: 'var(--snake)', grosor: 1.5, puntos: episodios.map((e, i) => [i + 1, e.retorno / 10]) }] : []),
      ]} />
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        {k > 0 && <Celda e={`Media primeros ${k}`} v={`${fmt(media(primeros.map((e) => e.manzanas)), 1)} manzanas`} />}
        {k > 0 && <Celda e={`Media últimos ${k}`} v={`${fmt(media(ultimos.map((e) => e.manzanas)), 1)} manzanas`} />}
        <Celda e="Mejor episodio" v={`#${mejor.episodio}: ${mejor.manzanas} (E${mejor.nivel})`} />
        <Celda e="Colisiones" v={episodios.filter((e) => e.causa_fin === 'limite' || e.causa_fin === 'cuerpo').length} />
      </div>
      <div className="max-h-48 overflow-auto">
        <table className="tabla min-w-[560px]">
          <thead><tr><th>Ep.</th><th className="num">Manzanas</th><th className="num">Longitud</th><th className="num">Ocup.</th><th className="num">E</th><th className="num">Pasos</th><th className="num">Acerca/aleja</th>{recompensa && <th className="num">Retorno</th>}{modelo === 'clark' && <th>Choques evitables ML/S/RL</th>}<th>Fin</th></tr></thead>
          <tbody>{[...episodios].reverse().slice(0, 50).map((e, i) => (
            <tr key={`${e.episodio}-${i}`}><td>{e.episodio}</td><td className="num">{e.manzanas}</td><td className="num">{e.longitud}</td><td className="num">{fmt(e.ocupacion, 1)} %</td><td className="num">E{e.nivel}</td><td className="num">{e.pasos}</td><td className="num">{e.acerca}/{e.aleja}</td>
              {recompensa && <td className="num">{fmt(e.retorno, 1)}</td>}
              {modelo === 'clark' && <td>{e.choques_evitables_por_componente ? `${e.choques_evitables_por_componente.ml}/${e.choques_evitables_por_componente.simbolico}/${e.choques_evitables_por_componente.refuerzo}` : '—'}</td>}
              <td className={e.causa_fin === 'limite' || e.causa_fin === 'cuerpo' ? 'text-danger' : ''}>{e.causa_fin}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );
}
