import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
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
