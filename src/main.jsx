/* Punto de entrada de React. */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import CookieConsent from './components/CookieConsent';
import { initAnalytics } from './lib/analytics';
import './index.css';

// Registra los scripts de terceros ANTES de pintar. No los carga: solo los deja
// listos para que el gestor de consentimiento los active si el usuario acepta.
initAnalytics();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
    {/* Fuera de App a proposito: el aviso de cookies debe salir aunque la app
        este cargando o sin conexion con el servidor de la IA. */}
    <CookieConsent />
  </StrictMode>,
);
