import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';

/* Carga una ruta y permite recargarla. */
export function useDatos(ruta, deps = []) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState(null);
  const recargar = useCallback(async () => {
    if (!ruta) return;
    try { setDatos(await api.get(ruta)); setError(null); } catch (e) { setError(e.message); }
  }, [ruta]);
  useEffect(() => { recargar(); }, [recargar, ...deps]);
  return [datos, recargar, error];
}

/* Sigue un trabajo en segundo plano hasta que termina. */
export function useTrabajo(alTerminar) {
  const [trabajo, setTrabajo] = useState(null);
  const ref = useRef(alTerminar);
  ref.current = alTerminar;
  useEffect(() => {
    if (!trabajo || trabajo.estado !== 'en_curso') return undefined;
    const id = setInterval(async () => {
      try {
        const t = await api.get(`/api/trabajos/${trabajo.id}`);
        setTrabajo(t);
        if (t.estado !== 'en_curso') ref.current?.(t);
      } catch { /* reintenta en el siguiente tick */ }
    }, 600);
    return () => clearInterval(id);
  }, [trabajo]);
  return [trabajo, setTrabajo];
}

/* Preferencia local de la interfaz (tema, pestaña). Nunca datos de los modelos. */
export function usePreferencia(clave, inicial) {
  const [v, setV] = useState(() => {
    try { const g = localStorage.getItem(`arkis:${clave}`); return g === null ? inicial : JSON.parse(g); } catch { return inicial; }
  });
  useEffect(() => { try { localStorage.setItem(`arkis:${clave}`, JSON.stringify(v)); } catch { /* sin almacenamiento */ } }, [clave, v]);
  return [v, setV];
}
