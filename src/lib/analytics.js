/* ============================================================================
   EJEMPLO — Google Analytics 4 con carga condicionada al consentimiento
   ----------------------------------------------------------------------------
   Este es el patron para CUALQUIER script de terceros: registrarlo en el gestor
   de consentimiento con su categoria y dejar que el sea quien decida cuando (y
   si) cargarlo. Aqui NO se toca el DOM ni se ejecuta gtag directamente: solo se
   declara la intencion. GA se descargara unica y exclusivamente cuando el
   usuario consienta la categoria "analytics".

   El ID de medicion se lee de una variable de entorno de Vite (VITE_GA_ID) para
   no dejarlo escrito en el codigo y poder cambiarlo por entorno. Es un valor de
   configuracion del desarrollador, nunca entrada de usuario: la fuente que se
   inyecta esta siempre controlada.
   ============================================================================ */

import { registerScript } from './consent';

const GA_ID = import.meta.env.VITE_GA_ID;   // p. ej. "G-XXXXXXXXXX"

export function initAnalytics() {
  // Sin ID configurado no se registra nada: en local/dev no cargas GA por error.
  if (!GA_ID) return;

  registerScript({
    id: 'ga4',
    category: 'analytics',
    src: `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_ID)}`,
    attrs: { async: true },
    // Se ejecuta SOLO despues de que el usuario acepte "analytics" y GA cargue.
    onLoad() {
      window.dataLayer = window.dataLayer || [];
      function gtag() { window.dataLayer.push(arguments); }
      window.gtag = gtag;
      gtag('js', new Date());
      gtag('config', GA_ID, {
        anonymize_ip: true,          // minimiza el dato personal (RGPD)
        send_page_view: true,
      });
    },
  });
}

/* ----------------------------------------------------------------------------
   Otros terceros, mismo patron (descomenta y adapta):

   // Meta Pixel  -> categoria "advertising"
   registerScript({
     id: 'meta-pixel',
     category: 'advertising',
     onLoad() {
       // El snippet oficial de Meta, pero disparado SOLO tras consentir.
       // (fbq init aqui, usando la libreria que cargues con otro registerScript
       //  o el snippet inline convertido a esta funcion.)
     },
   });

   // Hotjar  -> categoria "analytics"
   registerScript({
     id: 'hotjar',
     category: 'analytics',
     src: 'https://static.hotjar.com/c/hotjar-XXXXXXX.js?sv=6',
     attrs: { async: true },
   });
   -------------------------------------------------------------------------- */
