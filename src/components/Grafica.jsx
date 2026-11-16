/* Gráfica de líneas mínima en SVG (curvas de aprendizaje). */
export default function Grafica({ series, alto = 160, etiquetaX = 'episodio' }) {
  const todos = series.flatMap((s) => s.puntos);
  if (todos.length < 2) return <div className="text-xs text-muted">Aún no hay suficientes datos.</div>;
  const xs = todos.map((p) => p[0]); const ys = todos.map((p) => p[1]);
  const x0 = Math.min(...xs); const x1 = Math.max(...xs);
  const y0 = Math.min(0, ...ys); const y1 = Math.max(...ys, 1);
  const W = 600; const H = alto; const m = 28;
  const px = (x) => m + ((x - x0) / Math.max(1, x1 - x0)) * (W - m - 6);
  const py = (y) => H - 18 - ((y - y0) / Math.max(1e-9, y1 - y0)) * (H - 26);
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
        <line x1={m} y1={py(y0)} x2={W} y2={py(y0)} stroke="var(--line)" />
        <text x={2} y={py(y1) + 4} fontSize="10" fill="var(--muted)">{y1.toFixed(1)}</text>
        <text x={2} y={py(y0)} fontSize="10" fill="var(--muted)">{y0.toFixed(1)}</text>
        <text x={W - 4} y={H - 4} fontSize="10" fill="var(--muted)" textAnchor="end">{etiquetaX} {x1}</text>
        {series.map((s) => (
          <polyline key={s.nombre} fill="none" stroke={s.color} strokeWidth={s.grosor || 1.5}
            opacity={s.opacidad || 1} points={s.puntos.map(([x, y]) => `${px(x)},${py(y)}`).join(' ')} />
        ))}
      </svg>
      <div className="flex flex-wrap gap-3 text-xs text-muted">
        {series.map((s) => <span key={s.nombre}><span className="inline-block w-3 h-0.5 align-middle mr-1" style={{ background: s.color }} />{s.nombre}</span>)}
      </div>
    </div>
  );
}

export function mediaMovil(valores, k = 20) {
  const out = [];
  let suma = 0;
  valores.forEach((v, i) => {
    suma += v;
    if (i >= k) suma -= valores[i - k];
    out.push(suma / Math.min(i + 1, k));
  });
  return out;
}
