/* ARKIS: aprendizaje supervisado. Tú enseñas con ejemplos etiquetados (situación → acción
   correcta) y un Random Forest aprende a imitarlos. Flujo guiado en 5 pasos. */
import { useEffect, useState } from 'react';
import { ACCIONES, DIFICULTADES, FLECHA, api, fmt, pct } from '../../lib/api';
import { useDatos } from '../../lib/hooks';
import Tablero from '../../components/Tablero';
import Explicacion from '../../components/Explicacion';
import { Distribucion } from '../../components/Distribucion';
import { Aviso, Boton, Campo, Dato, Insignia, Interruptor, Nota, Numero, Panel, Plegable, Segmentado, Selector, Vacio } from '../../components/ui';

const FILTROS = { pendientes: 'Sin revisar', sin_etiqueta: 'Sin etiqueta', aprobados: 'Revisados', todos: 'Todos', papelera: 'Papelera' };
const LADO = { facil: 4, medio: 8, dificil: 16 };

export default function PanelArkis({ m, recargar, lanzar, ocupado, tema, visor, hayTrabajo }) {
  const [version, setVersion] = useState(0);
  const [pestana, setPestana] = useState(hayTrabajo ? 'vivo' : 'etiquetar');
  useEffect(() => { if (ocupado) setPestana('vivo'); }, [ocupado]);
  const refrescar = () => { setVersion((v) => v + 1); recargar(); };
  const e = m.entrenamiento;

  const controles = <Entrenar m={m} lanzar={lanzar} ocupado={ocupado} />;
  // Las dos vistas siguen montadas (solo se ocultan): cambiar de pestaña no pierde la partida.
  const principal = (
    <>
      <div className={pestana === 'etiquetar' ? '' : 'hidden'}><EtiquetadorGuiado tema={tema} alGuardar={refrescar} /></div>
      <div className={pestana === 'vivo' ? '' : 'hidden'}>{visor}</div>
    </>
  );
  return (
    <Distribucion visor={principal} controles={controles}
      titulo={pestana === 'etiquetar' ? 'Pasos 1–3 · Crear ejemplos etiquetados' : 'Entrenamiento en vivo'}
      accion={<Segmentado opciones={{ etiquetar: 'Etiquetar', vivo: 'En vivo' }} valor={pestana} cambiar={setPestana} />}>
      <QueEsUnaEtiqueta />
      <Revision tema={tema} ds={e.dataset} version={`${m.version}-${version}`} hecho={refrescar} />
      <Validacion met={e.metricas} version={m.version} />
    </Distribucion>
  );
}

/* --- Explicación ---------------------------------------------------------------- */
function QueEsUnaEtiqueta() {
  return (
    <Panel titulo="Cómo aprende ARKIS: ejemplos con etiqueta">
      <div className="grid gap-4 md:grid-cols-3 text-sm leading-relaxed">
        <div>
          <div className="font-medium">¿Qué es una etiqueta?</div>
          <p className="text-muted">Es la <b className="text-ink">respuesta que le das al modelo</b> para enseñarle qué acción debería tomar en una situación concreta. Ejemplo: «con la manzana a la derecha y el camino libre, la acción correcta es <b className="text-ink">→ derecha</b>».</p>
        </div>
        <div>
          <div className="font-medium">¿Por qué la necesita?</div>
          <p className="text-muted">ARKIS es aprendizaje <b className="text-ink">supervisado</b>: no prueba ni recibe premios. Busca patrones entre las situaciones y las respuestas que tú le diste, y luego los aplica a situaciones nuevas. Sin etiquetas no sabe nada: juega al azar.</p>
        </div>
        <div>
          <div className="font-medium">Un ejemplo contiene</div>
          <p className="text-muted">1) la <b className="text-ink">situación</b> (dónde están la cabeza, el cuerpo, la manzana y los muros, y hacia dónde va) y 2) la <b className="text-ink">acción</b> que tú elegiste. ARKIS convierte la situación en 27 números (peligro, espacio libre y distancia a la manzana en cada dirección…).</p>
        </div>
      </div>
      <div className="mt-3 text-xs text-muted border-t border-line pt-2">
        <b>No es una recompensa.</b> Una recompensa (BORK) solo dice «bien» o «mal» después de actuar; una etiqueta dice <i>cuál era la respuesta correcta</i>. ARKIS nunca se etiqueta a sí mismo: todas las etiquetas son tuyas, y puedes corregirlas o borrarlas cuando quieras.
      </div>
    </Panel>
  );
}

/* --- Pasos 1-3: crear ejemplos ------------------------------------------------------ */
function EtiquetadorGuiado({ tema, alGuardar }) {
  const [dif, setDif] = useState('medio');
  const [f, setF] = useState(null);
  const [eleccion, setEleccion] = useState(null);
  const [aprobar, setAprobar] = useState(true);
  const [verArkis, setVerArkis] = useState(false);
  const [aviso, setAviso] = useState(null);
  const [error, setError] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  const nueva = async () => {
    setError(null); setAviso(null); setEleccion(null);
    try { setF(await api.post('/api/sesiones', { modelo: 'arkis', dificultad: dif, modo: 'demostrar' })); } catch (err) { setError(err.message); }
  };
  const avanzar = async (guardar) => {
    if (!eleccion || ocupado) return;
    setOcupado(true); setError(null);
    try {
      const r = await api.post(`/api/sesiones/${f.id}/paso`, { accion: eleccion, guardar, aprobar });
      setAviso(guardar && r.ultimo_ejemplo
        ? `Ejemplo ${r.ultimo_ejemplo.id} guardado: en esa situación → ${FLECHA[eleccion]} ${eleccion}${r.ultimo_ejemplo.aprobado ? ' (revisado, se usará al entrenar)' : ' (pendiente de revisar)'}.`
        : `Movido a ${eleccion} sin guardar ejemplo.`);
      setF(r); setEleccion(null);
      if (guardar) alGuardar();
    } catch (err) { setError(err.message); } finally { setOcupado(false); }
  };

  const p = f?.partida; const c = f?.percepcion.cuerpo; const mz = f?.percepcion.manzana;
  return (
    <div>
      <Nota className="mb-2">Una <b className="text-ink">etiqueta</b> es la respuesta que le das a ARKIS: «en esta situación, la acción correcta es…». Con muchas, aprende a imitarte (explicación completa más abajo).</Nota>
      <div className="flex flex-wrap items-end gap-2 mb-3">
        <Campo etiqueta="Tablero"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
        <Boton variante="primario" onClick={nueva}>{f ? 'Nueva partida' : 'Empezar a etiquetar'}</Boton>
        {f && <span className="text-xs text-muted">Ejemplos guardados en esta partida: {f.ejemplos_guardados}</span>}
      </div>
      <Aviso error={error} />
      {!f && <Nota>Se abrirá una partida. En cada situación eliges tú el movimiento correcto; ARKIS aprenderá de esas elecciones.</Nota>}
      {f && (
        <div className="grid gap-4 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)] items-start">
          <div className="space-y-2">
            <div className="mx-auto w-full" style={{ maxWidth: 'min(280px, 40vh)' }}>
              <Tablero ancho={p.ancho} alto={p.alto} segmentos={p.segmentos} manzana={p.manzana} terminada={f.terminada} tema={tema} />
            </div>
            <div className="text-xs text-muted text-center">{p.manzanas} manzanas · {p.pasos} pasos{f.terminada ? ` · fin: ${p.causa_fin}` : ''}</div>
          </div>
          {f.terminada ? (
            <div className="space-y-2">
              <Nota>La partida terminó ({p.causa_fin}). Los ejemplos ya están guardados. Empieza otra partida para seguir enseñando: variar las situaciones ayuda a que ARKIS generalice.</Nota>
              <Boton variante="primario" onClick={nueva}>Nueva partida</Boton>
            </div>
          ) : (
            <div className="space-y-3 text-sm">
              <div>
                <div className="font-medium">Paso 1 · Observa la situación</div>
                <ul className="text-xs grid sm:grid-cols-2 gap-x-4 gap-y-0.5 mt-1">
                  <li>Cabeza: <b>({c.cabeza.join(', ')})</b></li>
                  <li>Dirección actual: <b>{FLECHA[c.direccion]} {c.direccion}</b></li>
                  <li>Cuerpo: <b>{c.longitud}</b> casilla(s), cola en ({c.cola.join(', ')})</li>
                  <li>Manzana: {mz ? <b>({mz.x}, {mz.y}) · {mz.direccion_relativa.join(' / ')} · a {mz.manhattan} pasos</b> : '—'}</li>
                </ul>
              </div>
              <div>
                <div className="font-medium">Paso 2 · Elige la acción correcta</div>
                <div className="grid grid-cols-2 gap-2 mt-1">
                  {ACCIONES.map((a) => {
                    const disponible = c.acciones_disponibles.includes(a);
                    const choque = c.colision_por_accion[a];
                    const acerca = mz && (Math.abs(mz.dx - { arriba: 0, abajo: 0, izquierda: -1, derecha: 1 }[a]) + Math.abs(mz.dy - { arriba: -1, abajo: 1, izquierda: 0, derecha: 0 }[a])) < mz.manhattan;
                    return (
                      <button key={a} disabled={!disponible} onClick={() => setEleccion(a)}
                        className={`text-left rounded-lg border px-2 py-1.5 transition disabled:opacity-35 disabled:cursor-not-allowed
                          ${eleccion === a ? 'border-accent bg-accent/10' : 'border-line hover:bg-surface2'}`}>
                        <div className="font-medium">{FLECHA[a]} {a}</div>
                        <div className="text-[11px] text-muted">
                          {!disponible ? 'no disponible (giro de 180°)' : choque ? <span className="text-danger">choca con {choque === 'limite' ? 'el límite' : 'su cuerpo'}</span> : 'casilla libre'}
                          {disponible && !choque && ` · ${acerca ? 'se acerca' : 'se aleja'} · ${c.espacio_por_accion[a]} casillas alcanzables`}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <div className="font-medium">Paso 3 · Guarda el ejemplo</div>
                <div className="mt-1"><Interruptor valor={aprobar} cambiar={setAprobar} etiqueta="Marcarlo como revisado (solo los revisados se usan para entrenar)" /></div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Boton variante="primario" disabled={!eleccion || ocupado} onClick={() => avanzar(true)}>Guardar ejemplo y mover</Boton>
                  <Boton disabled={!eleccion || ocupado} onClick={() => avanzar(false)} title="Útil para saltar situaciones poco interesantes">Mover sin guardar</Boton>
                </div>
                {aviso && <div className="mt-2 text-xs border border-accent/40 bg-accent/10 rounded-lg px-2 py-1">{aviso}</div>}
              </div>
              <div className="border-t border-line pt-2">
                <Interruptor valor={verArkis} cambiar={setVerArkis} etiqueta="Ver qué haría ARKIS ahora (solo para comparar; no es una etiqueta)" />
                {verArkis && <div className="mt-2"><Explicacion decision={f.decision} /></div>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* --- Paso 4: revisar ------------------------------------------------------------- */
function Revision({ tema, ds, version, hecho }) {
  const [filtro, setFiltro] = useState('todos');
  const [pagina, setPagina] = useState(0);
  const [lista, recargarLista] = useDatos(`/api/arkis/ejemplos?filtro=${filtro}&offset=${pagina * 18}&limite=18`, [filtro, pagina, version]);
  const listo = () => { recargarLista(); hecho(); };
  return (
    <Panel titulo="Paso 4 · Revisa tus ejemplos">
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
        <Dato etiqueta="Guardados" valor={ds.recopilados} ayuda="Incluye capturas sin etiqueta" />
        <Dato etiqueta="Con etiqueta" valor={ds.etiquetados} />
        <Dato etiqueta="Revisados (se usan)" valor={ds.aprobados} acento />
        <Dato etiqueta="Partidas distintas" valor={ds.episodios} ayuda="La validación separa por partida para no hacer trampa" />
        <Dato etiqueta="En papelera" valor={ds.en_papelera} />
      </div>
      <div className="mt-2 text-xs text-muted">Respuestas revisadas por acción: {ACCIONES.map((a) => `${FLECHA[a]} ${ds.distribucion_aprobados[a] || 0}`).join(' · ')}. Si una acción tiene muy pocos ejemplos, ARKIS la aprenderá peor.</div>
      <div className="mt-3 flex flex-wrap gap-2 items-center">
        <Segmentado opciones={FILTROS} valor={filtro} cambiar={(x) => { setFiltro(x); setPagina(0); }} />
        <Boton onClick={async () => { await api.post('/api/arkis/ejemplos/aprobar', { todos_pendientes: true }); listo(); }}>Marcar todos como revisados</Boton>
      </div>
      <div className="mt-3 grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {lista?.ejemplos.map((x) => <Ejemplo key={x.id} x={x} tema={tema} papelera={filtro === 'papelera'} hecho={listo} />)}
      </div>
      {lista && lista.total === 0 && <Vacio>No hay ejemplos aquí. Créalos en los pasos 1–3.</Vacio>}
      {lista && lista.total > 18 && (
        <div className="mt-3 flex gap-2 items-center text-sm">
          <Boton disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>Anterior</Boton>
          <span>{pagina * 18 + 1}–{Math.min(lista.total, (pagina + 1) * 18)} de {lista.total}</span>
          <Boton disabled={(pagina + 1) * 18 >= lista.total} onClick={() => setPagina(pagina + 1)}>Siguiente</Boton>
        </div>
      )}
    </Panel>
  );
}

function Ejemplo({ x, tema, papelera, hecho }) {
  const s = x.situacion;
  const cabeza = s.segmentos[0];
  const etiquetar = async (a) => { await api.patch(`/api/arkis/ejemplos/${x.id}`, { etiqueta: a }); hecho(); };
  return (
    <div className={`border rounded-xl p-2 space-y-1 ${x.error_validacion ? 'border-danger' : 'border-line'}`}>
      <Tablero ancho={LADO[s.dificultad]} alto={LADO[s.dificultad]} segmentos={s.segmentos} manzana={s.manzana} tema={tema} pequeno />
      <div className="text-[11px] leading-tight">
        <div>Cabeza ({cabeza.join(',')}) {FLECHA[s.direccion]} · manzana {s.manzana ? `(${s.manzana.join(',')})` : '—'}</div>
        <div className="font-medium">Acción asignada: {x.etiqueta ? `${FLECHA[x.etiqueta]} ${x.etiqueta}` : <span className="text-danger">sin etiqueta</span>}</div>
        <div className="text-muted">#{x.id} · {x.fecha.replace('T', ' ')}</div>
        <div className="text-muted">{x.origen} · {x.aprobado ? 'revisado' : 'sin revisar'}{x.historial?.length ? ` · corregido ${x.historial.length}×` : ''}</div>
        {x.error_validacion && <div className="text-danger">ARKIS predijo {FLECHA[x.error_validacion]} en la validación</div>}
      </div>
      <div className="flex gap-1" title="Cambiar la acción (editar)">
        {ACCIONES.map((a) => (
          <button key={a} onClick={() => etiquetar(a)} disabled={papelera}
            className={`flex-1 rounded border text-sm py-0.5 ${x.etiqueta === a ? 'bg-accent text-on-accent border-accent' : 'border-line hover:bg-surface2'}`}>{FLECHA[a]}</button>
        ))}
      </div>
      <div className="flex gap-1">
        {papelera ? <Boton className="flex-1 !py-0.5 text-xs" onClick={async () => { await api.post(`/api/arkis/ejemplos/${x.id}/restaurar`); hecho(); }}>Restaurar</Boton> : <>
          <Boton className="flex-1 !py-0.5 text-xs" disabled={!x.etiqueta} onClick={async () => { await api.post('/api/arkis/ejemplos/aprobar', { ids: [x.id], aprobado: !x.aprobado }); hecho(); }}>{x.aprobado ? 'Quitar revisión' : 'Revisado'}</Boton>
          <Boton className="!py-0.5 text-xs" onClick={async () => { await api.del(`/api/arkis/ejemplos/${x.id}`); hecho(); }} title="Eliminar (va a la papelera)">✕</Boton>
        </>}
      </div>
    </div>
  );
}

/* --- Paso 5: entrenar ---------------------------------------------------------------- */
function Entrenar({ m, lanzar, ocupado }) {
  const [semilla, setSemilla] = useState(0);
  const [aumentar, setAumentar] = useState(true);
  const [arboles, setArboles] = useState(100);
  const [dif, setDif] = useState('medio');
  const [episodios, setEpisodios] = useState(20);
  const ds = m.entrenamiento.dataset;
  const met = m.entrenamiento.metricas;
  const val = met?.validacion;
  return (
    <>
      <Panel titulo="Paso 5 · Entrenar ARKIS">
        <div className="text-sm">
          Tienes <b>{ds.recopilados}</b> ejemplos: <b>{ds.etiquetados}</b> con etiqueta y <b className="text-accent">{ds.aprobados}</b> revisados. Se entrenará con los <b>{ds.aprobados}</b> revisados.
        </div>
        {ds.aprobados < 2 && <Nota className="mt-1">Necesitas al menos 2 ejemplos revisados de acciones distintas (y de 2 partidas para poder medir el acierto).</Nota>}
        <div className="mt-2 grid grid-cols-3 gap-2">
          <Campo etiqueta="Semilla"><Numero valor={semilla} cambiar={setSemilla} min={0} /></Campo>
          <Campo etiqueta="Árboles"><Numero valor={arboles} cambiar={setArboles} min={10} max={500} /></Campo>
          <div className="pt-5"><Interruptor valor={aumentar} cambiar={setAumentar} etiqueta="Simetrías" /></div>
        </div>
        <Nota className="mt-1">«Simetrías» añade cada ejemplo girado y reflejado junto con su respuesta girada (8 variantes exactas). No inventa respuestas nuevas.</Nota>
        <div className="mt-3 flex flex-wrap gap-2">
          <Boton variante="primario" disabled={ocupado || ds.aprobados < 2} onClick={() => lanzar('entrenar', { semilla, aumentar, n_arboles: arboles })}>Entrenar</Boton>
        </div>
        {met && (
          <div className="mt-3 text-sm border-t border-line pt-2 space-y-1">
            <div className="font-medium">Resultado del último entrenamiento ({m.version})</div>
            <div>Usó <b>{met.ejemplos}</b> ejemplos de <b>{met.episodios}</b> partida(s){met.aumento ? `, ${met.filas_entrenamiento} con simetrías` : ''}.</div>
            {val ? <div>En partidas que <b>no vio</b> al entrenar, eligió tu misma acción el <b className="text-accent">{pct(val.accuracy)}</b> de las veces (F1 {pct(val.f1_macro)}). Abajo, los detalles y los errores.</div>
              : <div className="text-muted">{met.aviso}</div>}
          </div>
        )}
      </Panel>
      <Panel titulo="Ver a ARKIS jugar">
        <Nota>Reentrena con los ejemplos revisados y juega partidas de evaluación: en el visor verás cada predicción, la decisión y su resultado. Nunca crea etiquetas.</Nota>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Campo etiqueta="Tablero"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
          <Campo etiqueta="Partidas"><Numero valor={episodios} cambiar={setEpisodios} min={1} /></Campo>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          <Boton variante="primario" disabled={ocupado || ds.aprobados < 2} onClick={() => lanzar('automatico', { dificultad: dif, episodios, semilla, aumentar })}>Entrenar y jugar</Boton>
          <Boton disabled={ocupado} onClick={() => lanzar('recopilar', { dificultad: dif, episodios: 5, umbral: 0.6 })} title="ARKIS juega y guarda SIN etiqueta las situaciones donde duda, para que tú las etiquetes">Recopilar situaciones dudosas</Boton>
        </div>
      </Panel>
    </>
  );
}

/* --- Métricas ---------------------------------------------------------------------- */
function Validacion({ met, version }) {
  const [arbol] = useDatos('/api/arkis/arbol', [version]);
  const val = met?.validacion;
  return (
    <Panel titulo="Qué aprendió ARKIS (validación sin trampas)">
      {!met && <Nota>Aún no hay modelo entrenado.</Nota>}
      {met && !val && <Nota>{met.aviso}</Nota>}
      {val && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <Nota>Se reserva cada vez una parte de tus partidas, se entrena con el resto y se comprueba si ARKIS elige lo mismo que tú en las reservadas ({val.metodo}, {val.n} ejemplos).</Nota>
            <div className="grid grid-cols-4 gap-2">
              <Dato etiqueta="Acierto" valor={pct(val.accuracy)} acento ayuda="Accuracy: proporción de ejemplos en los que eligió tu acción" />
              <Dato etiqueta="Precisión" valor={pct(val.precision_macro)} ayuda="Cuando dice X, ¿cuántas veces era X?" />
              <Dato etiqueta="Exhaustividad" valor={pct(val.recall_macro)} ayuda="Recall: de todos los X, ¿cuántos reconoció?" />
              <Dato etiqueta="F1" valor={pct(val.f1_macro)} ayuda="Equilibrio entre precisión y exhaustividad" />
            </div>
            <table className="tabla">
              <thead><tr><th>Tu acción ↓ / ARKIS →</th>{val.matriz_confusion.clases.map((c) => <th key={c} className="num">{FLECHA[c]}</th>)}<th className="num">F1</th></tr></thead>
              <tbody>{val.matriz_confusion.valores.map((fila, i) => {
                const c = val.matriz_confusion.clases[i];
                return (<tr key={c}><td>{FLECHA[c]} {c}</td>{fila.map((v, j) => <td key={j} className={`num ${i === j ? 'text-accent font-medium' : v ? 'text-danger' : 'text-muted'}`}>{v}</td>)}<td className="num">{fmt(val.por_clase[c].f1, 2)}</td></tr>);
              })}</tbody>
            </table>
            <div className="text-xs text-muted">La diagonal son aciertos; fuera de ella, errores ({val.errores.length}). En «Todos» verás en rojo los ejemplos que falló.</div>
          </div>
          <div className="space-y-2">
            <Plegable titulo="Qué datos mira más (importancia)" abierto>
              <table className="tabla"><tbody>{met.importancias.map((i) => <tr key={i.rasgo}><td>{i.rasgo}</td><td className="num">{fmt(i.importancia, 3)}</td></tr>)}</tbody></table>
            </Plegable>
            <Plegable titulo="Árbol de decisión explicativo (solo para leer)">
              <pre className="codigo">{arbol?.arbol || '—'}</pre>
            </Plegable>
          </div>
        </div>
      )}
      {met && <div className="mt-2"><Insignia>{version}</Insignia></div>}
    </Panel>
  );
}
