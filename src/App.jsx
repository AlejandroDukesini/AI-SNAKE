/* IA-SNAKE — interfaz del laboratorio. */
import { useEffect, useState } from 'react';
import { API_URL, api, guardarToken, leerToken } from './lib/api';
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
const MODELOS_URL = ['arkis', 'lerk', 'bork', 'clark', 'mabu'];

/* Navegación por URL (#/vista/modelo): recargar conserva la pestaña y se puede enlazar. */
function leerHash() {
  const [v, m] = window.location.hash.replace(/^#\/?/, '').split('/');
  return { vista: VISTAS[v] ? v : null, modelo: MODELOS_URL.includes(m) ? m : null };
}

export default function App() {
  const [vista, setVista] = usePreferencia('vista', 'panel', leerHash().vista);
  const [tema, setTema] = usePreferencia('tema', 'oscura');
  const [modelo, setModelo] = usePreferencia('modelo', 'arkis', leerHash().modelo);
  const [config, setConfig] = useState(null);
  const [error, setError] = useState(null);
  const [salud, setSalud] = useState(null);
  const [token, setToken] = useState(leerToken);

  useEffect(() => { document.documentElement.dataset.theme = tema; }, [tema]);
  useEffect(() => {
    api.get('/api/config').then(setConfig).catch((e) => setError(e.message));
    api.get('/api/salud').then(setSalud).catch(() => {});
  }, []);
  const cambiarToken = (t) => { setToken(t); guardarToken(t.trim()); };

  useEffect(() => {
    const alCambiar = () => {
      const h = leerHash();
      if (h.vista) setVista(h.vista);
      if (h.modelo) setModelo(h.modelo);
    };
    window.addEventListener('hashchange', alCambiar);
    return () => window.removeEventListener('hashchange', alCambiar);
  }, [setVista, setModelo]);
  useEffect(() => {
    const destino = `#/${vista}${['simulador', 'entrenamiento'].includes(vista) ? `/${modelo}` : ''}`;
    if (window.location.hash !== destino) window.history.replaceState(null, '', destino);
  }, [vista, modelo]);

  const ir = (v, m) => { if (m) setModelo(m); setVista(v); };
  const props = { config, tema, modelo, setModelo, ir };

  return (
    <div className="min-h-full">
      <header className="border-b border-line bg-surface/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center gap-3 justify-between">
          <div>
            <div className="font-semibold tracking-tight">IA-SNAKE</div>
            <div className="text-xs text-muted">Laboratorio: cinco metodologías de aprendizaje, un mismo Snake</div>
          </div>
          <nav className="max-w-full"><Segmentado opciones={VISTAS} valor={vista} cambiar={setVista} /></nav>
          <div className="flex items-center gap-2">
            {salud?.requiere_clave && (
              <input type="password" value={token} onChange={(e) => cambiarToken(e.target.value)}
                placeholder="Clave del laboratorio" autoComplete="current-password"
                title="Necesaria para entrenar, editar o exportar. Se guarda solo en este navegador."
                className={`w-44 bg-surface2 border rounded-lg px-2 py-1 text-sm ${token ? 'border-line' : 'border-danger'}`} />
            )}
            <select className="bg-surface2 border border-line rounded-lg px-2 py-1 text-sm" value={tema} onChange={(e) => setTema(e.target.value)}>
              {Object.entries(TEMAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-5 min-w-0">
        {error && (
          <div className="mb-4 text-sm border border-danger/40 bg-danger/10 rounded-xl p-4">
            No hay conexión con el servidor del laboratorio ({error}).{' '}
            {API_URL ? <>Servidor configurado: <code>{API_URL}</code>. Comprueba que está en marcha y que su CORS_ORIGINS incluye este dominio.</>
              : <>En local, arráncalo con <code>npm run dev:all</code>.</>}
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
