/* ============================================================================
   App — raiz de la aplicacion
   ----------------------------------------------------------------------------
   Aqui vive el estado compartido (configuracion y lista de especimenes) y la
   navegacion entre las cuatro vistas. Nada de logica de juego: eso es de Python.

   Cada vista se monta y se DESMONTA al cambiar de pestana. Es deliberado: al
   desmontarse, sus WebSockets se cierran y el servidor deja de simular partidas
   que nadie mira.
   ============================================================================ */

import { useCallback, useEffect, useState } from 'react';
import { api } from './lib/api';
import { openPreferences } from './lib/consent';
import PlayView from './views/PlayView';
import TrainView from './views/TrainView';
import HistoryView from './views/HistoryView';
import ConfigView from './views/ConfigView';

const VISTAS = [
  { id: 'play',    label: 'Jugar' },
  { id: 'train',   label: 'Entrenar IA' },
  { id: 'history', label: 'Historial' },
  { id: 'config',  label: 'Configuración' },
];

export default function App() {
  const [vista, setVista] = useState('play');
  const [config, setConfig] = useState(null);
  const [meta, setMeta] = useState({ themes: [], grids: [], limits: {} });
  const [models, setModels] = useState([]);
  const [error, setError] = useState(null);

  const cargarModels = useCallback(async () => {
    try {
      const { models: ms } = await api.listModels();
      setModels(ms);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  // Carga inicial: sin configuracion no se puede pintar nada coherente.
  useEffect(() => {
    (async () => {
      try {
        const data = await api.getConfig();
        setConfig({ ...data.config, pop_size: data.pop_size });
        setMeta({ themes: data.themes, grids: data.grids, limits: data.limits });
        await cargarModels();
      } catch (e) {
        setError(`No se pudo hablar con el servidor de la IA. ${e.message}`);
      }
    })();
  }, [cargarModels]);

  // El tema es un atributo en <html>: el CSS hace el resto.
  useEffect(() => {
    if (config?.theme) document.documentElement.dataset.theme = config.theme;
  }, [config?.theme]);

  /* Optimista: se aplica el cambio en pantalla y luego se confirma con el
     servidor, que manda (puede recortar un valor fuera de rango). */
  const cambiarConfig = useCallback(async (patch) => {
    setConfig((c) => ({ ...c, ...patch }));
    try {
      const { config: efectiva } = await api.saveConfig(patch);
      setConfig((c) => ({ ...c, ...efectiva }));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  if (error && !config) {
    return (
      <div className="min-h-full grid place-items-center p-6">
        <div className="max-w-md text-center">
          <h1 className="text-xl font-semibold text-food mb-3">Sin conexión con la IA</h1>
          <p className="text-muted text-sm leading-relaxed mb-4">{error}</p>
          <p className="text-muted text-xs">
            Arranca el proyecto con <code className="text-ink">npm run dev</code>,
            que levanta el servidor de Python y esta web a la vez.
          </p>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="min-h-full grid place-items-center">
        <p className="text-muted text-sm">Cargando…</p>
      </div>
    );
  }

  return (
    <div className="min-h-full px-5 py-8 md:px-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Snake IA</h1>
          <p className="text-sm text-muted mt-1">
            Neuroevolución · redes neuronales entrenadas por selección natural
          </p>
        </header>

        <nav className="flex justify-center gap-1 p-1 mb-8 mx-auto w-fit
                        bg-surface border border-line rounded-2xl">
          {VISTAS.map((v) => (
            <button
              key={v.id}
              onClick={() => setVista(v.id)}
              aria-current={vista === v.id ? 'page' : undefined}
              className={`px-5 py-2 rounded-xl text-sm transition
                ${vista === v.id
                  ? 'bg-accent text-on-accent font-medium'
                  : 'text-muted hover:text-ink'}`}
            >
              {v.label}
            </button>
          ))}
        </nav>

        <main>
          {vista === 'play' && <PlayView theme={config.theme} grid={config.grid} />}
          {vista === 'train' && (
            <TrainView theme={config.theme} config={config} models={models}
                       onSaved={cargarModels} />
          )}
          {vista === 'history' && (
            <HistoryView theme={config.theme} grid={config.grid} models={models}
                         onChanged={cargarModels} />
          )}
          {vista === 'config' && (
            <ConfigView config={config} limits={meta.limits} grids={meta.grids}
                        onChange={cambiarConfig} />
          )}
        </main>

        <footer className="mt-12 pt-6 border-t border-line text-center">
          <button
            type="button"
            onClick={openPreferences}
            className="text-xs text-muted hover:text-ink underline underline-offset-4
                       transition focus-visible:outline-2 focus-visible:outline-offset-2
                       focus-visible:outline-accent rounded"
          >
            Preferencias de cookies
          </button>
        </footer>
      </div>
    </div>
  );
}
