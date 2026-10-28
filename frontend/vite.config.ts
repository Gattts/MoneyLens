import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  build: {
    rolldownOptions: {
      output: {
        // React num arquivo próprio: mudar o código do app não invalida o cache dele no navegador.
        // As demais bibliotecas ficam com a divisão automática (o Recharts só baixa no balanço anual).
        codeSplitting: {
          groups: [{ name: 'react', test: /node_modules[\\/](react|react-dom|scheduler|react-router)[\\/]/ }],
        },
      },
    },
  },
  server: {
    // Em desenvolvimento, o navegador fala só com o Vite; ele repassa /api para o backend.
    // Assim API e tela ficam na mesma origem e o cookie de sessão funciona sem CORS.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
