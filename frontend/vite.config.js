// Vite = the development server and build tool for the frontend.
//   npm run dev    -> live-reloading dev site at http://localhost:5173
//   npm run build  -> optimised files in dist/ (what the Docker image serves)
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api is proxied to the backend so the app works with no CORS setup.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: process.env.VITE_PROXY_TARGET || "http://localhost:8000", changeOrigin: true } },
  },
});
