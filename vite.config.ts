import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: '/watchin-mokchin/',
  server: {
    proxy: {
      '/s3': {
        target: 'https://s3.regru.cloud/watchin-mokchin',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/s3/, ''),
      },
    },
  },
})
