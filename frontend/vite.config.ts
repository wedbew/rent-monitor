import react from "@vitejs/plugin-react";
import type { ProxyOptions } from "vite";
import { defineConfig } from "vitest/config";

// Browser support (frontend/README.md): the last two stable Chromium, Firefox and Safari majors, iOS Safari and
// Android Chrome. The build target is the oldest of those; raise it when the matrix moves.
const BUILD_TARGET = ["chrome138", "firefox140", "safari18.4", "ios18.4"];

// Vite dev serves source modules (`/api/query.ts`, imported by main.tsx) under the same prefix as the real API, so a
// bare "/api" proxy forwards them to the backend (404, or 502 when it is down). A path ending in a source extension
// stays with Vite; real API routes have none. `vite preview` serves dist/assets and never meets this.
const SOURCE_MODULE = /\.(?:[cm]?[jt]sx?|css|map)$/;

export function apiProxy(target: string): Record<string, ProxyOptions> {
  return {
    "/api": {
      target,
      changeOrigin: false,
      bypass: (req) => (SOURCE_MODULE.test((req.url ?? "").split("?")[0] ?? "") ? req.url : undefined),
    },
  };
}

const API_TARGET = process.env["API_ORIGIN"] ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    // The SPA always calls relative `/api` URLs (same origin as in production, behind Caddy). In development
    // the API runs on :8000 (`make up`); override with API_ORIGIN, never with a VITE_* value (those are public).
    proxy: apiProxy(API_TARGET),
  },
  preview: {
    // The journey lane serves the built SPA with `vite preview` next to the real API (e2e/journey).
    proxy: apiProxy(API_TARGET),
  },
  build: { target: BUILD_TARGET, sourcemap: false, cssTarget: BUILD_TARGET },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules", "dist", "e2e/**/*.spec.ts"],
    css: false,
    // Unit-test coverage of ALL production code, reported per directory (audit F13, #311). The floors are a
    // ratchet at the level measured when they were set: `api/` is the tested seam; `features/` and `ui/` are mostly
    // exercised by the browser suite (e2e interaction gate), which these numbers do NOT include. Raise a floor when
    // a slice raises the number; never lower one to pass.
    coverage: {
      provider: "v8",
      include: ["api/**/*.ts", "shell/**/*.{ts,tsx}", "ui/**/*.{ts,tsx}", "features/**/*.{ts,tsx}"],
      exclude: ["**/*.generated.ts", "**/*.test.{ts,tsx}"],
      reporter: ["text-summary", "text"],
      thresholds: {
        "api/**": { lines: 97, functions: 95, branches: 93, statements: 95 },
        "shell/**": { lines: 70, functions: 66, branches: 60, statements: 70 },
        "ui/**": { lines: 28, functions: 29, branches: 40, statements: 26 },
        "features/**": { lines: 25, functions: 22, branches: 20, statements: 24 },
      },
    },
  },
});
