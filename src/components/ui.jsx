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
