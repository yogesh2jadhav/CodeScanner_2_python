/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The dev server proxies /api to FastAPI so the browser sees one origin (no CORS
// setup needed in development). Override the target with VITE_API_PROXY_TARGET.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), tailwindcss()],
    build: { chunkSizeWarningLimit: 1200 },
    server: {
      port: 5173,
      proxy: {
        "/api": { target: env.VITE_API_PROXY_TARGET || "http://localhost:8000", changeOrigin: true },
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
    },
  };
});
