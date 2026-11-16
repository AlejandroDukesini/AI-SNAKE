import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// El frontend llama siempre a través de src/lib/api.js. En desarrollo VITE_API_URL está
// vacía: las rutas /api/... son relativas y este proxy las reenvía al servidor Python
// local. En Netlify/Vercel, VITE_API_URL apunta al backend desplegado (ver
// DOCUMENTACION_DESPLIEGUE_NETLIFY_VERCEL.txt).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
