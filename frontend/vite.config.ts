import type { IncomingMessage } from "node:http";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Browser support (frontend/README.md): the last two stable Chromium, Firefox and Safari majors, iOS Safari and
// Android Chrome. The build target is the oldest of those; raise it when the matrix moves.
const BUILD_TARGET = ["chrome138", "firefox140", "safari18.4", "ios18.4"];

// The SPA always calls relative `/api` URLs (same origin as in production, behind Caddy). In development the API
// runs on :8000 (`make up`); override with API_ORIGIN, never with a VITE_* value (those are public). Check that
// the process on that port really is RentMonitor (`curl <origin>/openapi.json`, title "RentMonitor"): another
// project may own :8000.
//
// The SPA's own modules live in `frontend/api/*.ts`, so the dev server serves them at `/api/<file>.ts` (also
// with `?t=` or `?import` suffixes): the same prefix. Those requests are bypassed, so Vite serves the source and
// every other `/api` request (the real API has no script extensions) still reaches the backend (#341).
const SCRIPT_MODULE = /\.[cm]?[jt]sx?(?:\?|$)/;
const apiProxy = {
  "/api": {
    target: process.env["API_ORIGIN"] ?? "http://127.0.0.1:8000",
    changeOrigin: false,
    bypass: (req: IncomingMessage) => (SCRIPT_MODULE.test(req.url ?? "") ? req.url : undefined),
  },
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
  // The journey lane serves the built SPA with `vite preview` next to the real API (e2e/journey).
  preview: { proxy: apiProxy },
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
