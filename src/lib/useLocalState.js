/* ============================================================================
   useLocalState — useState que sobrevive a un F5
   ----------------------------------------------------------------------------
   Mismo contrato que useState, pero el valor se persiste en localStorage bajo un
   prefijo propio. Se usa para las preferencias de la pantalla de entrenamiento
   (cola de IAs, agentes, herencias): son decisiones del usuario que no aportan
   nada al servidor y que perderlas en cada recarga resultaba molesto.

   POR QUE localStorage Y NO config.json
   -------------------------------------
   `config.json` es estado COMPARTIDO por todos los visitantes (tema, tablero,
   generaciones por defecto). La cola de entrenamiento es lo contrario: una
   decisión de trabajo de ESTA persona en ESTE navegador. Guardarla en el
   servidor haría que dos pestañas se pisaran la selección mutuamente, y obligaría
   a tocar `storage.py` y la API. Aquí no se guarda nada del servidor: solo el
   orden y las casillas marcadas.

   RGPD: cae en la categoría "necesarias" del gestor de consentimiento (estado
   funcional de la propia aplicación, sin datos personales ni terceros), igual
   que el tema elegido. Por eso no pasa por `consent.js`.

   Todo va envuelto en try/catch: en modo privado, con la cuota llena o con el
   almacenamiento bloqueado por politica, localStorage LANZA. Una preferencia que
   no se puede guardar es un incordio; una excepción sin capturar tumbaría la
   vista entera.
   ============================================================================ */

import { useEffect, useState } from 'react';

const PREFIJO = 'snake-ia:';

function leer(clave, inicial) {
  try {
    const crudo = localStorage.getItem(PREFIJO + clave);
    return crudo === null ? inicial : JSON.parse(crudo);
  } catch {
    return inicial;   // Sin almacenamiento (o JSON corrupto) => valor por defecto
  }
}

export function useLocalState(clave, inicial) {
  // Inicializador perezoso: leer localStorage es sincrono y no debe repetirse
  // en cada render, solo en el primero.
  const [valor, setValor] = useState(() => leer(clave, inicial));

  useEffect(() => {
    try {
      localStorage.setItem(PREFIJO + clave, JSON.stringify(valor));
    } catch {
      /* Sin persistencia la app sigue funcionando: solo se olvida al recargar. */
    }
  }, [clave, valor]);

  return [valor, setValor];
}
