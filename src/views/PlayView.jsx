/* ============================================================================
   Jugar Manualmente
   ----------------------------------------------------------------------------
   La partida corre en Python: aqui solo se envian teclas y se dibuja el estado.

   La serpiente arranca DETENIDA. El servidor no la mueve hasta recibir 'start',
   que se envia al acabar la cuenta atras. Sin esa espera perdias antes de poder
   reaccionar.
   ============================================================================ */

import { useCallback, useEffect, useRef, useState } from 'react';
import Board from '../components/Board';
import { Panel, Title, Hint, Stat, Button } from '../components/ui';
import { useSocket } from '../lib/useSocket';

// 3 -> 2 -> 1 a 650 ms cada uno: los ~2 segundos de margen antes de jugar.
const PASOS = ['3', '2', '1'];
const MS_POR_PASO = 650;

// Indices identicos a DIRS en Python: 0=arriba 1=derecha 2=abajo 3=izquierda
const TECLAS = {
  ArrowUp: 0, ArrowRight: 1, ArrowDown: 2, ArrowLeft: 3,
  w: 0, d: 1, s: 2, a: 3, W: 0, D: 1, S: 2, A: 3,
};

export default function PlayView({ theme, grid }) {
  const [snake, setSnake] = useState(null);
  const [cuenta, setCuenta] = useState(null);   // null = no hay cuenta atras
  const [conectado, setConectado] = useState(false);
  const timers = useRef([]);

  const onMessage = useCallback((msg) => {
    if (msg.type === 'state') {
      setSnake(msg.snake);
      setConectado(true);
    }
  }, []);

  const { send } = useSocket('/ws/play', onMessage);

  const limpiarTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  /* Encadena 3, 2, 1 y avisa al servidor. Los timers se guardan para poder
     cancelarlos: sin esto, salir de la vista a mitad de cuenta dispararia un
     'start' sobre un socket ya cerrado. */
  const cuentaAtras = useCallback(() => {
    limpiarTimers();
    PASOS.forEach((paso, i) => {
      timers.current.push(setTimeout(() => setCuenta(paso), i * MS_POR_PASO));
    });
    timers.current.push(setTimeout(() => {
      setCuenta(null);
      send({ action: 'start' });
    }, PASOS.length * MS_POR_PASO));
  }, [send]);

  // Arranca la cuenta en cuanto el socket entrega el primer estado.
  useEffect(() => {
    if (!conectado) return undefined;
    cuentaAtras();
    return limpiarTimers;
  }, [conectado, cuentaAtras]);

  const reiniciar = useCallback(() => {
    send({ action: 'restart' });
    cuentaAtras();
  }, [send, cuentaAtras]);

  // Teclado. Se ignora durante la cuenta atras: el control aun no es tuyo.
  useEffect(() => {
    const onKey = (e) => {
      if (cuenta !== null) return;
      const dir = TECLAS[e.key];
      if (dir !== undefined) {
        e.preventDefault();          // Evita que la pagina haga scroll
        send({ action: 'dir', dir });
      }
      if (e.key === 'r' || e.key === 'R') reiniciar();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [send, cuenta, reiniciar]);

  const muerta = snake && !snake.alive && cuenta === null;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,560px)_1fr] items-start">
      {/* El tablero es cuadrado: si su lado supera el alto util del dispositivo
          se salia por abajo. Se limita el ancho al menor entre el hueco y el
          alto libre de pantalla, y se centra: asi cabe entero en cualquier
          movil (incluido 15x15) y el overlay de la cuenta atras queda alineado. */}
      <div className="relative w-full max-w-[min(100%,calc(100svh-13rem))] mx-auto">
        <Board snake={snake} grid={grid} theme={theme} />

        {cuenta !== null && (
          <div className="absolute inset-0 grid place-items-center rounded-panel
                          bg-bg/80 backdrop-blur-[2px]">
            <div className="text-center">
              {/* key fuerza el remontaje: sin el, la animacion solo correria
                  en el primer numero y el 2 y el 1 apareceria n de golpe. */}
              <div key={cuenta} className="animate-count text-8xl font-bold text-accent tabular-nums">
                {cuenta}
              </div>
              <p className="text-muted mt-3">Prepárate…</p>
            </div>
          </div>
        )}

        {muerta && (
          <div className="absolute inset-0 grid place-items-center rounded-panel
                          bg-bg/85 backdrop-blur-[2px]">
            <div className="text-center">
              <div className="text-3xl font-semibold text-food">Fin de la partida</div>
              <p className="text-muted mt-2 mb-5">
                Creciste hasta {snake.length} bloques · {snake.fruits} manzanas
              </p>
              <Button variant="primary" onClick={reiniciar}>Jugar otra vez</Button>
            </div>
          </div>
        )}
      </div>

      <Panel>
        <Title>Modo manual</Title>
        <Hint className="mt-2 mb-5">
          Muévete con las <b className="text-ink">flechas</b> o <b className="text-ink">WASD</b>.
          Las reglas las aplica Python: el navegador solo dibuja.
        </Hint>

        <div className="grid grid-cols-2 gap-3 mb-5">
          <Stat label="Tamaño" value={snake?.length ?? 3} accent />
          <Stat label="Manzanas" value={snake?.fruits ?? 0} />
        </div>

        {/* Controles tactiles: en movil no hay teclado. */}
        <div className="grid grid-cols-3 gap-2 w-44 mb-5">
          <span />
          <Button onClick={() => send({ action: 'dir', dir: 0 })}>▲</Button>
          <span />
          <Button onClick={() => send({ action: 'dir', dir: 3 })}>◀</Button>
          <Button onClick={() => send({ action: 'dir', dir: 2 })}>▼</Button>
          <Button onClick={() => send({ action: 'dir', dir: 1 })}>▶</Button>
        </div>

        <p className="text-xs text-muted">
          {conectado ? `Conectado · tablero ${snake?.grid ?? grid}×${snake?.grid ?? grid}`
                     : 'Conectando…'}
        </p>
      </Panel>
    </div>
  );
}
