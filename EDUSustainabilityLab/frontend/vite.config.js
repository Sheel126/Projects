import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react-swc'

// https://vitejs.dev/config/
export default ({mode}) => {
  
  process.env = {...process.env, ...loadEnv(mode, process.cwd())};
  
  return defineConfig({
    plugins: [react()],
    server: {
      host: '0.0.0.0',  
      port: parseInt(process.env.FRONTEND_PORT),        
    },
    preview: {
      port: 3001,
    },

    watch: {
      usePolling: true, 
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/tests/setup.js',
      coverage: {
        provider: 'istanbul',
        reporter: ['text', 'json', 'html']
      }
    },
    define: {
      'process.env': process.env
    },
  })
}
