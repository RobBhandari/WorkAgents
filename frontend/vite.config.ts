import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  const credentials = Buffer.from(
    `${env.API_USERNAME}:${env.API_PASSWORD}`
  ).toString('base64')

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          headers: {
            Authorization: `Basic ${credentials}`,
          },
        },
      },
    },
  }
})
