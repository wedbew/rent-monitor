# Frontend delivery plan

**Status:** plan of record for Phase 2 (owner request, 2026-10-15, #262). Implementation has not started; Phase 1 still
forbids `frontend/` until the owner authorises Phase 2 in #267 (FE-01). Delivery state stays in [`STATUS.md`](STATUS.md).

Inputs: the V2 handoff ([implementation guide](../design/v2/implementation-guide.md), [design system](../design/v2/design-system.md),
[tooling](../design/v2/frontend-tooling.md), [checklist](../design/v2/implementation-checklist.md)), [`BLUEPRINT.md`](BLUEPRINT.md)
§2 and §4.8 step 6, `docs/openapi.json`, and the API code on `staging` `f27257b`.

Owner direction this plan implements:

1. The frontend is built **after** an API smoke test that exercises every endpoint and keeps real response samples in
   `data/` (gitignored, never pushed). The UI is designed from those samples.
2. Every data view renders **at least 5 different examples**.
3. Every page, popup and clickable element has an **e2e test that runs autonomously** (CI, no human step).
4. The plan is checked a second time against the production-ready bar (§7).

## 1. Verification of the V2 handoff

Method: every factual claim in the four files was checked against the code, OpenAPI and blueprint on 2026-10-15.
*Confirmed* = read in source; *inferred* = conclusion not proven by a run.

| Claim in the handoff | Verdict | Evidence | Action |
| --- | --- | --- | --- |
| No `frontend/` exists; blueprint's "keep the existing SPA" is stale | confirmed | no `frontend/` in the checkout | Blueprint executive verdict, §4.1 and §4.4 corrected |
| `AuditCreate` takes only `listing_ref`, `lang`, `analyst`; no manual form or images | confirmed | `packages/rm_contracts/audits.py` | kept; manual analysis is #283 (FE-17) |
| `GET /api/audits` is a capped array (`limit` ≤ 100), no cursor/filter | confirmed | `services/rm_api/audits.py:172` | #265 (FE-A2) |
| `AuditOut.result` is an opaque object | confirmed | OpenAPI `additionalProperties: true` | #266 (FE-A3) publishes the `DealAnalysis` schema |
| SSE resumes only by the `Last-Event-ID` header; no query-parameter resume | confirmed | `services/rm_api/audits.py:208` | kept |
| `POST /api/audits/{id}/cancel` should not be shown as working | confirmed: the route does not exist (blueprint route map lists it) | OpenAPI has 36 operations, no cancel | no cancel button (#273) |
| Money arrives as strings | confirmed | OpenAPI `asking_price_pln: string \| null` | one formatter, ESLint ban on `Number()` (#268) |
| CSP has no inline scripts, so the theme bootstrap must be an external file | confirmed | blueprint §4.3 Caddyfile | kept (#270) |
| Pulpit lacks a "credit contract" | **wrong**: `GET /api/me` returns `credit_balance`, `flags`, `upstream` breaker state | `packages/rm_contracts/me.py` `MeDetailOut` | Pulpit uses it (#272) |
| Ustawienia is a placeholder "until explicit contracts" | **wrong**: sessions, sign-out-everywhere, password change, data export and account deletion all exist | OpenAPI `/api/auth/sessions`, `/api/me/export`, `DELETE /api/me` | #278 (FE-12) |
| "Substantially more market data exists" for Rynek | **partly**: data exists in Postgres, but **no `/api/market/*` route exists** | OpenAPI; #21 open | Rynek blocked on #21 (#282) |
| Page map covers the product | **incomplete**: no sign-in/sign-up pages, no email-link routes the API already sends (`/login/email#t=`, `/signup/verify#t=`, `/password/reset#t=`), no billing (`/pay` page Paddle needs), no saved listings | `services/rm_api/auth/router.py:124`, `auth/password.py:130,312`, `PADDLE-INTEGRATION.md` §5 | #271, #277, #276 |
| Problem responses are typed by the generated client | **wrong**: OpenAPI has no problem schema and advertises `HTTPValidationError` for 422, while the API answers `application/problem+json` | `docs/openapi.json` components; `services/rm_api/problems.py:138` | L-027, #264 (FE-A1) |
| Billing: use the Paddle spec, not Stripe screens | confirmed; also the blueprint CSP still allows only Stripe frames | blueprint §4.3 | CSP fixed in #281 |
| Tooling: pnpm, Vitest, Playwright, MSW, Storybook, ESLint/Prettier/Stylelint, prek not Husky | sound; consistent with TOOLCHAIN (prek, no Node in backend tooling) | `docs/TOOLCHAIN.md:21,119` | versions decided in #267 |
| Node "choose an LTS" vs blueprint "Node 22 LTS" | conflict; Node 22 is in maintenance, the active LTS is newer *(inferred from the Node release schedule; verify in #267)* | blueprint §4.4 | blueprint now says "active LTS pinned in `frontend/.node-version`" |
| Blueprint bootstrap `npx … -o src/api/schema.d.ts` | conflicts with the flat-layout rule and the "no unpinned npx" rule | `.agent/rules/repo-layout.md` | blueprint §4.4 corrected |
| pytest marker `e2e` | means "talks to Stripe test mode"; a browser e2e suite must not reuse it | `pyproject.toml:78` | Playwright lanes are separate (#269) |

Worth keeping: the four-layer component model, state-ownership table, contract-first adapters, honest states, SSE
lifecycle rules, the no-client-finance boundary, the media and AI-tool cautions. They match the blueprint and the
production bar. Not worth adding yet: Storybook before the first primitives exist (start it with #270, not #267),
virtualisation, a translation framework, offline/PWA.

## 2. Order

```
#263 FE-00 API smoke + samples ─┬─> #267 FE-01 foundation (owner: authorise Phase 2) ─> #269 FE-03 e2e gate ─> #270 FE-04 shell
#264 FE-A1 problem schema ──────┤                                                                              │
#265 FE-A2 audit paging ────────┤   #268 FE-02 typed client + fixtures (needs FE-00, FE-01, FE-A1) <──────────┘
#266 FE-A3 report schema ───────┘                │
                                                 v
                 #271 FE-05 auth ─┬─> #272 FE-06 Pulpit
                                  ├─> #273 FE-07 new analysis + SSE ─> #274 FE-08 report ─┐
                                  ├─> #275 FE-09 collection (needs FE-A2) ────────────────┴─> #276 FE-10 saved
                                  ├─> #277 FE-11 billing (live: #220, #43)
                                  └─> #278 FE-12 settings
 #279 FE-13 public pages (owner: #41) · #280 FE-14 observability · #281 FE-15 Caddy/CSP deploy
 #286 FE-20 release hardening  (after FE-05 … FE-15)
 Blocked: #282 FE-16 Rynek (#21) · #283 FE-17 manual analysis · #284 FE-18 interior · #285 FE-19 listing assistant (owner)
```

The four backend slices (#263–#266) are Phase 1 work and can start now. **Launch scope** is FE-00…FE-15 plus FE-20.
FE-16…FE-19 stay visible in the UI as honest "niedostępne" states behind flags until their contracts exist.

## 3. API smoke test and sample data (#263)

One scenario registry drives two things: a CI test and a local capture.

- **CI** (`tests/smoke/`): every OpenAPI operation must have at least one success scenario and one per documented error
  status, or `test_every_operation_has_a_scenario` fails. Scenarios run in-process against Testcontainers Postgres and a
  real worker with fake providers; bodies are validated against the OpenAPI response schemas.
- **Capture** (`make api-samples`): the same scenarios against the local Compose stack write

```
data/api-samples/<UTC timestamp>/
  manifest.json                    # commit, openapi sha256, mode (fake|live), evidence class, retention date
  <operationId>/<scenario>.json    # {request, status, headers (redacted), body}
  get_audit/<scenario>/events.ndjson   # SSE transcript
```

- **At least 5 different examples.** Five hand-built, anonymised SALE listings that differ in city, size, price, admin
  fee and photo count give five distinct `succeeded` results; the failure set adds `succeeded_degraded`, RENT rejection,
  fractional ownership, upstream failure, invalid input, 402, 409, foreign 404, plus collection states (empty, 120 audits,
  saved notes, several sessions, billing disabled, fake Paddle packs and purchases).
- **Live mode** (`--mode live`) is owner-authorised per run (VPS-3 or local) and is labelled `evidence: live`.
- `data/` is already ignored (`/data/` in `.gitignore`); a test asserts it. Samples may hold third-party listing text,
  so they stay local for 30 days (`make api-samples-clean`). They are never pasted into PRs, issues or screenshots.
- **From samples to the UI** (#268): `scripts/derive_ui_fixtures.py` turns a capture into committed, sanitised fixtures
  (synthetic ids, emails, text, photo URLs; shapes and nullability kept). Fixtures validate against OpenAPI in CI; the
  local check `pnpm check:fixtures-vs-samples` proves every key path seen in the samples is covered, and prints SKIPPED
  where `data/` is absent. `pnpm dev:samples` lets a developer render the raw local samples; it is never in a build.
- Re-run the capture whenever an endpoint changes; the OpenAPI drift check catches shape changes in between.

## 4. E2E for every page, popup and clickable element (#269)

"Every element has a test" is enforced by the machine, not by review:

1. **Registry** `frontend/e2e/interactions.ts`: each interactive element is `{id, route, scenario, role, name, outcome}`;
   each dialog, sheet, menu and popover is registered with its trigger.
2. **Inventory test** visits every route in every scenario listed for it, opens every registered popup, enumerates all
   visible elements with an interactive ARIA role, and fails on any element that is **unregistered or nameless**.
3. **Coverage reporter**: tests call `interaction(id)` and must assert the outcome (URL, request sent, dialog state,
   focus target, text). The run fails if any registered id was not exercised.
4. **Popup contract** helper used by every popup test: initial focus, focus trap, Escape, focus return, backdrop policy.
5. **Lanes, all automatic:**

| Lane | When | Against |
| --- | --- | --- |
| `frontend` | every PR | types, lint, unit/component tests, build, fixture and API drift |
| `frontend-e2e` | every PR | built SPA + mocked API (sanitised fixtures), Chromium, axe per route state, console errors fail |
| journey | PRs touching `frontend/` or `services/rm_api`, and nightly | Compose stack: real API, Postgres, worker, fake providers; session seeded inside the api container by `scripts/e2e_session.py` (no HTTP bypass); `http://localhost` with `PUBLIC_APP_URL` matching so the Origin check and Secure cookies stay as in production |
| cross-browser | nightly | Firefox, WebKit; visual baselines |

`make ci` runs the first two locally (SKIPPED, not passed, when Node is missing). Agents run them before every push.

## 5. Slices

| Slice | Issue | Labels | Depends on |
| --- | --- | --- | --- |
| FE-00 API smoke + samples in `data/` | #263 | frontend, phase-1 | — |
| FE-A1 problem+json in OpenAPI | #264 | frontend, phase-1 | — |
| FE-A2 audit cursor paging and filters | #265 | frontend, phase-1 | — |
| FE-A3 versioned `DealAnalysis` schema | #266 | frontend, phase-1 | — |
| FE-01 Phase 2 authorisation + foundation | #267 | owner, blocked | #263, owner comment |
| FE-02 typed client, problem copy, fixtures | #268 | | #263, #267, #264 (#266 for report types) |
| FE-03 e2e harness + coverage gate + CI | #269 | | #267; `.github/` approval |
| FE-04 tokens, primitives, theme, shell | #270 | | #267, #269 |
| FE-05 auth pages + session boundary | #271 | | #268, #270 |
| FE-06 Pulpit | #272 | | #271 |
| FE-07 Nowa analiza (URL) + SSE | #273 | | #271 |
| FE-08 report page | #274 | | #273, #266 |
| FE-09 Moje analizy | #275 | | #271, #265 |
| FE-10 saved listings | #276 | | #274, #275 |
| FE-11 packs, Paddle checkout, purchases | #277 | | #271; live: #220, #43; money approval |
| FE-12 settings and account | #278 | | #271 |
| FE-13 public pages | #279 | owner, blocked | #270, #41 |
| FE-14 browser error tracking, analytics | #280 | | #270; L-010 |
| FE-15 Caddy, CSP, caching, deploy | #281 | | #270, #277 |
| FE-16 Rynek | #282 | blocked | #21, #16, #48, #49 |
| FE-17 manual analysis | #283 | owner, blocked | owner decision, backend spec |
| FE-18 interior tool | #284 | owner, blocked | owner decision, backend spec |
| FE-19 listing assistant | #285 | owner, blocked | owner decision, backend spec |
| FE-20 release hardening | #286 | launch | #271 … #281 |

All carry `frontend`; FE-01 onwards also `phase-2`. Umbrella: #44.

## 6. Frontend definition of done (every UI slice)

- Ticket in Phase 2 scope; repository rules, PR template, Legal/GDPR and Context lines.
- Contract confirmed in code/OpenAPI; anything proposed is labelled as proposed, never invented in production code.
- Every page, popup and clickable element registered and exercised (§4); interaction-coverage gate green.
- **At least 5 distinct sample scenarios** rendered for each data view, with visual baselines in light and dark at
  390 px and 1280 px; reviewer screenshots use sanitised fixtures only.
- All relevant states: first visit, loading, empty, filtered-empty, ready, refreshing, degraded, validation error,
  network failure, session expired, unsupported version.
- No client-side finance; money via the one formatter; unknown ≠ zero; dates in `Europe/Warsaw`, `pl-PL` numbers and plurals.
- Keyboard, touch, focus, reduced motion, 320 px, 200 % zoom, both themes; axe clean.
- User content rendered as text; no tokens in storage; tenant caches cleared on sign-out.
- `pnpm check`, `frontend-e2e` and `make ci` green; SKIPPED stages named in the PR.
- STATUS, CONTEXT, LIMITATIONS, CHANGELOG updated in the same PR when affected.

## 7. Second-pass verification against the production-ready bar

The plan was checked against `.agent/rules/poc-reference.md` *Production-ready bar* after the issues were created. Gaps
found in this pass were added to the named issues on 2026-10-15 (marked *added*).

| Bar item | Where it is covered |
| --- | --- |
| Inputs bounded and typed | #268 generated types + fixture validation; #264 problem schema; #273 URL input, server authoritative |
| Money | #268 string money, one formatter, ESLint ban; #274 no TS finance; `test_no_frontend_finance` kept |
| Time and I/O | #268 *added*: query-client defaults (no mutation retries, ≤ 2 read retries on network/5xx only, request timeout via `AbortSignal`) with tests |
| Concurrency and idempotency | #273 one POST per intent, ambiguous failure re-read; #277 `Idempotency-Key`; #271 multi-tab sign-out |
| Failure states | §6 state list; #270 error boundary and chunk-reload; #273 terminal states and credit outcome |
| Security | #281 CSP without `unsafe-inline`, `frame-ancestors 'none'`, SPA fallback never masks `/api`; #271 token fragments, cache clearing; #267 *added*: ESLint bans `dangerouslySetInnerHTML`/`innerHTML`, pnpm build scripts allow-listed; #269 *added*: dependency audit in the security job, Dependabot npm |
| Operability | #280 error tracking with redaction and release tags; #281 smoke and deploy record; #267 frontend README runbook |
| Quality gates | #267 strict TS, lint, format; #268 *added*: measured coverage floor on `api/` and formatters; #269 coverage gate |
| Accessibility | #270 landmarks, skip link, zoom, reflow; §6; #286 manual screen-reader pass |
| Performance | #286 bundle budget enforced, Web Vitals lab diagnostics |
| Legal / GDPR | tags listed in each issue; #279 consent and approved legal text; #263 sample retention |
| SEO / indexing | #279 *added*: public pages have titles and meta; `/app/*` and email-link routes are `noindex` |
| Browser support | #267 *added*: support matrix recorded; #286 real iOS/Android check |

Still open, owned by the owner: Phase 2 authorisation (#267), landing-page decision and legal text (#279, #41), pack
prices and Paddle sandbox (#43, #220, B-017), Google client id on the host (B-004), Umami CSP (L-010), and the scope of
manual analysis, interior and listing tools (#283–#285).

## 8. Out of scope for launch (decided here; reopen by issue)

Admin UI (admin uses the API and CLI), audit cancellation (no route), English UI, offline/PWA, Otodom publishing,
virtualised lists, a component-library package.
