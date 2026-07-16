/* ============================================================================
   useSocket — un WebSocket atado al ciclo de vida de un componente
   ----------------------------------------------------------------------------
   Encapsula lo que siempre se olvida y rompe la app:
     - cerrar el socket al desmontar (si no, sigue vivo consumiendo CPU del
       servidor y recibiendo mensajes de una vista que ya no existe);
     - ignorar mensajes que llegan tarde, despues de cerrar;
     - no reconectar en cada render por culpa de una dependencia inestable.

   El callback se guarda en una ref: asi puede cambiar en cada render sin
   provocar una reconexion, que es el bug clasico de los WebSocket en React.
   ============================================================================ */

import { useEffect, useRef, useCallback } from 'react';
import { wsURL } from './api';

export function useSocket(path, onMessage, { enabled = true } = {}) {
  const socketRef = useRef(null);
  const handlerRef = useRef(onMessage);

  // El handler mas reciente, sin que su identidad dispare el efecto.
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!enabled || !path) return undefined;

    const ws = new WebSocket(wsURL(path));
    socketRef.current = ws;
    let vivo = true;

    ws.onmessage = (ev) => {
      if (!vivo) return;
      try {
        handlerRef.current?.(JSON.parse(ev.data));
      } catch {
        /* Un mensaje ilegible no debe tumbar la vista. */
      }
    };

    return () => {
      vivo = false;
      socketRef.current = null;
      // readyState CONNECTING no admite close() limpio: se espera a open.
      if (ws.readyState === WebSocket.OPEN) ws.close();
      else ws.addEventListener('open', () => ws.close());
    };
  }, [path, enabled]);

  const send = useCallback((data) => {
    const ws = socketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  return { send, socketRef };
}
