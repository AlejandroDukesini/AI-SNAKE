/* ARKIS AI LAB — interfaz del laboratorio. */
import { useEffect, useState } from 'react';
import { api } from './lib/api';
import { usePreferencia } from './lib/hooks';
import { Segmentado } from './components/ui';
import PanelView from './views/PanelView';
import SimuladorView from './views/SimuladorView';
import EntrenamientoView from './views/EntrenamientoView';
import EvolucionView from './views/EvolucionView';
import ComparacionView from './views/ComparacionView';
import DocsView from './views/DocsView';

const VISTAS = {
  panel: 'Panel', simulador: 'Simulador', entrenamiento: 'Entrenamiento',
  evolucion: 'Evolución', comparacion: 'Comparación', docs: 'Documentación',
};
const TEMAS = { oscura: 'Oscuro', minimalista: 'Claro', verde: 'Terminal' };

export default function App() {
  const [vista, setVista] = usePreferencia('vista', 'panel');
  const [tema, setTema] = usePreferencia('tema', 'oscura');
  const [modelo, setModelo] = usePreferencia('modelo', 'arkis');
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { document.documentElement.dataset.theme = tema; }, [tema]);
  useEffect(() => {
    api.get('/api/config').then(setConfig).catch((e) => setError(e.message));
  }, []);

  const ir = (v, m) => { if (m) setModelo(m); setVista(v); };
  const props = { config, tema, modelo, setModelo, ir };

  return (
    <div className="min-h-full">
      <header className="border-b border-line bg-surface/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3 justify-between">
          <div>
            <div className="font-semibold tracking-tight">ARKIS AI LAB</div>
            <div className="text-xs text-muted">Cinco metodologías de aprendizaje, un mismo Snake</div>
          </div>
          <nav className="overflow-x-auto max-w-full"><Segmentado opciones={VISTAS} valor={vista} cambiar={setVista} /></nav>
          <select className="bg-surface2 border border-line rounded-lg px-2 py-1 text-sm" value={tema} onChange={(e) => setTema(e.target.value)}>
            {Object.entries(TEMAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-5">
        {error && (
          <div className="mb-4 text-sm border border-danger/40 bg-danger/10 rounded-xl p-4">
            No hay conexión con el servidor del laboratorio ({error}). Arráncalo con <code>npm run dev</code> o <code>python run.py</code>.
          </div>
        )}
        {config && vista === 'panel' && <PanelView {...props} />}
        {config && vista === 'simulador' && <SimuladorView {...props} />}
        {config && vista === 'entrenamiento' && <EntrenamientoView {...props} />}
        {config && vista === 'evolucion' && <EvolucionView {...props} />}
        {config && vista === 'comparacion' && <ComparacionView {...props} />}
        {vista === 'docs' && <DocsView {...props} />}
      </main>
    </div>
  );
}
