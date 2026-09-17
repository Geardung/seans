import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    proxy: {
      '/s3': {
        target: 'https://s3.ru1.storage.beget.cloud/e7ad1529f5f1-watchin-mokchin',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/s3/, ''),
      },
    },
  },
})
