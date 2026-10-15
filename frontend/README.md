# renti frontend

Vite + React 19 + TypeScript SPA, served statically by Caddy on the API's origin (blueprint §4.4). Python stays the
only server runtime: Node is a build and test tool here, never production infrastructure. Plan of record:
[`docs/FRONTEND-PLAN.md`](../docs/FRONTEND-PLAN.md); design starting point: [`design/v2/`](../design/v2/).

## Bootstrap

```bash
corepack enable                      # pnpm comes from package.json "packageManager"
nvm install && nvm use               # Node per .node-version (24 LTS); or any manager that reads it
make fe-install                      # pnpm install --frozen-lockfile
make up                              # the API on :8000 (Compose); or point API_ORIGIN at another API
make fe-dev                          # Vite on http://localhost:5173, /api proxied to API_ORIGIN
make fe-check                        # everything CI runs for the SPA
```

`make ci` runs the same stage and reports **SKIPPED** (never passed) when Node or pnpm is missing or the major version
differs from `.node-version`.

## Scripts (run from `frontend/`)

| Script                              | What it does                                                                                                                                                                                                                     |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm dev`                          | Vite dev server; `/api` proxied to `API_ORIGIN` (default `http://127.0.0.1:8000`)                                                                                                                                                |
| `pnpm generate:api`                 | Regenerate `api/schema.generated.ts` (from `../docs/openapi.json`) and `api/report.generated.ts` (from `../docs/deal-analysis.schema.json`)                                                                                      |
| `pnpm check:api`                    | Fail when either committed file differs from its schema (never rewrites)                                                                                                                                                         |
| `pnpm typecheck`                    | `tsc` for the app and for the tooling configs (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`)                                                                                                                 |
| `pnpm lint` / `pnpm lint:css`       | ESLint (type-checked, React Hooks, a11y) and Stylelint, zero warnings                                                                                                                                                            |
| `pnpm format:check` / `pnpm format` | Prettier check / rewrite                                                                                                                                                                                                         |
| `pnpm test` / `pnpm test:watch`     | Vitest + Testing Library; `pnpm test` also enforces the coverage floor on `api/`                                                                                                                                                 |
| `pnpm check:fixtures-vs-samples`    | Local only: every key path of the newest capture exists in a fixture (SKIPPED where `data/` is absent)                                                                                                                           |
| `pnpm test:e2e`                     | Playwright, mocked lane: Chromium at 1280 and 390 px against the built SPA and the scenario registry, axe, the interaction gate; fails the run when a registered interaction or popup was not exercised with an asserted outcome |
| `pnpm test:e2e:journey`             | Playwright, journey lane: the same SPA against the real Compose stack (see below)                                                                                                                                                |
| `pnpm build`                        | Production build into `dist/`                                                                                                                                                                                                    |
| `pnpm check:dist`                   | `dist/` contains no mock or test tooling                                                                                                                                                                                         |
| `pnpm check`                        | All of the above in order                                                                                                                                                                                                        |

Storybook (#270) is added by its slice.

## Environment

The browser always calls relative `/api` URLs. There are no runtime variables in the bundle yet; **every `VITE_*` value
would be public** (never put a key in one). `API_ORIGIN` only configures the dev proxy and is read by Node, not the app.
Names live in `../.env.example`; real values are never read or committed.

## Shell, tokens and primitives (RM-270)

- `styles/tokens.css`: semantic tokens (surfaces, text, boundaries, actions, status, geometry, motion) for the light
  palette and the explicit dark one; `styles/globals.css` is reset, text, focus and the screen-reader utility only.
  Components own CSS Modules next to them. Reduced motion zeroes the motion tokens (no `!important`).
- **Theme**: light on first visit even when the system prefers dark; an explicit choice persists in `localStorage`
  (`renti-theme`); storage failures fall back silently. `public/theme-boot.js` applies it before first paint as an
  external script (no inline-script CSP exception). The control's visible text is its name and names the mode it
  switches to (`Tryb ciemny` / `Tryb jasny`), with the matching moon or sun.
- **Navigation**: `shell/navigation.ts` is the one registry behind the desktop rail and the mobile sheet; each
  destination owns its active rule, so a report under `/app/analyses/:id` lights "Moje analizy" and
  `/app/analyses/new` lights "Nowa analiza". The sheet is a modal dialog that closes first and navigates after, so the
  new page's `h1` gets focus last. After every client navigation the shell focuses that `h1`; every page starts with
  `PageHeading` (title, `h1`, document title `<page> · renti`).
- **Primitives** (`ui/`): `Button`, `IconButton`, `LinkButton` (a real link that looks like a button), `Icon`,
  `InlineNotice`, `Skeleton`, `Dialog` (Base UI). Hover is a stable 1 px border plus a brief icon nudge, never a size
  change. They import nothing from `api/`, `features/` or `shell/` (ESLint).
- **Errors**: `NotFound` and `RouteError` render inside the shell; a stale chunk after a deploy offers a manual reload
  and never reloads by itself.
- Pages that exist in the navigation but are not built use `PendingPage` and say so; Rynek, Architekt wnętrz and Stwórz
  ogłoszenie say "Niedostępne" until their backend exists.
- **Adding a page**: add its route in `routes.tsx`, its entry in `e2e/interactions.ts` (`PAGES`, `INTERACTIONS`,
  `POPUPS`), and tests that `exercise()` each element. The gate fails the run otherwise.

Storybook is deliberately not installed yet: with only these primitives a catalog would be a second set of examples to
keep in sync; the real pages in the e2e gate are the living examples. Revisit when a second feature slice shares
patterns (decision recorded in #270).

## Authentication and the session boundary (RM-271)

- **Routes**: `/login`, `/signup`, `/password/forgot` and the three links the API mails, exactly:
  `/login/email#t=`, `/signup/verify#t=`, `/password/reset#t=`. Signed-out pages use `features/auth/PublicLayout`.
- **Tokens**: `features/auth/token.ts` takes the fragment token once at boot (before React renders), removes it with
  `history.replaceState`, keeps it in memory only and spends it exactly once. It is never in storage, a URL, a query
  key, analytics or error tracking.
- **Session**: `shell/session.tsx` holds one query (`GET /api/me`; a 401 is "signed out", not a failure). `/app/*` sits
  behind `RequireSession` (signed out: sign-in, then back to where you were; `next` accepts in-app paths only).
  Signing out, a 401 `UNAUTHENTICATED` from any request, or a sign-out in another tab (BroadcastChannel, `storage`
  event fallback; only a signal travels) runs `endSession`: tenant cleanups (streams, object URLs register with
  `shell/tenant.ts`), every cache entry dropped, signed-out state shown. No token or session id exists in storage:
  the session is an HttpOnly cookie the page cannot read.
- **Google**: Google Identity Services in callback mode (`features/auth/gis.ts`); the button renders only when
  `VITE_GOOGLE_CLIENT_ID` is set at build time (a public value, same as the server's `GOOGLE_CLIENT_ID`); if the script
  is blocked a notice points to the e-mail methods. `GOOGLE_EMAIL_UNVERIFIED` and `EMAIL_CONFIRMATION_REQUIRED` lead to
  the e-mail link. The e2e lanes use a stand-in for Google's script (`e2e/gis.ts`); real Google is unverified (L-029).
- **Forms**: `ui/Field.tsx` (label, hint, textual error, `aria-describedby`) and `ui/FormErrors.tsx` (an error summary
  that takes focus after a failed submit and links to each field). Values survive failures; client checks mirror the
  server's rules but the server is authoritative (422 and `WEAK_PASSWORD` reasons map onto fields).

## End-to-end tests (`e2e/`)

"Every page, popup and clickable element has an e2e test" is a gate, not a habit (docs/FRONTEND-PLAN.md section 4).

- `e2e/interactions.ts` is the registry: `PAGES` (path, `h1`, the API scenarios to inventory it in), `INTERACTIONS`
  (`{id, page, role, name, outcome}`) and `POPUPS` (trigger, role, name, backdrop policy). A slice adds its page,
  its elements and its tests in the same PR.
- A page can also list **states** (`PageState`): an error summary, a "link sent" confirmation, a banner. The
  inventory drives the real UI there (`prepare`) and inventories the state too; elements only present in a state are
  registered with `state`. Pages in the signed-out frame use `layout: "public"` and the `public:*` shared elements.
- `inventory.spec.ts` visits every page in every listed scenario, opens every popup, lists every visible element with an
  interactive ARIA role (from the browser's own accessibility tree) and **fails on one that has no accessible name or is
  not registered**, and on a registered one that is gone. axe runs on every state.
- A test counts an element as covered only through `exercise(id, run)`: `run` must return an `outcome.*` token
  (`url`, `request`, `dialog`, `focus`, `text`, `state`), each of which makes a real assertion, and the token kind must
  match what the registry promises. `coverage-reporter.ts` fails the run when anything registered was not exercised.
- `expectDialogContract` is the popup contract: opens from the keyboard, focus moves in and stays (modal), Escape
  closes, focus returns to the trigger, the dialog has a name, the backdrop follows the registered policy.
- `gate.spec.ts` and `gate.test.ts` test the gate itself on synthetic pages, so a broken gate cannot pass silently.
- A test also fails on any console error or uncaught page error, and on any API request the scenario has no route for
  (`e2e/fixtures.ts`). No retries and no `waitForTimeout` (linted).

## New analysis and progress (RM-273)

- `features/analyses/new/` is the form (`LEGAL[url-analysis]`): client validation is only "not empty, at most 300
  characters"; the API decides what an Otodom sale listing is. `useCreateAudit` never retries. After a transport failure
  that proves nothing (dropped connection, timeout) `reconcileAfterAmbiguousFailure` looks for an analysis of the same
  Otodom id created since the click; nothing else counts as proof and an empty or unreadable list is "unknown".
- `features/analyses/progress/`: `streams.ts` owns one `EventSource` per analysis (shared, replays what it has seen to
  a late watcher, deduplicates by event id, closes on the terminal frame and on `runTenantCleanups`); `frames.ts`
  parses defensively; `useAuditProgress` copies stage and percentage, never computes them. A server `error` event and
  the connection's own `error` event are different things (`MessageEvent` or not).
- `AnalysisPage` reads `GET /api/audits/{id}` first (a remount cannot resume a stream), opens the stream only for an
  active analysis, and keeps polling as a safety net: 10 s always, 3 s when the stream failed or kept reconnecting for
  8 s. A read that shows the analysis finished refreshes the balance (`refreshBalance`, never from inside the audit query's
  own invalidation).
- Scenarios: `createRun({outcome, interrupt, streamDown, silent, post, postDelayMs, listAfterPost, listFails})` is one
  analysis from click to end with a stateful balance, audit and stream.

## The report (RM-274)

- `features/analyses/report/ReportView.tsx` renders a `DealAnalysis` (version 1 only; `api/report.ts` decides: unsupported
  or incomplete results get a safe notice and no values). Every figure is the engine's decimal string passed to
  `api/format.ts`; the only things derived on the client are wording (`discountSentence` strips a sign) and lists.
  A `null` is "nie obliczono" in italics, a zero stays "0,00 zł".
- `copy.ts` and `warnings.ts` are exhaustive maps of the engine's vocabularies (verdict, grade, condition, title form,
  warning codes); an unknown warning code is still shown. `ui/Accordion.tsx` (`DisclosureGroup`, Base UI) holds the
  details; several can be open.
- Listing photos are not displayed (third-party images; counts only). `LEGAL[republication]` is on `SourceSection`.
- Scenarios: `unsupportedReport`, `invalidReport`, `richReport` patch the stored result of the first captured audit.

## Analyses collection (RM-275)

- `/app/analyses` displays the API's newest-first collection as cards or a native table. View, status group, grade
  and Otodom-id-prefix search live in the URL; Back and reload restore them.
- `features/analyses/list/useAuditList.ts` requests server-cursor pages of 24 and follows `next_cursor`; no client-side
  slicing or inferred total. Repeated ids are rendered once, and a failed next page keeps the existing rows.
- First visit, filtered-empty, loading, refreshing-with-results and errors have separate states. The table has a
  caption, row/column headers and its own labelled keyboard-focusable horizontal scroll region at 320 px.
- `e2e/analyses.spec.ts` covers 120 audits, cursor exhaustion, duplicate rows, filters/history, both views, errors and
  table reflow/focus. Browser inventory/axe includes light and dark collection scenarios; journey tests verify the
  real API's newly created analyses can be opened from the collection using fake provider data.

### Journey lane

The same SPA against a real stack: API, Postgres, workers and fake providers. The session is seeded **inside the api
container** by `scripts/e2e_session.py` (a synthetic user and a real session row; no HTTP bypass, no test route).

```bash
# Apple Silicon: DOCKER_DEFAULT_PLATFORM=linux/amd64 (L-021); POSTGRES_PORT=55432 if 5432 is taken
docker compose -f deploy/compose.yml -f deploy/compose.e2e.yml up -d --build --wait api worker-audit worker-ops
pnpm test:e2e:journey          # builds the SPA, serves it with `vite preview` (port 4173, /api proxied to :8000)
```

`deploy/compose.e2e.yml` sets `PUBLIC_APP_URL=http://localhost:4173` so the API's Origin check and Secure cookies behave
as in production. Override the compose command with `E2E_COMPOSE`. `scripts/e2e_session.py plant-listing --kind sale|rent` plants a hand-built, fresh listing (and rental comparables in a
made-up city) so the worker makes no Otodom request; `deploy/compose.e2e.yml` gives the audit worker
`AUDIT_PROVIDERS=real` and a test `RISK_FREE_RATE`. Evidence class: fake provider data; there is no OpenRouter key,
so a success is `succeeded_degraded`. The interaction gate counts the mocked lane; the journey lane runs the whole sign-up (register, mailed link via `register-token`, sign out, sign in);
journeys are the few paths worth running against the real thing. The GitHub lanes (PR, nightly Firefox and WebKit)
are the follow-up issue #296 because they edit `.github/`.

## API seam (`api/`)

- `client.ts`: the one `openapi-fetch` client (`createApi`), relative `/api` URLs, a 15 s deadline on every request.
  `unwrap()` turns an error status into `ApiError` (RFC 9457 `Problem`, `code`, `request_id`, `Retry-After`) and a
  dropped connection, timeout or abort into `TransportError`.
- `problems.ts`: Polish title, detail and next action for **every** problem code (exhaustive: a new API code is a
  compile error and a failing test), plus the transport failures. Where a failure releases the credit, the text says so.
- `format.ts`: the only place numbers become text. Money, areas and rates arrive as decimal strings and are formatted
  by integer arithmetic (no `Number`, no `parseFloat`; both are linted). `null` is "nie obliczono", never `0`. Dates in
  Europe/Warsaw, pl-PL numbers, Polish plurals.
- `query.ts`: TanStack Query defaults. Mutations are never retried; reads retry at most twice, only on network errors,
  timeouts and 5xx; `staleTime` 30 s; `clearTenantState` empties the cache on sign-out.
- `report.ts`: `parseReport` renders a known `schema_version` and says "unsupported" otherwise.

## Fixtures and scenarios (`test/`)

`test/fixtures/` are sanitised API answers derived from a local capture by `make fe-fixtures`
(`scripts/derive_ui_fixtures.py`; synthetic ids, emails, names, text, URLs and times; shapes and nullability kept).
`test/scenarios.ts` is the typed registry the screens are built and tested against: `firstVisit`, `empty`, `loaded`
(five distinct audits), `pending`, `degraded`, `rejectedRent`, `rejectedFractional`, `failedUpstream`, `failedInput`,
`insufficientCredits`, `breakerOpen`, `billingDisabled`, `sessionExpired`, `offline`, `reconnecting`. Scenarios are
plain data: `test/handlers.ts` serves them with MSW in Vitest (`useScenario("loaded")`) and the Playwright lane (#269)
reads the same registry. A request no route matches answers 599 and fails the test. `test/contract.ts` validates every
fixture against `docs/openapi.json`.

## Layout

Flat, per `.agent/rules/repo-layout.md`: no `src/`. Add a directory only when it has several real files.
`api/` (generated types and, from #268, the client), `styles/`, `test/` (setup), and later `ui/`, `shell/`,
`features/`, `e2e/`. `ui/` imports neither `api/`, `features/` nor `shell/`; production code imports no test tooling,
mock or fixture (both enforced by ESLint).

## Decisions (RM-267, 2026-10-15)

| Choice                                                      | Version                                                          | Why                                                                                         |
| ----------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Node                                                        | 24.22.0 (active LTS "Krypton")                                   | React Router 8 needs Node >= 22.22, jsdom 30 the same; Node 22 is in maintenance            |
| pnpm                                                        | 12.11.2 via `packageManager`                                     | frozen lockfile, build scripts of dependencies blocked by default (none are allowed)        |
| Vite + `@vitejs/plugin-react`                               | 8.3.4 / 6.1.2                                                    | build and dev server; plugin v6 requires Vite 8                                             |
| React, React DOM                                            | 19.3                                                             | blueprint; Base UI needs >= 19.2.7                                                          |
| React Router                                                | 8.4.0, library mode (`createBrowserRouter`)                      | client-only routing, no server runtime                                                      |
| TanStack Query                                              | 5.104                                                            | the one server-state cache                                                                  |
| openapi-typescript / openapi-fetch                          | 7.13 / 0.17                                                      | blueprint-required generated client boundary                                                |
| TypeScript                                                  | ~6.0.3                                                           | typescript-eslint 8.71 supports `<6.1`; TypeScript 7 is not yet supported by the lint stack |
| ESLint 10 + typescript-eslint 8.71, react-hooks 7, jsx-a11y |                                                                  | typed correctness, hooks, accessibility, import and HTML-sink bans                          |
| Prettier 3.9, Stylelint 17 + standard                       |                                                                  | formatting only / CSS correctness and no `!important`                                       |
| Vitest 5, Testing Library, jsdom 30                         |                                                                  | unit and component tests                                                                    |
| Base UI                                                     | 1.9.0 (**recorded, installed with the first primitive in #270**) | headless dialogs, tabs, menus; no unused dependency until then                              |

Initial entry bundle: **106 kB gzip** (React, Router, Query). The provisional budget of 200 kB gzip for the entry
chunk is ratified here and enforced in #286.

## Browser support

The last two stable majors of Chromium, Firefox and Safari, iOS Safari and Android Chrome. The build target is the
oldest of them (`vite.config.ts`: chrome138, firefox140, safari18.4, ios18.4); raise it when the matrix moves. No
offline or PWA support.

## Troubleshooting

- `ERR_PNPM_UNSUPPORTED_ENGINE`: your Node is not 24.x; `nvm use` in `frontend/`.
- `pnpm check:api` fails after an API change: `uv run python scripts/gen_openapi.py`, then `pnpm generate:api`, commit both.
- Login on localhost: session cookies are `Secure`; use the repository's test-session mechanism (#269), not a bypass.
- A dependency install script is blocked: that is the default. Do not allow-list one without a reason in the PR.
