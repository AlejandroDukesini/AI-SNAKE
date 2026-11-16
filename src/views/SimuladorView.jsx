/* Simulador: observar a un modelo, demostrarle acciones o jugar. Incluye los tres
   sentidos, la explicación de cada decisión, la evolución E0–E8 y las correcciones. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { ACCIONES, DIFICULTADES, FLECHA, TECLAS, api, fmt } from '../lib/api';
import { usePreferencia } from '../lib/hooks';
import Tablero from '../components/Tablero';
import EscalaE from '../components/Evolucion';
import Explicacion from '../components/Explicacion';
import { SentidoCuerpo, SentidoManzana, SentidoMuros } from '../components/Sentidos';
import { Aviso, Boton, Campo, Insignia, Nota, Numero, Panel, Segmentado, Selector } from '../components/ui';

const MODELOS = { arkis: 'ARKIS', lerk: 'LERK', bork: 'BORK', clark: 'CLARK' };
const MODOS = { observar: 'Observar al modelo', demostrar: 'Demostrar (etiquetar)', jugar: 'Jugar yo' };
const ACELERACION = { 1: '×1', 2: '×2', 5: '×5', 20: '×20' };

export default function SimuladorView({ config, tema, modelo, setModelo }) {
  const [dificultad, setDificultad] = usePreferencia('sim:dificultad', 'medio');
  const [modo, setModo] = usePreferencia('sim:modo', 'observar');
  const [velocidad, setVelocidad] = usePreferencia('sim:velocidad', config.velocidad_por_defecto);
  const [acel, setAcel] = usePreferencia('sim:acel', '1');
  const [semilla, setSemilla] = useState('');
  const [f, setF] = useState(null);
  const [corriendo, setCorriendo] = useState(false);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const ocupado = useRef(false);

  const destinoValido = modo !== 'demostrar' || ['arkis', 'lerk'].includes(modelo);

  const nueva = async () => {
    setError(null); setAviso(null); setCorriendo(false);
    try {
      setF(await api.post('/api/sesiones', {
        modelo: modo === 'jugar' ? null : modelo, dificultad, modo,
        semilla: semilla === '' ? null : Number(semilla), velocidad: Number(velocidad),
      }));
    } catch (e) { setError(e.message); }
  };

  const paso = useCallback(async (accion, pasos = 1) => {
    if (!f || ocupado.current) return;
    ocupado.current = true;
    try {
      setF(await api.post(`/api/sesiones/${f.id}/paso`, accion ? { accion } : { pasos }));
      setError(null);
    } catch (e) { setError(e.message); setCorriendo(false); } finally { ocupado.current = false; }
  }, [f]);

  // Reproducción automática: el intervalo sigue la velocidad del juego; la aceleración
  // agrupa varios pasos por fotograma (render) sin cambiar las reglas ni el tiempo de juego.
  useEffect(() => {
    if (!corriendo || !f || f.modo !== 'observar') return undefined;
    if (f.terminada) { setCorriendo(false); return undefined; }
    const a = Number(acel);
    const intervalo = Math.max(30, 1000 / (Number(velocidad) * Math.min(a, 2)));
    const porFotograma = a <= 2 ? 1 : Math.ceil(a / 2);
    const id = setInterval(() => paso(null, porFotograma), intervalo);
    return () => clearInterval(id);
  }, [corriendo, f, acel, velocidad, paso]);

  // Teclado para demostrar y jugar
  useEffect(() => {
    const t = (e) => {
      if (!f || f.modo === 'observar' || f.terminada || f.pausada) return;
      const a = TECLAS[e.key];
      if (a) { e.preventDefault(); paso(a); }
    };
    window.addEventListener('keydown', t);
    return () => window.removeEventListener('keydown', t);
  }, [f, paso]);

  const pausar = async (p) => {
    setCorriendo(!p && f?.modo === 'observar' ? corriendo : false);
    if (f) setF(await api.post(`/api/sesiones/${f.id}/pausa`, { pausada: p }));
  };

  const corregir = async (accion) => {
    if (!f) return;
    try {
      const situacion = await api.get(`/api/sesiones/${f.id}/situacion`);
      let r;
      if (f.modelo === 'arkis') { await api.post('/api/arkis/ejemplos', { situacion, etiqueta: accion }); r = 'Guardado como ejemplo de ARKIS (pendiente de aprobar en Entrenamiento).'; }
      if (f.modelo === 'lerk') { const c = await api.post('/api/lerk/corregir', { situacion, correcta: accion }, 120_000); r = c.sin_cambios ? 'LERK ya elegía esa acción.' : `LERK corregido: ${c.elegida_antes} → ${c.elegida_despues}${c.excepcion ? ' (excepción añadida)' : ''}${c.regla_nueva ? ' (regla nueva)' : ''}.`; }
      if (f.modelo === 'clark') { const c = await api.post('/api/clark/corregir', { situacion, correcta: accion }, 120_000); r = `CLARK corregido: ${c.elegida_antes} → ${c.elegida_despues}. La tabla Q no se toca: solo aprende de recompensas.`; }
      if (f.modelo === 'bork') r = 'BORK solo aprende de recompensas: no admite correcciones directas.';
      setAviso(r);
      setF(await api.get(`/api/sesiones/${f.id}`));
    } catch (e) { setError(e.message); }
  };

  const capturar = async () => {
    await api.post(`/api/sesiones/${f.id}/capturar`);
    setAviso('Situación guardada sin etiqueta en el conjunto de ARKIS.');
  };

  const p = f?.partida;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-start">
      <div className="space-y-4">

        {!p && (
          <Panel titulo="Sin partida">
            <div className="mx-auto w-full opacity-60" style={{ maxWidth: 'min(100%, 50vh, 420px)' }}>
              <Tablero ancho={{ facil: 4, medio: 8, dificil: 16 }[dificultad]} alto={{ facil: 4, medio: 8, dificil: 16 }[dificultad]} segmentos={[]} manzana={null} tema={tema} />
            </div>
            <Nota className="mt-2 text-center">Tablero {DIFICULTADES[dificultad]} vacío. Configura la sesión a la derecha y pulsa «Nueva partida».</Nota>
          </Panel>
        )}
        {p && (
          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2 text-sm">
              <span>{f.modelo ? f.modelo.toUpperCase() : 'Tú'} · {DIFICULTADES[p.dificultad]} · semilla {p.semilla}{f.version ? ` · ${f.version}` : ''}</span>
              <span className="flex gap-1">
                <Insignia tono="acento">{p.manzanas} manzanas</Insignia>
                <Insignia>{p.pasos} pasos</Insignia>
                {f.terminada && <Insignia tono={p.estado === 'victoria' ? 'ok' : 'peligro'}>{p.estado === 'victoria' ? '¡Victoria! E8' : `Fin: ${p.causa_fin}`}</Insignia>}
                {f.pausada && <Insignia>En pausa</Insignia>}
              </span>
            </div>
            <div className="mx-auto w-full" style={{ maxWidth: 'min(100%, 60vh, 560px)' }}>
              <Tablero ancho={p.ancho} alto={p.alto} segmentos={p.segmentos} manzana={p.manzana} terminada={f.terminada} tema={tema} />
            </div>
            {f.modo !== 'observar' && !f.terminada && (
              <div className="mt-3 flex justify-center gap-2">
                {ACCIONES.map((a) => (
                  <Boton key={a} onClick={() => paso(a)} disabled={f.pausada || !f.percepcion.cuerpo.acciones_disponibles.includes(a)}>{FLECHA[a]} {a}</Boton>
                ))}
              </div>
            )}
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div>Tiempo de juego: <b>{fmt(f.tiempo.juego_s, 1)} s</b></div>
              <div>Tiempo real activo: <b>{fmt(f.tiempo.real_activo_s, 1)} s</b></div>
              <div className={f.tiempo.pasos_en_ciclo ? 'text-danger' : ''}>En ciclo: <b>{fmt(f.tiempo.segundos_en_ciclo, 1)} / 30 s</b></div>
              <div>Velocidad: <b>{f.tiempo.velocidad} mov/s</b></div>
            </div>
          </Panel>
        )}

        {p && (
          <Panel titulo="Evolución">
            <EscalaE umbrales={f.evolucion.umbrales} nivel={f.evolucion.nivel} record={f.evolucion.record?.nivel ?? 0}
              longitud={p.longitud} casillas={p.ancho * p.alto} />
          </Panel>
        )}
      </div>

      <div className="space-y-4">
        <Panel titulo="Sesión">
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Modo"><Selector valor={modo} cambiar={setModo} opciones={MODOS} /></Campo>
            {modo !== 'jugar' && <Campo etiqueta="Modelo"><Selector valor={modelo} cambiar={setModelo} opciones={modo === 'demostrar' ? { arkis: 'ARKIS (ejemplos)', lerk: 'LERK (casos)' } : MODELOS} /></Campo>}
            <Campo etiqueta="Dificultad"><Selector valor={dificultad} cambiar={setDificultad} opciones={DIFICULTADES} /></Campo>
            <Campo etiqueta="Velocidad del juego (mov/s)" ayuda="Define el tiempo de juego: la regla de 30 s equivale a 30 × esta velocidad en pasos."><Numero valor={velocidad} cambiar={setVelocidad} min={1} max={60} /></Campo>
            <Campo etiqueta="Semilla (vacía = aleatoria)"><Numero valor={semilla} cambiar={setSemilla} min={0} /></Campo>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <Boton variante="primario" onClick={nueva} disabled={!destinoValido}>Nueva partida</Boton>
            {f?.modo === 'observar' && <>
              <Boton onClick={() => setCorriendo(!corriendo)} disabled={f.terminada || f.pausada}>{corriendo ? 'Detener' : 'Reproducir'}</Boton>
              <Boton onClick={() => paso(null)} disabled={f.terminada || corriendo}>Un paso</Boton>
              <Segmentado opciones={ACELERACION} valor={String(acel)} cambiar={setAcel} />
            </>}
            {f && <Boton onClick={() => pausar(!f.pausada)} disabled={f.terminada}>{f.pausada ? 'Reanudar' : 'Pausar'}</Boton>}
          </div>
          {modo === 'demostrar' && <Nota className="mt-2">Tú eliges cada movimiento (flechas o WASD). Cada elección se guarda como ejemplo etiquetado de {modelo === 'lerk' ? 'LERK (caso)' : 'ARKIS (pendiente de tu aprobación)'}.</Nota>}
          <div className="mt-2"><Aviso error={error} /></div>
          {aviso && <div className="mt-2 text-sm border border-accent/40 bg-accent/10 rounded-lg px-3 py-2">{aviso}</div>}
        </Panel>
        {f?.decision !== undefined && f?.modo !== 'jugar' && (
          <Panel titulo={f.modo === 'demostrar' ? 'Qué haría el modelo (para comparar)' : 'Decisión y explicación'}>
            <Explicacion decision={f.decision} />
            {f.modo === 'observar' && !f.terminada && (
              <div className="mt-3 border-t border-line pt-3 space-y-2">
                <div className="text-xs text-muted">¿No estás de acuerdo? Indica la acción correcta en esta situación:</div>
                <div className="flex flex-wrap gap-2">
                  {ACCIONES.map((a) => <Boton key={a} onClick={() => corregir(a)} disabled={!f.percepcion.cuerpo.acciones_disponibles.includes(a)}>{FLECHA[a]}</Boton>)}
                  <Boton onClick={capturar}>Capturar para ARKIS</Boton>
                </div>
              </div>
            )}
          </Panel>
        )}
        {f?.ultima && (
          <Panel titulo="Último paso">
            <div className="text-xs space-y-1">
              <div>Acción {FLECHA[f.ultima.accion]} · {f.ultima.comio ? 'comió' : 'no comió'}{f.ultima.ciclo?.en_ciclo ? ` · en ciclo (${f.ultima.ciclo.motivos.join(', ')})` : ''}</div>
              <div className="text-muted">Recompensa común (la usan los componentes de refuerzo): {fmt(f.ultima.recompensa, 3)}</div>
              <div className="grid grid-cols-2 gap-x-3">{Object.entries(f.ultima.componentes).filter(([, v]) => v).map(([k, v]) => <span key={k}>{k}: {fmt(v, 3)}</span>)}</div>
            </div>
          </Panel>
        )}
        {f && (
          <Panel titulo="Percepción · los tres sentidos">
            <div className="grid gap-4 sm:grid-cols-2">
              <SentidoCuerpo cuerpo={f.percepcion.cuerpo} />
              <div className="space-y-4">
                <SentidoManzana manzana={f.percepcion.manzana} />
                <SentidoMuros muros={f.percepcion.muros} />
              </div>
            </div>
          </Panel>
        )}
        {!f && <Panel><Nota>Crea una partida para empezar. En «Observar» decide el modelo; en «Demostrar» decides tú y se guardan ejemplos; en «Jugar» solo juegas.</Nota></Panel>}
      </div>
    </div>
  );
}
