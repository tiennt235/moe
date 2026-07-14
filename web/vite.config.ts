import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built SPA is emitted into the Python package so `pip install` ships the dashboard.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../src/moe/web_dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // In dev, proxy API calls to the FastAPI backend (moe-dashboard).
      "/api": "http://127.0.0.1:8848",
    },
  },
});
