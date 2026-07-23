/* ============================================================================
   CookieConsent — banner + panel de personalizacion (RGPD)
   ----------------------------------------------------------------------------
   Solo interfaz: la logica (persistir, decidir que scripts cargar) vive en
   lib/consent.js. Este componente pinta el banner la primera vez y el modal de
   preferencias cuando se pide, y traduce clics en llamadas al nucleo.

   Reutiliza Button y Modal de components/ui.jsx y los colores del tema, asi que
   respeta los tres temas sin una sola linea de estilo fija.
   ============================================================================ */

import { useEffect, useState } from 'react';
import { Button, Modal } from './ui';
import {
  CATEGORIES,
  on,
  getConsent,
  hasDecision,
  acceptAll,
  rejectNonEssential,
  savePreferences,
} from '../lib/consent';

/* Interruptor accesible (role="switch"). Las categorias obligatorias se pintan
   fijas en ON y deshabilitadas: se ve que estan activas y que no se tocan. */
function Toggle({ id, checked, disabled, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative w-11 h-6 rounded-full transition shrink-0
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent
        disabled:opacity-50 disabled:cursor-not-allowed
        ${checked ? 'bg-accent' : 'bg-line'}`}
    >
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow
          transition-transform ${checked ? 'translate-x-5' : 'translate-x-0'}`}
      />
    </button>
  );
}

export default function CookieConsent() {
  // El banner se muestra solo si el usuario aun no ha decidido.
  const [showBanner, setShowBanner] = useState(!hasDecision());
  const [showPrefs, setShowPrefs] = useState(false);
  // Borrador de toggles del modal: arranca de lo ya guardado o de "solo necesarias".
  const [draft, setDraft] = useState(
    () => getConsent()?.categories ??
      Object.fromEntries(CATEGORIES.map((c) => [c.id, !!c.required])),
  );

  // Reaccionar a peticiones externas de abrir el panel (footer, window.CookieConsent.open()).
  useEffect(() => {
    const offOpen = on('open', () => {
      setDraft(getConsent()?.categories ??
        Object.fromEntries(CATEGORIES.map((c) => [c.id, !!c.required])));
      setShowPrefs(true);
    });
    // Si la decision cambia en otra pestana o por reset, refrescar el banner.
    const offChange = on('change', () => setShowBanner(!hasDecision()));
    return () => { offOpen(); offChange(); };
  }, []);

  const cerrarTodo = () => { setShowBanner(false); setShowPrefs(false); };

  const onAceptarTodo = () => { acceptAll(); cerrarTodo(); };
  const onRechazar    = () => { rejectNonEssential(); cerrarTodo(); };
  const onGuardar     = () => { savePreferences(draft); cerrarTodo(); };

  const toggle = (id, value) =>
    setDraft((d) => ({ ...d, [id]: value }));

  return (
    <>
      {/* ---------------- BANNER FLOTANTE ---------------- */}
      {showBanner && (
        <div
          role="dialog"
          aria-live="polite"
          aria-label="Aviso de cookies"
          className="fixed inset-x-0 bottom-0 z-40 p-4 sm:p-5 pointer-events-none"
        >
          <div
            className="pointer-events-auto mx-auto max-w-3xl bg-surface border border-line
                       rounded-panel shadow-2xl p-5 sm:p-6 animate-modal"
          >
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="min-w-0">
                <h2 className="text-base font-semibold text-ink mb-1">🍪 Usamos cookies</h2>
                <p className="text-sm leading-relaxed text-muted">
                  Usamos cookies propias imprescindibles y, con tu permiso, de terceros para
                  analitica, publicidad y preferencias. Puedes aceptarlas, rechazar las no
                  esenciales o elegir por categoria. Cambia tu decision cuando quieras desde
                  el pie de pagina.
                </p>
              </div>

              <div className="flex flex-wrap gap-2 md:flex-nowrap md:shrink-0">
                <Button variant="ghost" onClick={() => setShowPrefs(true)}>
                  Configurar
                </Button>
                <Button variant="ghost" onClick={onRechazar}>
                  Rechazar no esenciales
                </Button>
                <Button variant="primary" onClick={onAceptarTodo}>
                  Aceptar todas
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ---------------- MODAL DE PERSONALIZACION ---------------- */}
      <Modal open={showPrefs} onClose={() => setShowPrefs(false)} title="Preferencias de cookies">
        <p className="text-sm leading-relaxed text-muted mb-5">
          Activa solo las categorias que quieras permitir. Ningun script de terceros se carga
          hasta que lo consientes aqui.
        </p>

        <div className="space-y-3 mb-6">
          {CATEGORIES.map((cat) => (
            <div
              key={cat.id}
              className="flex items-start gap-3 bg-surface2 border border-line rounded-xl p-4"
            >
              <div className="min-w-0 flex-1">
                <label htmlFor={`ck-${cat.id}`} className="text-sm font-medium text-ink">
                  {cat.label}
                  {cat.required && (
                    <span className="ml-2 text-xs text-muted font-normal">(siempre activas)</span>
                  )}
                </label>
                <p className="text-xs text-muted mt-1 leading-relaxed">{cat.desc}</p>
              </div>
              <Toggle
                id={`ck-${cat.id}`}
                checked={cat.required ? true : !!draft[cat.id]}
                disabled={cat.required}
                onChange={(v) => toggle(cat.id, v)}
              />
            </div>
          ))}
        </div>

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={onRechazar}>Rechazar no esenciales</Button>
          <Button variant="ghost" onClick={onAceptarTodo}>Aceptar todas</Button>
          <Button variant="primary" onClick={onGuardar}>Guardar seleccion</Button>
        </div>
      </Modal>
    </>
  );
}
