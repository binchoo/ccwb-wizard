import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8400,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8450",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
