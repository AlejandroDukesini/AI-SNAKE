/* Escala E0–E8: nivel actual de la partida frente al récord histórico. */
export default function EscalaE({ umbrales, nivel = 0, record = 0, longitud, casillas }) {
  return (
    <div className="space-y-1">
      <div className="grid grid-cols-9 gap-1">
        {umbrales.map((u, n) => {
          const actual = n === nivel;
          const alcanzado = n <= nivel;
          const enRecord = n <= record;
          return (
            <div key={n} title={n === 0 ? 'E0: no alcanzar E1' : `E${n}: ${u} casillas (${(n * 12.5).toFixed(1)} %)`}
              className={`rounded-md border text-center py-1 text-xs tabular-nums
                ${actual ? 'border-accent bg-accent text-on-accent' : alcanzado ? 'border-accent text-accent bg-accent/10' : enRecord ? 'border-snake text-snake' : 'border-line text-muted'}`}>
              <div className="font-semibold">E{n}</div>
              <div className="text-[10px] opacity-80">{n === 0 ? '—' : u}</div>
            </div>
          );
        })}
      </div>
      {longitud !== undefined && (
        <div className="text-xs text-muted">
          Ocupación: {longitud}/{casillas} = {((100 * longitud) / casillas).toFixed(1)} % · relleno = nivel de esta partida · borde verde = récord histórico (E{record})
        </div>
      )}
    </div>
  );
}
