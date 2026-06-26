import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs on :8000 in local dev; proxy API calls there so the
// browser talks to a single origin and we avoid CORS in development.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
