/* ============================================================================
   useTrainingQueue — la cola de entrenamiento
   ----------------------------------------------------------------------------
   Toda la lógica de "qué IAs se entrenan y en qué orden", separada de su pintura
   (ver components/AIQueue.jsx). El componente no calcula nada: solo muestra
   `filas` y llama a estas acciones.

   POR QUE UNA COLA Y NO UN ENTRENAMIENTO CONJUNTO
   -----------------------------------------------
   Se podría meter a varias IAs en la misma población y dejar que se cruzaran
   entre ellas. Se descartó a propósito: en este proyecto la CARPETA ES la
   identidad del espécimen, y `storage.rename_model` ya rechaza fusionar dos
   linajes porque eso borra el aprendizaje de uno. Cruzar tres linajes en una
   población haría exactamente ese daño, pero en silencio. La cola entrena a cada
   IA por separado, una detrás de otra, y cada linaje sigue siendo suyo.

   POR QUE EL ORDEN NO VIVE EN EL SERVIDOR
   ---------------------------------------
   `list_models()` ordena por fitness y varias vistas dependen de ese orden. Meter
   un campo `orden` en modelo.json cambiaría la respuesta de /api/models para todo
   el mundo. El orden de la cola es una decisión de trabajo local, así que se
   guarda en el navegador (ver useLocalState) y NO altera ninguna respuesta de la
   API existente.

   La fuente de verdad de QUÉ IAs existen sigue siendo el servidor (`models`).
   Aquí solo se guardan referencias por carpeta, y las que ya no existen se
   ignoran al derivar `filas`: borrar una IA desde el Historial no deja basura.
   ============================================================================ */

import { useCallback, useMemo } from 'react';
import { useLocalState } from './useLocalState';

export function useTrainingQueue(models) {
  const [orden, setOrden] = useLocalState('cola-orden', []);          // [carpeta]
  const [seleccion, setSeleccion] = useLocalState('cola-seleccion', []); // [carpeta]

  /* Las filas a pintar: los modelos del servidor ordenados según la preferencia
     guardada. Lo que está en `orden` va primero y en ese orden; lo que no (una IA
     recién creada) se añade al final tal y como venía del servidor. Así una IA
     nueva aparece siempre, sin necesidad de tocar el orden guardado. */
  const filas = useMemo(() => {
    const porCarpeta = new Map(models.map((m) => [m.carpeta, m]));
    const puestas = new Set();
    const salida = [];

    for (const carpeta of orden) {
      const m = porCarpeta.get(carpeta);
      if (m && !puestas.has(carpeta)) { salida.push(m); puestas.add(carpeta); }
    }
    for (const m of models) {
      if (!puestas.has(m.carpeta)) { salida.push(m); puestas.add(m.carpeta); }
    }

    const marcadas = new Set(seleccion);
    return salida.map((m) => ({ ...m, seleccionada: marcadas.has(m.carpeta) }));
  }, [models, orden, seleccion]);

  /* Las IAs que se van a entrenar, YA en el orden en que se entrenarán. Es lo
     único que consume TrainView: la cola real. */
  const seleccionadas = useMemo(
    () => filas.filter((f) => f.seleccionada),
    [filas],
  );

  /* Guarda el orden completo a partir de una lista de carpetas. Siempre se
     escribe la lista entera y no un "índice movido": así el estado guardado no
     puede quedar desincronizado de lo que se ve. */
  const guardarOrden = useCallback((carpetas) => setOrden(carpetas), [setOrden]);

  /* Mueve una IA `delta` posiciones (−1 arriba, +1 abajo). Silencioso en los
     extremos: pulsar ↑ en la primera no debe hacer nada raro, solo nada. */
  const mover = useCallback((carpeta, delta) => {
    const lista = filas.map((f) => f.carpeta);
    const desde = lista.indexOf(carpeta);
    const hasta = desde + delta;
    if (desde < 0 || hasta < 0 || hasta >= lista.length) return;
    lista.splice(hasta, 0, lista.splice(desde, 1)[0]);
    guardarOrden(lista);
  }, [filas, guardarOrden]);

  /* Suelta `carpeta` en la posición de `destino`. Es lo que usa el drag & drop;
     las flechas ↑↓ son el mismo movimiento expresado con teclado. */
  const soltarSobre = useCallback((carpeta, destino) => {
    if (carpeta === destino) return;
    const lista = filas.map((f) => f.carpeta);
    const desde = lista.indexOf(carpeta);
    const hasta = lista.indexOf(destino);
    if (desde < 0 || hasta < 0) return;
    lista.splice(hasta, 0, lista.splice(desde, 1)[0]);
    guardarOrden(lista);
  }, [filas, guardarOrden]);

  const alternar = useCallback((carpeta) => {
    setSeleccion((s) => (s.includes(carpeta)
      ? s.filter((c) => c !== carpeta)
      : [...s, carpeta]));
  }, [setSeleccion]);

  /* Marcar todas respeta el orden VISIBLE, no el de llegada: si marcas todas,
     la cola se ejecuta en el orden que estás viendo. */
  const marcarTodas = useCallback(() => {
    setSeleccion(filas.map((f) => f.carpeta));
  }, [filas, setSeleccion]);

  const desmarcarTodas = useCallback(() => setSeleccion([]), [setSeleccion]);

  /* Renombrar puede cambiar el slug de la carpeta (es la identidad en disco).
     Sin esto, la IA renombrada perdería su puesto en la cola y su casilla, y
     reaparecería al final como si fuera otra distinta. */
  const renombrada = useCallback((carpetaVieja, carpetaNueva) => {
    if (!carpetaNueva || carpetaVieja === carpetaNueva) return;
    setOrden((o) => o.map((c) => (c === carpetaVieja ? carpetaNueva : c)));
    setSeleccion((s) => s.map((c) => (c === carpetaVieja ? carpetaNueva : c)));
  }, [setOrden, setSeleccion]);

  /* Al borrar se limpia la referencia. `filas` ya la ignoraría por sí sola, pero
     dejarla acumularía carpetas fantasma en localStorage con el tiempo. */
  const olvidar = useCallback((carpeta) => {
    setOrden((o) => o.filter((c) => c !== carpeta));
    setSeleccion((s) => s.filter((c) => c !== carpeta));
  }, [setOrden, setSeleccion]);

  return {
    filas,
    seleccionadas,
    mover,
    soltarSobre,
    alternar,
    marcarTodas,
    desmarcarTodas,
    renombrada,
    olvidar,
  };
}
