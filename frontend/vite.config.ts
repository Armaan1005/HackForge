import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The FastAPI backend (engine /api + genai /api/ai) runs on :8000 and is proxied, so no CORS in dev.
// host: true exposes the dev server on the LAN so a judge's phone can open /challenge from the QR code.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
    fs: { allow: ['..'] } // fixtures are imported from ../contracts
  }
});
