import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // Accept connections from any host header so we can browse the
    // dev site from another device on the LAN (e.g. an iPhone hitting
    // http://<mac-LAN-IP>:5173/). Dev-only — the production bundle is
    // served by the nginx image and doesn't use the Vite dev server.
    allowedHosts: true,
    proxy:
      command === 'serve'
        ? {
            '/api': {
              target: process.env.VITE_API_URL || 'http://localhost:8000',
              changeOrigin: true,
            },
          }
        : undefined,
  },
}));
