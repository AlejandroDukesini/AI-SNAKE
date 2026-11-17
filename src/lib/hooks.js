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
        const t = await api.getSinReintentos(`/api/trabajos/${trabajo.id}`);
        setTrabajo(t);
        if (t.estado !== 'en_curso') ref.current?.(t);
      } catch { /* reintenta en el siguiente tick */ }
    }, 600);
    return () => clearInterval(id);
  }, [trabajo]);
  return [trabajo, setTrabajo];
}

/* Preferencia local de la interfaz (tema, pestaña). Nunca datos de los modelos. */
export function usePreferencia(clave, inicial, forzado) {
  const [v, setV] = useState(() => {
    if (forzado !== undefined && forzado !== null) return forzado;   // p. ej. la URL manda
    try { const g = localStorage.getItem(`ia-snake:${clave}`); return g === null ? inicial : JSON.parse(g); } catch { return inicial; }
  });
  useEffect(() => { try { localStorage.setItem(`ia-snake:${clave}`, JSON.stringify(v)); } catch { /* sin almacenamiento */ } }, [clave, v]);
  return [v, setV];
}
