import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    proxy: {
      '/v4': { target: process.env.V4_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
      '/discover': { target: process.env.V4_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true },
    },
    hmr: {
      overlay: false,
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
