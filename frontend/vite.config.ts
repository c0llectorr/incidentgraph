import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base URL is not hard-coded in components; Vite proxies /api to the
// backend so the frontend stays provider- and environment-agnostic (PRD §12.8).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
