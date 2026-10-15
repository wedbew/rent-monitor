import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Browser support (frontend/README.md): the last two stable Chromium, Firefox and Safari majors, iOS Safari and
// Android Chrome. The build target is the oldest of those; raise it when the matrix moves.
const BUILD_TARGET = ["chrome138", "firefox140", "safari18.4", "ios18.4"];

export default defineConfig({
  plugins: [react()],
  server: {
    // The SPA always calls relative `/api` URLs (same origin as in production, behind Caddy). In development
    // the API runs on :8000 (`make up`); override with API_ORIGIN, never with a VITE_* value (those are public).
    proxy: { "/api": { target: process.env["API_ORIGIN"] ?? "http://127.0.0.1:8000", changeOrigin: false } },
  },
  preview: {
    // The journey lane serves the built SPA with `vite preview` next to the real API (e2e/journey).
    proxy: { "/api": { target: process.env["API_ORIGIN"] ?? "http://127.0.0.1:8000", changeOrigin: false } },
  },
  build: { target: BUILD_TARGET, sourcemap: false, cssTarget: BUILD_TARGET },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e/**/*.spec.ts"],
    css: false,
    coverage: {
      provider: "v8",
      include: ["api/**/*.ts"],
      exclude: ["api/**/*.generated.ts", "api/**/*.test.ts"],
      reporter: ["text-summary", "text"],
      thresholds: { lines: 97, functions: 95, branches: 93, statements: 95 },
    },
  },
});
