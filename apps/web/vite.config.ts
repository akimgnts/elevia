import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const API_TARGET = process.env.VITE_API_BASE_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 3001,       // fixed — use `make dev-up` or `make web`
    strictPort: true, // fail hard if 3001 is taken — never silently shift to 5173
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        ws: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/dev": {
        target: API_TARGET,
        changeOrigin: true,
        bypass: (req) => {
          if (req.method === "GET") {
            return "/index.html";
          }
          return undefined;
        },
      },
      "/v1": { target: API_TARGET, changeOrigin: true },
      "/debug": { target: API_TARGET, changeOrigin: true },
      "/profile": { target: API_TARGET, changeOrigin: true },
      "/offers": { target: API_TARGET, changeOrigin: true },
      "/context": { target: API_TARGET, changeOrigin: true },
      "/inbox": { target: API_TARGET, changeOrigin: true },
      "/metrics": { target: API_TARGET, changeOrigin: true },
      "/apply-pack": { target: API_TARGET, changeOrigin: true },
      "/applications": { target: API_TARGET, changeOrigin: true },
      "/health": { target: API_TARGET, changeOrigin: true },
      "/documents": { target: API_TARGET, changeOrigin: true },
      "/analyze": { target: API_TARGET, changeOrigin: true },
    },
  },
});
