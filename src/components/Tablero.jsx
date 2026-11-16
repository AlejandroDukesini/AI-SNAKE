/* Tablero. Dibuja lo que envía el servidor; no conoce ninguna regla del juego. */
import { useEffect, useRef } from 'react';

const LADO = 560;

function color(nombre) {
  return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
}

export default function Tablero({ ancho, alto, segmentos = [], manzana, terminada = false, tema, pequeno = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    const celda = LADO / Math.max(ancho, alto);
    ctx.fillStyle = color('--bg');
    ctx.fillRect(0, 0, LADO, LADO);
    ctx.strokeStyle = color('--line');
    ctx.lineWidth = pequeno ? 2 : 1;
    for (let i = 0; i <= ancho; i++) {
      const p = Math.round(i * celda) + 0.5;
      ctx.beginPath(); ctx.moveTo(p, 0); ctx.lineTo(p, alto * celda); ctx.stroke();
    }
    for (let i = 0; i <= alto; i++) {
      const p = Math.round(i * celda) + 0.5;
      ctx.beginPath(); ctx.moveTo(0, p); ctx.lineTo(ancho * celda, p); ctx.stroke();
    }
    const pad = Math.max(2, celda * 0.08);
    const r = Math.min(celda / 3, 8);
    if (manzana) {
      ctx.fillStyle = color('--food');
      ctx.beginPath();
      ctx.roundRect(manzana[0] * celda + pad * 2, manzana[1] * celda + pad * 2, celda - pad * 4, celda - pad * 4, r);
      ctx.fill();
    }
    const n = segmentos.length;
    segmentos.forEach(([x, y], i) => {
      ctx.globalAlpha = terminada ? 0.45 : 1 - (0.45 * i) / Math.max(1, n);
      ctx.fillStyle = i === 0 ? color('--head') : color('--snake');
      ctx.beginPath();
      ctx.roundRect(x * celda + pad, y * celda + pad, celda - pad * 2, celda - pad * 2, r);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
    // Ojos de la cabeza: muestran hacia dónde mira
    if (n >= 1 && !pequeno) {
      const [hx, hy] = segmentos[0];
      ctx.fillStyle = color('--bg');
      const cx = hx * celda + celda / 2; const cy = hy * celda + celda / 2;
      ctx.beginPath(); ctx.arc(cx, cy, Math.max(2, celda * 0.08), 0, Math.PI * 2); ctx.fill();
    }
  }, [ancho, alto, segmentos, manzana, terminada, tema, pequeno]);
  return <canvas ref={ref} width={LADO} height={LADO}
    className={`w-full h-auto block bg-bg ${pequeno ? 'rounded-md border border-line' : 'rounded-panel border border-line'}`} />;
}
