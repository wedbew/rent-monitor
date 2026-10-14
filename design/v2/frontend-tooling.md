# Frontend environment, checks and production workflow

2026-10-15 · Proposed Phase 2 setup, not tooling already installed · See [implementation guide](implementation-guide.md).

## 1. Reproducible setup

At the foundation ticket, inspect any frontend that has landed since this handoff. Choose one supported Node LTS version compatible with **all selected tools**, pin it in the agreed version file and CI, and set `engines`. Do not infer compatibility from Vite alone: current [Vite requirements](https://vite.dev/guide/) and [Vitest requirements](https://vitest.dev/guide/) must both be checked. Verify React/primitives/router/test-runner peer dependencies together.

Recommend pnpm with an exact `packageManager` version and one committed lockfile in the frontend. Reuse an established repository manager if one exists rather than introducing a competing lockfile. CI uses a frozen lockfile; use locally installed CLIs, not unpinned `npx latest` commands. Review dependency lifecycle/build scripts and provenance; document why each runtime dependency is needed. Record selected versions in the foundation PR, not speculative version numbers in this guide.

Node is development/build tooling only; production serves compiled assets through Caddy. Do not run Vite's dev/preview server as production infrastructure.

Do not install Husky, commitlint or a second commit hook chain. Existing repository policy uses prek and its commit-title checks. Add focused frontend checks to that workflow only once real frontend files exist; CI remains authoritative. Keep Python commands under uv and frontend commands under the chosen package manager.

## 2. Tool responsibilities

| Concern | Proposed tool | Configuration intent |
|---|---|---|
| Build/dev | Vite + React plugin | Client SPA; matching dev proxy and production origin assumptions |
| Types | TypeScript | Strict app + configuration typechecks; type generation is separate |
| JS/TS quality | ESLint flat config + typescript-eslint | Typed correctness, React Hooks, accessibility and architectural boundaries |
| Formatting | Prettier | Formatting only; `eslint-config-prettier` resolves overlapping style rules |
| CSS quality | Stylelint + standard config | Catch invalid/duplicate declarations and specificity/cascade mistakes; support CSS Modules deliberately |
| Unit/component tests | Vitest + React Testing Library + user-event | User-visible behavior and adapter logic; explicit DOM environment |
| Network fixtures | MSW | Reuse contract-shaped handlers across tests and component catalog |
| Browser tests | Playwright | User journeys, real browser behavior, accessibility integration and selected visual baselines |
| Component catalog | Storybook | Shared states, variants, interaction and accessibility examples |
| Contract generation | openapi-typescript + openapi-fetch | Blueprint-required generated client boundary |
| Health checks | Bundle analysis, focused dependency checks; later Knip if useful | Size regressions, unused exports/dependencies and supply-chain visibility without duplicate scanners |

Do not run ESLint and Biome on the same responsibility by default. Biome is an alternative worth evaluating if it demonstrably covers the chosen typed/React/accessibility rules, not a second formatting engine to add “more linting”. Use CSS Modules without Tailwind by default; if utility CSS is chosen instead, record why and retain semantic tokens and one ownership model.

Sources: [ESLint flat configuration](https://eslint.org/docs/latest/use/configure/configuration-files), [typescript-eslint presets](https://typescript-eslint.io/users/configs/), [Prettier integration](https://prettier.io/docs/install.html), [Stylelint setup](https://stylelint.io/user-guide/get-started/). Recheck current configuration APIs when implementing; do not paste legacy `.eslintrc` examples into a flat-config setup.

## 3. TypeScript and lint policy

Start with the selected Vite template's compiler/module settings, then enable `strict`, `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`. Use isolated app/node configuration if the toolchain requires it and typecheck both. Verify the selected TypeScript version's options; these flags make missing/indexed/optional values explicit ([TypeScript reference](https://www.typescriptlang.org/tsconfig/types)). Vite compilation is not a substitute for `tsc`.

For ESLint, start with recommended JS, type-checked TypeScript, React Hooks and JSX accessibility presets. Configure typed project discovery explicitly; avoid accidentally type-linting unsupported generated/config files. Add:

- No floating or misused promises; handle async event/clipboard failures deliberately.
- Exhaustive discriminated-union switches for job/payment/analysis states.
- No unexplained explicit `any`, unsafe casts/non-null assertions at API boundaries, or blanket suppression comments.
- No raw untrusted HTML; no debug console statements in production application paths.
- Import restrictions: `ui` cannot import features/API; production cannot import fixtures; features should not reach into another feature's private modules.
- React Hooks dependencies and rules remain enforced. Fix state ownership rather than suppressing a dependency loop.

Use `recommendedTypeChecked` as a workable baseline; adopt stricter presets after measuring friction and documenting exceptions. Enable a rule because it prevents a relevant failure, not to maximize the rule count. Generated schemas are excluded from hand-written style linting but remain typechecked. Every localized suppression explains the reason and, if temporary, the issue to remove it.

Prettier formats TS/TSX/CSS/JSON/Markdown within the frontend scope; it should not churn historical design artifacts or backend files. Keep formatting out of lint logic. Stylelint should know the chosen CSS syntax and allow only specific necessary custom constructs (such as CSS Modules composition), never ignore all unknown properties.

## 4. Proposed script contract

These commands **do not exist yet**. The foundation ticket should implement and verify them before telling contributors to run them. Run from `frontend/` with pnpm; replace only if the manager decision changes.

| Script | Expected behavior |
|---|---|
| `pnpm dev` | Local SPA and `/api` dev proxy; no required remote credentials |
| `pnpm dev:mock` | Explicit isolated mocked environment; mocks cannot load in production |
| `pnpm generate:api` | Generate `api/schema.generated.ts` from `../docs/openapi.json` |
| `pnpm check:api` | Regenerate deterministically and fail on drift; do not silently rewrite the committed baseline in CI |
| `pnpm typecheck` | Check application and tooling configs without emitting application JS |
| `pnpm lint` / `pnpm lint:css` | Quality checks with zero unexplained warnings; no auto-fix in CI |
| `pnpm format:check` / `pnpm format` | Check formatting / explicit developer rewrite |
| `pnpm test` / `pnpm test:watch` | One-shot unit/component suite / interactive watch |
| `pnpm storybook` / `pnpm build:storybook` | Local catalog / static artifact without live customer data |
| `pnpm test:e2e` | Playwright against built app with deterministic mocks or disposable local backend |
| `pnpm test:visual` | Small approved visual suite with motion disabled and fixtures fixed |
| `pnpm build` | Production assets with no embedded private data or mock service worker startup |
| `pnpm preview` | Local inspection of built assets; not a deployment command |
| `pnpm check` | Fast aggregate: schema drift, types, lint, CSS, formatting, unit tests and build |

Use the existing `uv run python scripts/gen_openapi.py` at repo root when an authorized API change updates the schema. Commit schema and generated types together where relevant. Do not fetch a live production schema during build. A formatter-only check must not invoke a network service or provider.

Document commands, expected env names, local backend startup and troubleshooting in the eventual frontend README. Verify them from a clean install in CI; a command that only works in an agent's bundled runtime is not a reproducible project setup.

## 5. Developer experience and local environment

- Define UTF-8, final newlines and consistent whitespace in the existing EditorConfig/contributor conventions; optionally lint changed handoff Markdown after establishing a non-disruptive baseline.
- Add scoped editor recommendations for TypeScript, ESLint, Prettier, Stylelint and Playwright as useful; use workspace versions and format-on-save without changing unrelated repository preferences.
- Provide a short bootstrap: install pinned runtime/manager, frozen install, start local API or mock mode, run dev, run check. Use `.env.example` names only; never read/copy real `.env` values.
- Proxy `/api` through the dev server so browser code always calls relative URLs. Document local secure-cookie behavior and use the repository's supported test-auth mechanism; do not weaken production cookie flags or invent an insecure bypass to get localhost login working.
- Keep a typed mock scenario registry: first visit, empty, loaded, pending, degraded, offline/reconnecting, expired session, insufficient credits and upstream failure. Unknown requests should fail loudly in tests. [MSW documentation](https://mswjs.io/docs/) is the reference for the selected version.
- Mocks are opt-in for development/tests, isolated from production imports/builds. Do not let a missing backend cause silent fallback to successful fixtures.
- Test public environment validation at startup. Build-time values cannot be changed in an already built Vite bundle; document rebuild vs approved runtime-public-config behavior. Public config must never contain provider secrets.
- Keep error messages and sample data Polish-first. Centralize repeated status/error copy, date/number formatting and supported locales; do not introduce a full translation framework before scope requires it.

## 6. Tests that earn their maintenance cost

Use [Testing Library's user-oriented approach](https://testing-library.com/docs/guiding-principles/) and [Playwright locators/isolation](https://playwright.dev/docs/best-practices). Prefer roles, labels and visible actions to CSS structure. Avoid fixed sleeps; wait for the actual state. Use synthetic fixtures, independent test data and no external Otodom, AI or billing calls.

| Layer | Valuable coverage |
|---|---|
| Unit | Form/request adapters, precise display formatting, unknown-vs-zero, URL validation, exhaustive status mapping, draft version handling |
| Component | Label/error wiring, tabs, focus restoration, upload decode/removal, retry boundaries, table sorting/filter state, clipboard fallback |
| Contract | Generated schema drift, handlers matching current shapes, problem-code normalization, unsupported report schema, pagination metadata |
| Browser | Sign-in/session expiry, URL analysis submission → progress → result, duplicate clicks, degraded result, collection back/refresh, mobile navigation |
| Visual | Shell and dense/report/form states at selected widths, both themes, long Polish copy and focus; inspect intentional changes |
| Manual | Keyboard, screen reader, touch, zoom, high contrast/reduced motion, real image sizes and slow network |

Do not test every CSS property or snapshot entire markup trees. Test risky behaviors once at the cheapest reliable level; browser-test a small number of end-to-end journeys. Pure visual refinements need relevant renders rather than artificial unit tests mirroring CSS.

For critical adapters/state machines, establish meaningful coverage and branch cases after baseline measurement; do not invent a universal 100% threshold or weaken existing invariant gates. Fix flaky tests; retries and blanket screenshot tolerances are not a fix. Fix time, timezone, locale, fonts and browser versions for visual CI. Retain traces/screenshots only for a defined short duration because these can contain sensitive information in integration environments.

Chromium is the fast PR lane. Add representative Firefox/WebKit coverage for release/nightly and browser-sensitive changes; headless WebKit is not a replacement for checking a real iOS viewport/keyboard/file picker. Use component accessibility checks and route-level axe checks, plus manual verification. A green accessibility scan is not a compliance certificate.

## 7. CI and hooks

Proposed frontend jobs, added without weakening existing Python/security/invariant jobs:

1. Frozen install with minimal read-only permissions and pinned action commit SHAs.
2. Generated-client drift, TypeScript, ESLint, Stylelint and formatting checks.
3. Unit/component tests and a production build; fail on unexpected console/runtime errors in relevant browser checks.
4. Component catalog build once adopted, browser smoke/journey checks and selected visual/accessibility gates.
5. Publish test reports/artifacts with limited retention and restricted access. No secrets in untrusted PR jobs; no `pull_request_target` for running PR code.

Cache the package store keyed by lockfile/runtime/platform; do not restore a stale `node_modules` tree across incompatible environments. Pin Playwright browsers and OS image for repeatable screenshots. Keep status checks consistent with branch protection; a path-filtered job must not leave a required check permanently pending. Split fast PR gates from slower cross-browser/performance suites explicitly.

Use prek for quick staged-file formatting/lint checks if useful. Do not run the entire browser suite on every keystroke/commit. `pnpm check` should be convenient enough that Claude and humans run it before review. Required repository checks still apply before pushes, including `uv run pytest -m "not e2e"` when the repo requires it.

## 8. Performance, resilience and deployment

Route-split report charts and creative tools; avoid shipping editor/chart/image-processing dependencies to the dashboard unnecessarily. Lazy-load offscreen images, reserve dimensions and cap decode/concurrency. Use thumbnails for grids, not full-resolution uploads. Add virtualization only after profiling and accessibility review; start with honest server pagination.

Track compressed initial JS and route chunks in the production build. Provisional planning budget: initial entry JS at most 200 kB gzip, excluding separately documented lazy chunks. Measure the first real bundle and ratify or revise the budget in the foundation issue; this is not a claimed measurement or existing gate. Explain material regressions rather than raising limits silently.

Aim for good field Core Web Vitals at the 75th percentile: LCP ≤2.5 s, INP ≤200 ms, CLS ≤0.1. Lab tests are diagnostics, not proof of field performance ([Web Vitals](https://web.dev/articles/vitals)). Do not add noisy device-dependent Lighthouse score assertions without a fixed harness and baseline.

Keep route-level error boundaries and retry actions. Handle a stale HTML document referencing removed chunks: coordinate asset retention/cache headers; provide a recoverable reload path without discarding unsaved edits or entering a reload loop. Version HTML and hashed assets coherently. Test direct deep links, refresh, unknown app routes and API errors through Caddy; the SPA fallback must not turn missing `/api` responses into HTML.

Hashed assets can be cached immutably; HTML needs an appropriate revalidation policy. Keep private reports/media out of shared caches and service workers. Do not add offline/PWA persistence by default. Agree CSP, framing policy, referrer handling and source-map access with the existing deployment/security setup; error-monitoring artifacts must not become a public data leak.

Use the existing observability direction rather than adding competing monitoring SDKs. Track safe error categories/request IDs and rendering failures; redact payloads, user notes, image locations and draft text. Respect approved analytics/privacy settings. Verify staged build and rollback behavior with the repository deployment process; no production/customer-data testing from this guide.
