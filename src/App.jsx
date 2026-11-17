/* IA-SNAKE — interfaz del laboratorio. */
import { useCallback, useEffect, useState } from 'react';
import { API_URL, api, esperarServidor, guardarToken, leerToken } from './lib/api';
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
  const [conexion, setConexion] = useState({ estado: 'conectando', segundos: 0 });

  // Arranque: esperar al backend (puede estar despertando) y después cargar la configuración.
  const conectar = useCallback(async () => {
    setError(null);
    if (!(await esperarServidor(setConexion))) return;
    try {
      setConfig(await api.get('/api/config'));
      setSalud(await api.get('/api/salud'));
    } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { conectar(); }, [conectar]);
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
        <EstadoConexion conexion={conexion} error={error} reintentar={conectar} cargando={conexion.estado === 'listo' && !config && !error} />
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

/* Estados de conexión con el backend (arranque en frío incluido). */
function EstadoConexion({ conexion, error, reintentar, cargando }) {
  const { estado, segundos } = conexion;
  if (estado === 'listo' && !error && !cargando) return null;
  const textos = {
    conectando: ['Conectando con el servidor…', 'normal'],
    despertando: [`El servidor está arrancando (${segundos} s). Si estaba inactivo puede tardar hasta un minuto; no hace falta recargar.`, 'normal'],
    no_disponible: ['El servidor no está disponible temporalmente. Inténtalo de nuevo en unos minutos.', 'peligro'],
    tiempo_agotado: ['El servidor no respondió a tiempo.', 'peligro'],
    sin_conexion: ['No se pudo conectar con el servidor.', 'peligro'],
  };
  const [texto, tono] = error ? [`Conectado, pero no se pudo cargar la información: ${error}`, 'peligro']
    : cargando ? ['Cargando información…', 'normal'] : textos[estado] || textos.conectando;
  const final = tono === 'peligro';
  return (
    <div className={`mb-4 text-sm rounded-xl p-4 border ${final ? 'border-danger/40 bg-danger/10' : 'border-line bg-surface'}`} role="status" aria-live="polite">
      <div className="flex flex-wrap items-center gap-3">
        {!final && <span className="inline-block w-3 h-3 rounded-full border-2 border-accent border-t-transparent animate-spin" aria-hidden />}
        <span>{texto}</span>
        {final && <button onClick={reintentar} className="px-3 py-1 rounded-lg border border-line bg-surface2 hover:bg-line">Reintentar</button>}
      </div>
      {final && (
        <div className="mt-2 text-xs text-muted">
          {API_URL ? <>Servidor configurado: <code>{API_URL}</code>. Comprueba que está en marcha y que su CORS_ORIGINS incluye este dominio.</>
            : <>En local, arráncalo con <code>npm run dev:all</code>.</>}
        </div>
      )}
    </div>
  );
}
