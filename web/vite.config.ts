/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

// The SPA always calls /api/*. In dev and `vite preview` Vite proxies it to the FastAPI backend and
// rewrites the refresh cookie's Path (/auth -> /api/auth) so the browser sends it back through the proxy.
// In Docker the nginx container does exactly the same (see nginx.conf). Same-origin => no CORS, and the
// SameSite=Strict refresh cookie just works.
const target = process.env.VITE_PROXY_TARGET ?? "http://127.0.0.1:8000";
const proxy = {
  "/api": {
    target,
    changeOrigin: false,
    rewrite: (p: string) => p.replace(/^\/api/, ""),
    cookiePathRewrite: { "/auth": "/api/auth" },
  },
};

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { sourcemap: false, chunkSizeWarningLimit: 900 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
