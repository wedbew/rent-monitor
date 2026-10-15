import { defineConfig, devices } from "@playwright/test";

/**
 * Two lanes, one tool (docs/FRONTEND-PLAN.md section 4):
 *  - mocked (default): the built SPA served by `vite preview`, the API answered from the scenario registry.
 *  - journey (E2E_LANE=journey): the same SPA against a real stack (Compose: API, Postgres, worker, fake
 *    providers); `scripts/e2e_session.py` seeds a session inside the api container.
 * No retries: a flaky test is fixed, not repeated. Fixed locale, time zone, colour scheme and reduced motion keep
 * runs and screenshots reproducible.
 */
const lane = process.env["E2E_LANE"] ?? "mocked";
const port = Number(process.env["E2E_PORT"] ?? 4173);
const baseURL = process.env["E2E_BASE_URL"] ?? `http://localhost:${port}`;
const ci = process.env["CI"] !== undefined;

export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  forbidOnly: ci,
  retries: 0,
  reporter: [
    ["list"],
    ["./e2e/coverage-reporter.ts"],
    ...(ci ? ([["html", { open: "never" }]] as const) : []),
  ],
  outputDir: "test-results",
  use: {
    baseURL,
    locale: "pl-PL",
    timezoneId: "Europe/Warsaw",
    colorScheme: "light",
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  projects:
    lane === "journey"
      ? [
          {
            name: "journey",
            testMatch: "journey/**/*.spec.ts",
            use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
          },
        ]
      : [
          {
            name: "desktop",
            testIgnore: "journey/**",
            use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
          },
          {
            name: "mobile",
            testIgnore: "journey/**",
            use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
          },
          // Cross-browser lane (audit F13, #311): the same mocked suite in Firefox and WebKit (Safari's engine) at
          // the desktop width. Opt-in with E2E_BROWSERS=all (`pnpm test:e2e:browsers`); nightly on GitHub.
          ...(process.env["E2E_BROWSERS"] === "all"
            ? [
                {
                  name: "firefox",
                  testIgnore: "journey/**",
                  use: { ...devices["Desktop Firefox"], viewport: { width: 1280, height: 800 } },
                },
                {
                  name: "webkit",
                  testIgnore: "journey/**",
                  use: { ...devices["Desktop Safari"], viewport: { width: 1280, height: 800 } },
                },
              ]
            : []),
        ],
  webServer: {
    // Both lanes serve the built SPA; the journey lane's preview server also proxies /api to the real API.
    // The mocked lane builds with a test Google client id (a public value) so the Google button renders; e2e/gis.ts
    // replaces the Google script. The journey lane builds without one: real Google is not part of it.
    command: `${lane === "journey" ? "" : "VITE_GOOGLE_CLIENT_ID=test-client.apps.googleusercontent.com "}pnpm build && pnpm preview --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !ci,
    timeout: 120_000,
  },
});
