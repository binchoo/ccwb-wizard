import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite 설정 - React 플러그인만 활성화. 기본 포트 5173.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    open: false,
  },
});
