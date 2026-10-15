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

| Script                              | What it does                                                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `pnpm dev`                          | Vite dev server; `/api` proxied to `API_ORIGIN` (default `http://127.0.0.1:8000`)                                |
| `pnpm generate:api`                 | Regenerate `api/schema.generated.ts` from `../docs/openapi.json`                                                 |
| `pnpm check:api`                    | Fail when the committed types differ from the schema (never rewrites)                                            |
| `pnpm typecheck`                    | `tsc` for the app and for the tooling configs (strict, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`) |
| `pnpm lint` / `pnpm lint:css`       | ESLint (type-checked, React Hooks, a11y) and Stylelint, zero warnings                                            |
| `pnpm format:check` / `pnpm format` | Prettier check / rewrite                                                                                         |
| `pnpm test` / `pnpm test:watch`     | Vitest + Testing Library                                                                                         |
| `pnpm build`                        | Production build into `dist/`                                                                                    |
| `pnpm check:dist`                   | `dist/` contains no mock or test tooling                                                                         |
| `pnpm check`                        | All of the above in order                                                                                        |

Playwright (`test:e2e`, #269), Storybook (#270) and MSW fixtures (#268) are added by their slices.

## Environment

The browser always calls relative `/api` URLs. There are no runtime variables in the bundle yet; **every `VITE_*` value
would be public** (never put a key in one). `API_ORIGIN` only configures the dev proxy and is read by Node, not the app.
Names live in `../.env.example`; real values are never read or committed.

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
