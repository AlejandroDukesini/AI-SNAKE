/* ============================================================================
   Board — el tablero
   ----------------------------------------------------------------------------
   Dibuja el estado que llega del servidor. No conoce ninguna regla: no sabe que
   es una colision ni cuando crece la serpiente. Solo pinta lo que recibe.
   ============================================================================ */

import { useEffect, useRef } from 'react';

const SIZE = 560;   // Lado del canvas en pixeles (el CSS lo escala)

/* Los colores se leen de las variables CSS del tema activo, no se escriben
   aqui: asi el tablero cambia con el tema sin duplicar la paleta en JS. */
function themeColor(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export default function Board({ snake, grid = 8, theme }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const g = snake?.grid ?? grid;
    const cell = SIZE / g;
    const radius = parseInt(themeColor('--radius'), 10) || 0;
    const r = Math.max(0, Math.min(cell / 2 - 2, radius - 4));

    ctx.fillStyle = themeColor('--bg');
    ctx.fillRect(0, 0, SIZE, SIZE);

    // Rejilla
    ctx.strokeStyle = themeColor('--line');
    ctx.lineWidth = 1;
    for (let i = 0; i <= g; i++) {
      const p = Math.round(i * cell) + 0.5;   // +0.5 evita lineas borrosas
      ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, SIZE); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(SIZE, p); ctx.stroke();
    }

    if (!snake) return;

    const pad = Math.max(2, cell * 0.09);

    // Manzana
    if (snake.food) {
      ctx.fillStyle = themeColor('--food');
      ctx.beginPath();
      ctx.roundRect(snake.food[0] * cell + pad * 2, snake.food[1] * cell + pad * 2,
                    cell - pad * 4, cell - pad * 4, r);
      ctx.fill();
    }

    // Cuerpo. La cabeza va aparte para que se vea hacia donde mira; si esta
    // muerta, todo el cuerpo se apaga.
    const cuerpo = snake.alive ? themeColor('--snake') : themeColor('--muted');
    snake.body.forEach(([x, y], i) => {
      ctx.fillStyle = i === 0 && snake.alive ? themeColor('--head') : cuerpo;
      ctx.globalAlpha = snake.alive ? 1 : 0.35;
      ctx.beginPath();
      ctx.roundRect(x * cell + pad, y * cell + pad, cell - pad * 2, cell - pad * 2, r);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    // `theme` es dependencia a proposito: el canvas es un mapa de bits y no
    // hereda las variables CSS, hay que repintarlo cuando cambia el tema.
  }, [snake, grid, theme]);

  return (
    <canvas
      ref={canvasRef}
      width={SIZE}
      height={SIZE}
      className="w-full h-auto block rounded-panel border border-line bg-bg"
    />
  );
}
