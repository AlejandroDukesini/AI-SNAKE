/* ARKIS: conjunto de ejemplos etiquetados por el usuario + Random Forest. */
import { useState } from 'react';
import { ACCIONES, DIFICULTADES, FLECHA, api, fmt, pct } from '../../lib/api';
import { useDatos } from '../../lib/hooks';
import Tablero from '../../components/Tablero';
import { Boton, Campo, Dato, Interruptor, Nota, Numero, Panel, Plegable, Segmentado, Selector, Vacio } from '../../components/ui';

const FILTROS = { pendientes: 'Pendientes', sin_etiqueta: 'Sin etiqueta', aprobados: 'Aprobados', todos: 'Todos', papelera: 'Papelera' };

export default function PanelArkis({ m, recargar, lanzar, ocupado, tema }) {
  const [filtro, setFiltro] = useState('pendientes');
  const [pagina, setPagina] = useState(0);
  const [lista, recargarLista] = useDatos(`/api/arkis/ejemplos?filtro=${filtro}&offset=${pagina * 24}&limite=24`, [filtro, pagina, m.version]);
  const [semilla, setSemilla] = useState(0);
  const [aumentar, setAumentar] = useState(true);
  const [arboles, setArboles] = useState(100);
  const [dif, setDif] = useState('medio');
  const [episodios, setEpisodios] = useState(30);
  const [arbol] = useDatos('/api/arkis/arbol', [m.version]);
  const e = m.entrenamiento;
  const ds = e.dataset;
  const met = e.metricas;
  const val = met?.validacion;

  const accion = async (fn) => { await fn(); recargarLista(); recargar(); };

  return (
    <div className="space-y-4">
      <Panel titulo="1 · Ejemplos etiquetados por ti">
        <Nota>ARKIS solo aprende de las acciones que tú eliges. Crea ejemplos en el Simulador (modo «Demostrar» con ARKIS, o corrigiendo/capturando situaciones). Aquí los revisas, corriges y apruebas: solo los aprobados se usan para entrenar.</Nota>
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-5 gap-2">
          <Dato etiqueta="Recopilados" valor={ds.recopilados} />
          <Dato etiqueta="Etiquetados" valor={ds.etiquetados} />
          <Dato etiqueta="Aprobados" valor={ds.aprobados} acento />
          <Dato etiqueta="Episodios distintos" valor={ds.episodios} ayuda="La validación agrupa por episodio para evitar fugas de datos" />
          <Dato etiqueta="En papelera" valor={ds.en_papelera} />
        </div>
        <div className="mt-2 text-xs text-muted">Distribución de clases (aprobados): {ACCIONES.map((a) => `${FLECHA[a]} ${ds.distribucion_aprobados[a] || 0}`).join(' · ')}</div>
        <div className="mt-3 flex flex-wrap gap-2 items-center">
          <Segmentado opciones={FILTROS} valor={filtro} cambiar={(f) => { setFiltro(f); setPagina(0); }} />
          <Boton onClick={() => accion(() => api.post('/api/arkis/ejemplos/aprobar', { todos_pendientes: true }))}>Aprobar todos los pendientes</Boton>
        </div>
        <div className="mt-3 grid gap-3 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
          {lista?.ejemplos.map((x) => <Ejemplo key={x.id} x={x} tema={tema} papelera={filtro === 'papelera'} hecho={() => { recargarLista(); recargar(); }} />)}
        </div>
        {lista && lista.total === 0 && <Vacio>No hay ejemplos en este filtro.</Vacio>}
        {lista && lista.total > 24 && (
          <div className="mt-3 flex gap-2 items-center text-sm">
            <Boton disabled={pagina === 0} onClick={() => setPagina(pagina - 1)}>Anterior</Boton>
            <span>{pagina * 24 + 1}–{Math.min(lista.total, (pagina + 1) * 24)} de {lista.total}</span>
            <Boton disabled={(pagina + 1) * 24 >= lista.total} onClick={() => setPagina(pagina + 1)}>Siguiente</Boton>
          </div>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel titulo="2 · Entrenar el Random Forest">
          <div className="grid grid-cols-3 gap-2">
            <Campo etiqueta="Semilla"><Numero valor={semilla} cambiar={setSemilla} min={0} /></Campo>
            <Campo etiqueta="Árboles"><Numero valor={arboles} cambiar={setArboles} min={10} max={500} /></Campo>
            <div className="pt-5"><Interruptor valor={aumentar} cambiar={setAumentar} etiqueta="Simetrías" /></div>
          </div>
          <Nota className="mt-2">Las simetrías giran y reflejan cada ejemplo junto con su etiqueta (8 variantes exactas). No inventan decisiones; solo dentro del entrenamiento de cada pliegue.</Nota>
          <div className="mt-3 flex flex-wrap gap-2">
            <Boton variante="primario" disabled={ocupado || ds.aprobados < 2} onClick={() => lanzar('entrenar', { semilla, aumentar, n_arboles: arboles })}>Entrenar con {ds.aprobados} aprobados</Boton>
          </div>
          <div className="mt-4 border-t border-line pt-3">
            <div className="text-sm font-medium">Modo automático</div>
            <Nota>Reentrena con los ejemplos ya aprobados y se evalúa jugando. Nunca etiqueta por su cuenta.</Nota>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <Campo etiqueta="Dificultad"><Selector valor={dif} cambiar={setDif} opciones={DIFICULTADES} /></Campo>
              <Campo etiqueta="Partidas de evaluación"><Numero valor={episodios} cambiar={setEpisodios} min={5} /></Campo>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              <Boton disabled={ocupado || ds.aprobados < 2} onClick={() => lanzar('automatico', { dificultad: dif, episodios, semilla, aumentar })}>Reentrenar y evaluar</Boton>
              <Boton disabled={ocupado} onClick={() => lanzar('recopilar', { dificultad: dif, episodios: 5, umbral: 0.6 })} title="ARKIS juega y guarda SIN etiqueta las situaciones donde duda">Recopilar dudas</Boton>
            </div>
          </div>
        </Panel>

        <Panel titulo="3 · Validación (sin fugas)">
          {!met && <Nota>Aún no hay modelo entrenado.</Nota>}
          {met && !val && <Nota>{met.aviso}</Nota>}
          {val && (
            <div className="space-y-3">
              <div className="text-xs text-muted">{val.metodo} · {val.n} ejemplos evaluados fuera de pliegue</div>
              <div className="grid grid-cols-4 gap-2">
                <Dato etiqueta="Accuracy" valor={pct(val.accuracy)} acento />
                <Dato etiqueta="Precision" valor={pct(val.precision_macro)} />
                <Dato etiqueta="Recall" valor={pct(val.recall_macro)} />
                <Dato etiqueta="F1" valor={pct(val.f1_macro)} />
              </div>
              <table className="tabla">
                <thead><tr><th>Real ↓ / Predicha →</th>{val.matriz_confusion.clases.map((c) => <th key={c} className="num">{FLECHA[c]}</th>)}<th className="num">F1</th></tr></thead>
                <tbody>{val.matriz_confusion.valores.map((fila, i) => {
                  const c = val.matriz_confusion.clases[i];
                  return (<tr key={c}><td>{FLECHA[c]} {c}</td>{fila.map((v, j) => <td key={j} className={`num ${i === j ? 'text-accent font-medium' : v ? 'text-danger' : 'text-muted'}`}>{v}</td>)}<td className="num">{fmt(val.por_clase[c].f1, 2)}</td></tr>);
                })}</tbody>
              </table>
              <div className="text-xs text-muted">Errores de clasificación: {val.errores.length}. Filtra «Todos» para verlos marcados en rojo y corregirlos.</div>
              <Plegable titulo="Importancia de las características">
                <table className="tabla"><tbody>{met.importancias.map((i) => <tr key={i.rasgo}><td>{i.rasgo}</td><td className="num">{fmt(i.importancia, 3)}</td></tr>)}</tbody></table>
              </Plegable>
              <Plegable titulo="Árbol de decisión explicativo (profundidad 4, solo para leer)">
                <pre className="codigo">{arbol?.arbol || '—'}</pre>
              </Plegable>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function Ejemplo({ x, tema, papelera, hecho }) {
  const s = x.situacion;
  const lado = { facil: 4, medio: 8, dificil: 16 }[s.dificultad];
  const etiquetar = async (a) => { await api.patch(`/api/arkis/ejemplos/${x.id}`, { etiqueta: a }); hecho(); };
  return (
    <div className={`border rounded-xl p-2 space-y-1 ${x.error_validacion ? 'border-danger' : 'border-line'}`}>
      <Tablero ancho={lado} alto={lado} segmentos={s.segmentos} manzana={s.manzana} tema={tema} pequeno />
      <div className="text-[11px] text-muted">{x.origen} · {x.aprobado ? 'aprobado' : 'pendiente'}{x.error_validacion ? ` · ARKIS predijo ${FLECHA[x.error_validacion]}` : ''}</div>
      <div className="flex gap-1">
        {ACCIONES.map((a) => (
          <button key={a} onClick={() => etiquetar(a)} disabled={papelera}
            className={`flex-1 rounded border text-sm py-0.5 ${x.etiqueta === a ? 'bg-accent text-on-accent border-accent' : 'border-line hover:bg-surface2'}`}>{FLECHA[a]}</button>
        ))}
      </div>
      <div className="flex gap-1">
        {papelera ? <Boton className="flex-1 !py-0.5 text-xs" onClick={async () => { await api.post(`/api/arkis/ejemplos/${x.id}/restaurar`); hecho(); }}>Restaurar</Boton> : <>
          <Boton className="flex-1 !py-0.5 text-xs" disabled={!x.etiqueta} onClick={async () => { await api.post('/api/arkis/ejemplos/aprobar', { ids: [x.id], aprobado: !x.aprobado }); hecho(); }}>{x.aprobado ? 'Desaprobar' : 'Aprobar'}</Boton>
          <Boton className="!py-0.5 text-xs" onClick={async () => { await api.del(`/api/arkis/ejemplos/${x.id}`); hecho(); }} title="Mover a la papelera">✕</Boton>
        </>}
      </div>
    </div>
  );
}
