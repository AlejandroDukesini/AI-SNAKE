import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// El frontend usa SIEMPRE rutas relativas (/api/..., /ws/...). En desarrollo
// este proxy las reenvia al servidor de Python; en produccion es ese mismo
// servidor quien sirve la web, asi que las rutas ya apuntan a el. Resultado:
// cero URLs escritas a mano en el codigo React y el mismo build vale en ambos.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws':  { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
