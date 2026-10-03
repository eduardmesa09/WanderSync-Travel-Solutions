import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El .env vive en la raíz del repositorio y lo comparten backend y frontend.
// Vite solo expone al navegador las variables con prefijo VITE_, así que
// DATABASE_URL y demás secretos nunca llegan al bundle.
export default defineConfig({
  plugins: [react()],
  envDir: '..',
  server: {
    port: 5173, // el gateway solo acepta CORS desde http://localhost:5173
    strictPort: true,
  },
})
