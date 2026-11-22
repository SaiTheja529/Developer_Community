import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  // Reads .env, .env.local, etc. (all keys, not only VITE_*) so the dev proxy target is configurable.
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env };
  const target = env.DEV_API_TARGET || 'http://localhost:5001';
  const origin = env.DEV_API_ORIGIN || 'http://localhost:5173';
  return {
    plugins: [react(), tailwindcss()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      port: 5173,
      host: 'localhost',
      // Dev only: when VITE_API_BASE_URL is empty the app calls same-origin /api, proxied to Flask.
      // The Origin header is rewritten to one the backend's CORS/CSRF allow-list accepts.
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyReq', (req) => {
              if (req.getHeader('origin')) req.setHeader('origin', origin);
            });
          },
        },
      },
    },
    build: { chunkSizeWarningLimit: 1300 },
  };
});
