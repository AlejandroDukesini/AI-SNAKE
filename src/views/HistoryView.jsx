/* ============================================================================
   Historial
   ----------------------------------------------------------------------------
   Lista interactiva de los especimenes guardados con su historico de scores.
   Cada uno se puede probar en vivo (carga sus pesos y juega), marcar como
   favorito o borrar.
   ============================================================================ */

import { useCallback, useState } from 'react';
import Board from '../components/Board';
import { api } from '../lib/api';
import { useSocket } from '../lib/useSocket';
import { Panel, Title, Hint, Button, IconButton, Empty, Modal, Stat } from '../components/ui';

/* Los especimenes importados del formato antiguo no registraron sus
   generaciones y no se pueden deducir: se dice, no se inventa una cifra. */
function generacionesTexto(g) {
  if (g === null || g === undefined) return 'generaciones no registradas';
  return `${g} ${g === 1 ? 'generación' : 'generaciones'}`;
}

/* Mini-grafica del historico de scores, en SVG puro: son cuatro lineas y no
   merece la pena arrastrar una libreria de graficos para esto. */
function Sparkline({ sesiones }) {
  const puntos = sesiones.map((s) => s.fitness);
  if (puntos.length < 2) return null;

  const max = Math.max(...puntos);
  const min = Math.min(...puntos);
  const rango = max - min || 1;
  const w = 120, h = 28;
  const d = puntos
    .map((p, i) => {
      const x = (i / (puntos.length - 1)) * w;
      const y = h - ((p - min) / rango) * h;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={w} height={h} className="shrink-0" aria-label="Evolución del score">
      <path d={d} fill="none" stroke="var(--accent)" strokeWidth="1.5"
            strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ModelRow({ m, index, onProbar, onFavorito, onBorrar }) {
  return (
    <div className="flex items-center gap-4 bg-surface border border-line
                    rounded-panel px-5 py-4">
      <button
        onClick={() => onFavorito(m)}
        aria-pressed={m.favorito}
        title={m.favorito ? 'Quitar de favoritos' : 'Marcar como favorito'}
        className={`text-xl transition hover:scale-110
          ${m.favorito ? 'text-accent' : 'text-muted hover:text-accent'}`}
      >
        {m.favorito ? '★' : '☆'}
      </button>

      <span className="text-xs text-muted tabular-nums w-6">#{index + 1}</span>

      <div className="flex-1 min-w-0">
        <div className="font-medium text-ink truncate">{m.nombre}</div>
        <div className="text-xs text-muted mt-0.5">
          historial/{m.carpeta}/ · {generacionesTexto(m.generaciones)} ·
          {' '}tamaño {m.length} · tablero {m.grid}×{m.grid}
        </div>
        <div className="text-xs text-muted">
          {m.sesiones?.length ?? 0} entrenamiento{(m.sesiones?.length ?? 0) === 1 ? '' : 's'}
          {' '}· creada {m.fecha_creacion || '—'}
        </div>
      </div>

      <Sparkline sesiones={m.sesiones ?? []} />

      <span className="text-lg font-semibold text-accent tabular-nums" title="Récord de fitness">
        {m.fitness}
      </span>

      <div className="flex gap-2">
        <IconButton label="Probar esta IA" onClick={() => onProbar(m)}>▶</IconButton>
        <IconButton label="Borrar espécimen" onClick={() => onBorrar(m)}
                    className="hover:!bg-danger hover:!border-danger hover:!text-on-danger">
          🗑
        </IconButton>
      </div>
    </div>
  );
}

export default function HistoryView({ theme, grid, models, onChanged }) {
  const [probando, setProbando] = useState(null);   // Especimen en la ventana de prueba
  const [demoSnake, setDemoSnake] = useState(null);
  const [borrar, setBorrar] = useState(null);
  const [vaciar, setVaciar] = useState(false);
  const [soloFavoritos, setSoloFavoritos] = useState(false);

  const onDemo = useCallback((msg) => {
    if (msg.type === 'state') setDemoSnake(msg.snake);
  }, []);

  // El hook cierra el socket solo al cerrar la ventana (probando -> null).
  useSocket(probando ? `/ws/demo/${encodeURIComponent(probando.carpeta)}` : null, onDemo,
            { enabled: !!probando });

  const favorito = async (m) => {
    await api.setFavorite(m.carpeta, !m.favorito);
    onChanged();
  };

  const confirmarBorrado = async () => {
    await api.deleteModel(borrar.carpeta);
    setBorrar(null);
    onChanged();
  };

  const confirmarVaciado = async () => {
    await api.clearHistory();
    setVaciar(false);
    onChanged();
  };

  const visibles = soloFavoritos ? models.filter((m) => m.favorito) : models;
  const favoritos = models.filter((m) => m.favorito).length;

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <Title>Historial</Title>
          <Hint className="mt-1">
            {models.length} espécimen{models.length === 1 ? '' : 'es'} en <code>historial/</code>
            {' '}· pulsa ▶ para ver jugar a cualquiera.
          </Hint>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setSoloFavoritos((v) => !v)}>
            {soloFavoritos ? 'Ver todos' : `★ Solo favoritos (${favoritos})`}
          </Button>
          <Button variant="danger" onClick={() => setVaciar(true)}
                  disabled={models.length === 0}>
            Vaciar historial
          </Button>
        </div>
      </div>

      {visibles.length === 0 ? (
        <Empty>
          {soloFavoritos
            ? <>Aún no has marcado ningún favorito.<br />Pulsa la estrella ☆ de un espécimen.</>
            : <>Todavía no hay especímenes.<br />Ve a <b className="text-ink">Entrenar IA</b> y crea el primero.</>}
        </Empty>
      ) : (
        <div className="space-y-3">
          {visibles.map((m, i) => (
            <ModelRow key={m.carpeta} m={m} index={i}
                      onProbar={(x) => { setDemoSnake(null); setProbando(x); }}
                      onFavorito={favorito} onBorrar={setBorrar} />
          ))}
        </div>
      )}

      {/* --- Probar --- */}
      <Modal open={!!probando} onClose={() => setProbando(null)}
             title={`Probando: ${probando?.nombre ?? ''}`}>
        <Hint className="mb-4">
          Récord {probando?.fitness} · {generacionesTexto(probando?.generaciones)} ·
          {' '}entrenada en {probando?.grid}×{probando?.grid}, jugando en {grid}×{grid}
        </Hint>
        <Board snake={demoSnake} grid={grid} theme={theme} />
        <div className="grid grid-cols-2 gap-3 my-4">
          <Stat label="Tamaño ahora" value={demoSnake?.length ?? '—'} accent />
          <Stat label="Energía" value={demoSnake?.energy ?? '—'} />
        </div>
        <div className="flex justify-end">
          <Button onClick={() => setProbando(null)}>Cerrar</Button>
        </div>
      </Modal>

      {/* --- Borrar uno --- */}
      <Modal open={!!borrar} onClose={() => setBorrar(null)} danger
             title="¿Borrar este espécimen?">
        <Hint className="mb-5">
          Se eliminará la carpeta <code className="text-ink">historial/{borrar?.carpeta}/</code>
          {' '}entera, con su red neuronal y su histórico. No se puede deshacer.
        </Hint>
        <div className="flex justify-end gap-2">
          <Button onClick={() => setBorrar(null)}>Cancelar</Button>
          <Button variant="danger" onClick={confirmarBorrado}>Sí, borrar</Button>
        </div>
      </Modal>

      {/* --- Vaciar historial --- */}
      <Modal open={vaciar} onClose={() => setVaciar(false)} danger title="¡Cuidado!">
        <Hint className="mb-4">
          Vas a borrar <b className="text-ink">{models.length - favoritos}</b> especímenes
          y sus redes neuronales. Esta acción no se puede deshacer.
        </Hint>
        <div className="bg-surface2 border-l-2 border-accent rounded-lg px-4 py-3 mb-5">
          <p className="text-xs text-muted">
            ★ Tus <b className="text-ink">{favoritos}</b> favoritos <b className="text-ink">se conservarán</b>.
          </p>
        </div>
        <div className="flex justify-end gap-2">
          <Button onClick={() => setVaciar(false)}>Cancelar</Button>
          <Button variant="danger" onClick={confirmarVaciado}>Sí, vaciar el historial</Button>
        </div>
      </Modal>
    </div>
  );
}
