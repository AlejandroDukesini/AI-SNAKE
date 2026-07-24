/* ============================================================================
   Piezas de interfaz reutilizables
   ----------------------------------------------------------------------------
   Estilo sobrio: mucho aire, bordes suaves, una sola tipografia y un unico
   color de acento. Todos los colores salen de las variables del tema, nunca
   fijos, para que los tres temas funcionen sin tocar los componentes.
   ============================================================================ */

import { useEffect } from 'react';

export function Panel({ children, className = '' }) {
  return (
    <div className={`bg-surface border border-line rounded-panel p-6 ${className}`}>
      {children}
    </div>
  );
}

export function Title({ children, className = '' }) {
  return (
    <h2 className={`text-lg font-semibold tracking-tight text-ink ${className}`}>
      {children}
    </h2>
  );
}

export function Hint({ children, className = '' }) {
  return (
    <p className={`text-sm leading-relaxed text-muted ${className}`}>{children}</p>
  );
}

export function Stat({ label, value, accent = false }) {
  return (
    <div className="bg-surface2 border border-line rounded-xl px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className={`text-2xl font-semibold tabular-nums ${accent ? 'text-accent' : 'text-ink'}`}>
        {value}
      </div>
    </div>
  );
}

/* Insignia del nivel de inteligencia (N0…N5). El nivel lo calcula el servidor a
   partir de la cobertura del tablero (ver plan.txt); aqui solo se pinta. Muestra
   el codigo corto (N2) y, al pasar el raton, la etiqueta completa. */
export function LevelBadge({ nivel, etiqueta, className = '' }) {
  if (nivel === undefined || nivel === null) return null;
  const corto = etiqueta ? etiqueta.split('·')[0].trim() : `N${nivel}`;
  return (
    <span
      title={etiqueta || corto}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border
        border-accent text-accent bg-accent/10 text-xs font-medium ${className}`}
    >
      🧠 {corto}
    </span>
  );
}

const VARIANTES = {
  ghost: 'bg-surface2 text-ink border-line hover:bg-line',
  primary: 'bg-accent text-on-accent border-accent hover:brightness-110 font-medium',
  danger: 'bg-danger text-on-danger border-danger hover:brightness-110 font-medium',
};

export function Button({ variant = 'ghost', className = '', ...props }) {
  return (
    <button
      {...props}
      className={`px-4 py-2.5 rounded-xl border text-sm transition
        active:translate-y-px disabled:opacity-40 disabled:pointer-events-none
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
        ${VARIANTES[variant]} ${className}`}
    />
  );
}

export function IconButton({ label, className = '', ...props }) {
  return (
    <button
      {...props}
      title={label}
      aria-label={label}
      className={`w-9 h-9 grid place-items-center rounded-lg border border-line
        bg-surface2 text-ink text-sm transition hover:bg-accent hover:text-on-accent
        hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2
        focus-visible:outline-accent ${className}`}
    />
  );
}

export function Field({ label, help, children }) {
  return (
    <div className="mb-5">
      {label && <label className="block text-sm text-ink mb-2">{label}</label>}
      {children}
      {help && <p className="text-xs text-muted mt-2 leading-relaxed">{help}</p>}
    </div>
  );
}

/* Deslizador + casilla numérica para el mismo valor. Nace de Configuración, que
   ya usaba esta pareja: el deslizador es cómodo para tantear y el número es la
   única forma de poner un valor exacto sin pelearse con el ratón. Al haber tres
   controles así en Entrenar (agentes, generaciones, herencias) se extrae aquí en
   vez de copiar el marcado cuatro veces. */
export function RangeField({ label, help, value, onChange, min, max, step = 1,
                            disabled = false }) {
  // Un solo manejador para los dos controles: no pueden desincronizarse porque
  // no hay dos estados, solo dos formas de tocar el mismo.
  const cambiar = (e) => onChange(Number(e.target.value));

  return (
    <Field label={label} help={help}>
      <div className="flex items-center gap-4">
        <input
          type="range"
          min={min} max={max} step={step} value={value}
          disabled={disabled}
          onChange={cambiar}
          className="flex-1 accent-accent disabled:opacity-40"
        />
        <input
          type="number"
          min={min} max={max} step={step} value={value}
          disabled={disabled}
          onChange={cambiar}
          className="w-20 bg-surface2 border border-line rounded-xl px-3 py-2
                     text-ink text-center tabular-nums focus:outline-2
                     focus:outline-offset-2 focus:outline-accent
                     disabled:opacity-40"
        />
      </div>
    </Field>
  );
}

/* Interruptor para una opción de sí o no. Es un <button> real con aria-pressed,
   no un div pintado: así funciona con teclado y lo anuncian los lectores de
   pantalla sin trabajo extra. */
export function Toggle({ checked, onChange, label, help, disabled = false }) {
  return (
    <div className="flex items-start justify-between gap-4 bg-surface2 border
                    border-line rounded-xl px-4 py-3 mb-5">
      <div className="min-w-0">
        <div className="text-sm text-ink">{label}</div>
        {help && <p className="text-xs text-muted mt-1 leading-relaxed">{help}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={typeof label === 'string' ? label : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`shrink-0 mt-0.5 w-11 h-6 rounded-full border transition
          disabled:opacity-40 disabled:pointer-events-none
          focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
          ${checked ? 'bg-accent border-accent' : 'bg-surface border-line'}`}
      >
        <span
          className={`block w-4 h-4 rounded-full bg-on-accent transition-transform
            ${checked ? 'translate-x-6' : 'translate-x-1 bg-muted'}`}
        />
      </button>
    </div>
  );
}

export function Empty({ children }) {
  return (
    <div className="border border-dashed border-line rounded-panel py-16 px-6
                    text-center text-muted leading-relaxed">
      {children}
    </div>
  );
}

/* Modal. ESC y el clic en el fondo cierran, que es lo que todo el mundo espera.
   El listener se limpia al desmontar para no acumular uno por apertura. */
export function Modal({ open, onClose, title, children, danger = false }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center
                 justify-center p-5 overflow-y-auto"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        className="animate-modal w-full max-w-md bg-surface border border-line
                   rounded-panel p-6 shadow-2xl"
      >
        <h3 className={`text-lg font-semibold mb-3 ${danger ? 'text-danger' : 'text-ink'}`}>
          {title}
        </h3>
        {children}
      </div>
    </div>
  );
}

/* Segmented control (estilo iOS): la forma mas clara de elegir entre pocas
   opciones excluyentes, como el tamano del tablero. */
export function Segmented({ options, value, onChange }) {
  return (
    <div className="inline-flex p-1 bg-surface2 border border-line rounded-xl gap-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`px-4 py-2 rounded-lg text-sm transition
            ${value === o.value
              ? 'bg-accent text-on-accent font-medium'
              : 'text-muted hover:text-ink'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
