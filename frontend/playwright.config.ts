import { defineConfig, devices } from "@playwright/test";

/**
 * Two lanes, one tool (docs/FRONTEND-PLAN.md section 4):
 *  - mocked (default): the built SPA served by `vite preview`, the API answered from the scenario registry.
 *  - journey (E2E_LANE=journey): the same SPA against a real stack (Compose: API, Postgres, worker, fake
 *    providers); `scripts/e2e_session.py` seeds a session inside the api container.
 * No retries: a flaky test is fixed, not repeated. Fixed locale, time zone, colour scheme and reduced motion keep
 * runs and screenshots reproducible.
 */
const lane = process.env["E2E_LANE"] ?? "mocked"; // mocked | journey | visual | perf | ux
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
    // The interaction gate belongs to the mocked lane; the visual lane only compares pictures.
    ...(lane === "visual" || lane === "perf" || lane === "ux"
      ? []
      : ([["./e2e/coverage-reporter.ts"]] as const)),
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
  // Visual baselines (#334): one directory per project, the same Linux image for comparing and for updating.
  snapshotPathTemplate: "{testDir}/__screenshots__/{projectName}/{arg}{ext}",
  expect: {
    toHaveScreenshot: { animations: "disabled", caret: "hide", scale: "css", maxDiffPixels: 40 },
  },
  projects:
    lane === "perf"
      ? [
          {
            name: "perf-desktop",
            testMatch: "perf.spec.ts",
            use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
          },
          {
            name: "perf-mobile",
            testMatch: "perf.spec.ts",
            use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
          },
        ]
      : lane === "visual"
        ? [
            {
              name: "visual-desktop",
              testMatch: "visual.spec.ts",
              use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
            },
            {
              name: "visual-mobile",
              testMatch: "visual.spec.ts",
              use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
            },
          ]
        : lane === "ux"
          ? [
              {
                name: "ux",
                testMatch: "ux.spec.ts",
                use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
              },
            ]
          : lane === "journey"
            ? [
                {
                  name: "journey",
                  testMatch: "journey/**/*.spec.ts",
                  // QA evidence (docs/QA.md): a trace, a video and a picture of every failed journey, plus the named
                  // `shot()` pictures a journey takes on purpose. All land in test-results/, which CI uploads.
                  use: {
                    ...devices["Desktop Chrome"],
                    viewport: { width: 1280, height: 800 },
                    trace: "retain-on-failure",
                    video: "retain-on-failure",
                    screenshot: "only-on-failure",
                  },
                },
              ]
            : [
                {
                  name: "desktop",
                  testIgnore: ["journey/**", "visual.spec.ts", "perf.spec.ts", "ux.spec.ts"],
                  use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
                },
                {
                  name: "mobile",
                  testIgnore: ["journey/**", "visual.spec.ts", "perf.spec.ts", "ux.spec.ts"],
                  use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
                },
                // Cross-browser lane (audit F13, #311): the same mocked suite in Firefox and WebKit (Safari's engine) at
                // the desktop width. Opt-in with E2E_BROWSERS=all (`pnpm test:e2e:browsers`); nightly on GitHub.
                ...(process.env["E2E_BROWSERS"] === "all"
                  ? [
                      {
                        name: "firefox",
                        testIgnore: ["journey/**", "visual.spec.ts", "perf.spec.ts", "ux.spec.ts"],
                        use: { ...devices["Desktop Firefox"], viewport: { width: 1280, height: 800 } },
                      },
                      {
                        name: "webkit",
                        testIgnore: ["journey/**", "visual.spec.ts", "perf.spec.ts", "ux.spec.ts"],
                        use: { ...devices["Desktop Safari"], viewport: { width: 1280, height: 800 } },
                      },
                    ]
                  : []),
              ],
  webServer: {
    // Both lanes serve the built SPA; the journey lane's preview server also proxies /api to the real API.
    // The mocked lane builds with a test Google client id (a public value) so the Google button renders; e2e/gis.ts
    // replaces the Google script, and with a test Paddle client token (also public) so purchases are offered; e2e/paddle.ts
    // replaces Paddle.js. The journey lane builds with neither: real Google and Paddle are not part of it (the shop is
    // then the honest "not configured" state).
    command: `${lane === "journey" ? "" : "VITE_GOOGLE_CLIENT_ID=test-client.apps.googleusercontent.com VITE_PADDLE_CLIENT_TOKEN=test_fixture_token "}pnpm build && pnpm preview --port ${port} --strictPort`,
    url: baseURL,
    reuseExistingServer: !ci,
    timeout: 120_000,
  },
});
