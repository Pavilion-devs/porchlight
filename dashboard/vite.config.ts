import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api and /ws go to the backend on :8000. In production the backend serves dist/ itself.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
});
