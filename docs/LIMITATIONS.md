# Limitations register

Entry format and rules: `.agent/rules/limitations.md`. IDs never reused. Seeded from blueprint "Limitations to carry into planning" and §5.

**Owner-policy update, 2026-10-19:** [confirmed decisions](OWNER-DECISIONS-2026-10-19.md) supersede
older entries that call media retention, metric/scoring policy, cancellation, pricing/expiry or the
specific CSP/CI changes undecided. Implementation, source validation, configuration and quality
limitations remain active until evidenced; permission alone does not resolve them. Do not repeat
settled questions. BDL now includes an experimental index and separately visible adverse financial
scenario, preserving the base result. External legal/accountant/merchant sign-offs remain unconfirmed.

## Active

### L-001 — Otodom terms of service and EU database-right exposure
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** Fetch stage, `listing_snapshot`, city report, tags `LEGAL[scraping]`, `LEGAL[republication]`
- **Evidence:** inferred (blueprint §5; not assessed, not legal advice)
- **Description:** Commercial scraping of Otodom may conflict with its terms and database rights. Needs Polish legal review before charging.
- **Workaround:** Audits are user-initiated single-listing analyses; raw snapshots stay private. Features stay available and tagged.
- **Target:** Blueprint §5 risk register; pre-launch legal review

### L-002 — Datacenter IP may be blocked by Otodom
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `UPSTREAM_BLOCKED` path, audit queue
- **Evidence:** confirmed for one request (2026-10-13): one GET from the OVH VPS-1 IP through `curl_cffi` (`impersonate="chrome"`) returned HTTP 200 with `__NEXT_DATA__` and an ad with an id. Not confirmed under sustained or concurrent load, or over days.
- **Description:** One request from an OVH address was not blocked. Blocking at audit volume, rate-limit behaviour and IP reputation over time are unmeasured; the page body also contains the word `captcha` on a normal 200 page, so that marker alone is not proof of a challenge.
- **Workaround:** `UPSTREAM_BLOCKED` releases the credit; about $10/month headroom reserved for a proxy.
- **Target:** Test from the VPS in week 1 (blueprint §5)

### L-003 — Per-audit OpenRouter cost is unmeasured
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `PRO_MONTHLY_AUDIT_ALLOWANCE` (40, placeholder), pricing, release gate 4
- **Evidence:** estimate
- **Description:** No measured tokens/USD per audit; the Pro allowance has no cost basis yet.
- **Measured (2026-10-14, first live call, RM-246):** 11 photos, 3258 prompt and 175 completion tokens, USD 0.0003958 on `google/gemini-2.5-flash-lite`; one data point, one model, no floor plans. The budget hold is now priced from the OpenRouter catalog (about USD 0.0025 for that call) and the real cost replaces it.
- **Workaround:** Tokens and USD of every call are logged in `app.ai_usage` (RM-24) and spend is capped monthly with a kill switch (`OPENROUTER_MONTHLY_BUDGET_USD`, 0 = off). Measurement itself still needs real traffic.
- **Target:** Set allowance after two weeks of measured COGS

### L-004 — POC engine models money as float
- **Status:** resolved by design (ADR 0001): the engine is rewritten with `Decimal`; kept as a lesson, not a defect to carry
- **Discovered:** 2026-10-11
- **Affects:** `apps/deal-analyzer` (`output.py`, `operating.py`), API/worker boundary
- **Evidence:** confirmed in POC read (CONTEXT.md §5 G1–G2)
- **Description:** Engine uses float; `agents.md` §3 requires Decimal in persisted/returned money fields.
- **Workaround:** None needed; do not reproduce float money in new code.
- **Target:** Data-plane step (blueprint 4.8 step 2)

### L-005 — Otodom listing payload shape is not verified against a live page
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `rm_worker.clients.otodom.classify`, `UPSTREAM_SCHEMA_DRIFT`, RM-28 contract test
- **Evidence:** confirmed for one sale listing (2026-10-13, owner-authorised, `scripts/live_otodom_probe.py` from a dev machine and from the VPS): HTTP 200, `__NEXT_DATA__` present, `props.pageProps.ad` an object with an integer `id`. One listing only; other listing types, rental ads and expired ads are unverified. `ad.characteristics` is a **list** of items, not a mapping, so the admin-fee (czynsz) extraction must scan it. A challenge marker (`captcha`) appears inside a normal 200 page, so the marker check is a hint, not a verdict.
- **Description:** The client accepts a page whose `__NEXT_DATA__` holds `props.pageProps.ad.id`, the minimum the engine needs. Offline tests use hand-built pages. Page markup, challenge pages and the real ad shape can differ.
- **Workaround:** Anything unexpected becomes `UPSTREAM_BLOCKED` or `UPSTREAM_SCHEMA_DRIFT` and releases the credit; nothing is guessed.
- **Target:** RM-28 (nightly contract test against one live listing); L-002 test from the VPS

### L-006 — Listing image hosts and per-call vision cost are assumptions
- **Status:** active
- **Discovered:** 2026-10-11
- **Affects:** `rm_worker.images` (host allow-list), `OpenRouterClient` budget estimate, release gate 4
- **Evidence:** inferred (`olxcdn.com` confirmed against one live listing on 2026-10-14: all 12 photos were served from `ireland.apollo.olxcdn.com`; floor-plan hosts unverified; the per-call budget hold is now priced from the OpenRouter catalog, RM-246)
- **Description:** Photos are fetched only from allow-listed https host suffixes; if Otodom serves images from another host they are skipped (the audit then runs with fewer photos, or degraded). Redirects are never followed, so a CDN that redirects to another host is skipped too. The reservation estimate per OpenRouter call is not measured.
- **Workaround:** Set `IMAGE_HOST_ALLOWLIST` and `OPENROUTER_CALL_ESTIMATE_USD` from the first live run; skipped images are logged (`image_skipped`) without URLs.
- **Target:** Verify with the contract test (RM-28) and measured COGS (L-003, RM-24)

### L-007 — CAPEX catalog prices are placeholders
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** `deal_analyzer.capex` (`CATALOG_PLN_PER_M2`, `TIER_MULTIPLIER`), CAPEX, Max Bid, grades; release readiness
- **Evidence:** estimate (invented round numbers; no market source)
- **Description:** The PLN/m² renovation prices and the regional multipliers only make the estimator work. Every `CapexEstimate` carries `prices_are_placeholders=True` and a `placeholder-…` catalog version. Valuations built on them must not be shown as real.
- **Workaround:** None until the owner supplies a sourced price list (per condition and city tier, ideally per item: bathroom, kitchen, floors, windows, wiring) or approves a source to import.
- **Target:** blocker B-015; PRE-DEPLOYMENT §5

### L-008 — OpenStreetMap: attribution and public-service limits
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** `rm_worker.clients.osm`, `app.geo_cache`, any screen or report that shows distances
- **Evidence:** confirmed (OSM usage policy and ODbL licence, read 2026-10-12; not legal advice)
- **Description:** Distances and points of interest come from OpenStreetMap (ODbL): the product must show "© OpenStreetMap contributors" wherever they are shown. The public Nominatim and Overpass services forbid heavy or bulk use and require an identifying User-Agent, a 1 request per second cap and caching, all enforced in code (placeholder User-Agent refused). Batch refreshes of hundreds of cities would breach the policy.
- **Workaround:** Cache 90 days (geocoding) and 30 days (POIs); degrade to "no distances" on any failure. Self-hosting Nominatim/Overpass is the path for scale.
- **Target:** frontend attribution (Phase 2); revisit before the batch lane (RM-16)

### L-009 — Better Stack: free-tier limits and data region not verified for launch
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** `rm_core.observability` (error events and traces), uptime monitor, backup heartbeat; processor list
- **Evidence:** confirmed (betterstack.com/pricing and the Sentry SDK ingestion docs, read 2026-10-12); data region unverified
- **Description:** Monitoring moved from Sentry to Better Stack (ADR 0009). The free tier read on 2026-10-12 is 100k exceptions/month (90-day retention), 10 uptime monitors, 10 heartbeats, 3 GB logs/month (3-day retention). The docs do not say where error data is stored, so EU residency for scrubbed events is unconfirmed. Heartbeats have no "in progress" signal, so a backup that hangs is only caught when the 24 h heartbeat is missed.
- **Workaround:** PII is scrubbed before sending (`scrub_event`); traces sampled at 5 %.
- **Target:** before launch (PRE-DEPLOYMENT §4 DPA, §6 monitoring); B-001

### L-010 — Umami events go to a host the blueprint CSP does not allow
- **Status:** deferred (decided: allow `https://gateway.umami.is` in `connect-src`, owner 2026-10-12; applied with the Caddy config when the frontend exists)
- **Discovered:** 2026-10-12
- **Affects:** blueprint Caddy `Content-Security-Policy` (`connect-src`), the SPA analytics loader (Phase 2), B-002
- **Evidence:** confirmed (the script served at `https://cloud.umami.is/script.js` on 2026-10-12 posts to `https://gateway.umami.is/api/send`; the blueprint `connect-src` lists only `https://cloud.umami.is`); whether the script host ever changes is unverified
- **Description:** With the blueprint CSP the browser would block every analytics event while the script itself loads. The blueprint is not edited until the maintainer decides (`rules/architecture.md`).
- **Workaround:** none needed in Phase 1 (no frontend). Options: allow `https://gateway.umami.is` in `connect-src`, or proxy events through our own domain.
- **Target:** #143 (`docs/ANALYTICS-SPEC.md` section 2 lays out both options); decide before the Caddy config (#15) and N-30 (#72)

### L-011 — The magic-link token travels in Procrastinate job arguments
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** `rm_worker.tasks.email.send_magic_link`, table `procrastinate_jobs`, GDPR retention
- **Evidence:** confirmed (the API defers the task with `email` and `url`; the URL fragment holds the raw token)
- **Description:** Everywhere else only the SHA-256 of a login token is stored. The job arguments hold the raw token and the address until the job row is deleted, and failed jobs are kept for inspection. The token is single-use and expires after 30 minutes, which bounds the damage of a database leak; it does not remove it.
- **Workaround:** none yet. Planned: delete finished and old failed `send_magic_link` jobs in the ops maintenance task (Procrastinate's built-in `remove_old_jobs`).
- **Target:** #25 (worker-ops); blueprint §2 Auth decision, rule 1

### L-012 — Client IP behind the proxy decides the per-IP limit
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** `POST /api/auth/email/start` (20/hour per IP), the stored session IP, deploy (Caddy → uvicorn)
- **Evidence:** inferred (uvicorn `--proxy-headers` trusts forwarded headers only from `127.0.0.1` unless `--forwarded-allow-ips` is set; the image enables `--proxy-headers` but not the allow-list; not yet run behind Caddy)
- **Description:** If uvicorn does not trust Caddy, every request looks like it comes from the proxy, so the per-IP limit would become one shared limit for all users and the stored session IP would be wrong.
- **Workaround:** none needed locally. Before deploy set `--forwarded-allow-ips` to the Caddy container address and add a smoke check.
- **Target:** #15 (ops); PRE-DEPLOYMENT §6

### L-017 — Engine memory cap is Linux-only; stalled worker jobs are not cleaned
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** `rm_worker.engine_child`, `rm_worker.tasks.reconcile`, release gate 4 (memory)
- **Evidence:** confirmed (code); the 1024 MB `AUDIT_CHILD_MEMORY_MB` value is an estimate until gate 4 measures peak audit memory
- **Description:** The engine child lowers `RLIMIT_AS`, which Linux enforces and macOS does not; the cap test is skipped off Linux and runs in CI. Address-space limits also count mapped-but-unused memory, so the value needs the gate 4 measurement. When a worker is killed, its Procrastinate job row stays `doing`; the reconciler recovers the audit and credit from the `audit` row, but the stalled job row is only removed by the weekly retention job once finished states exist.
- **Workaround:** none needed for correctness (the claim is idempotent, a re-run is a no-op); watch `monitor` queue lag.
- **Target:** gate 4 (#34), #15

### L-018 — The audit journey is proven offline only; no live evidence, no vision, no rent data
- **Status:** active (renumbered from a duplicate L-015, RM-187)
- **Discovered:** 2026-10-13
- **Affects:** `POST /api/audits`, `rm_worker.audit_pipeline`, `rm_worker.context`, `rm_worker.listing_source`
- **Evidence:** confirmed (`tests/integration/test_audit_journey.py`, `test_audit_context.py` run with a fake HTTP transport and hand-built rental rows)
- **Description:** Crash recovery, the killable engine child and the SSE stream are built and tested offline (RM-185, RM-186). The real Otodom client and market context are wired behind `AUDIT_PROVIDERS=real` (RM-187) but have only run against a fake transport; one live fetch was confirmed for payload shape (L-005). The comparable-rent store is filled on demand by the rental importer (RM-240, L-022); the first audit in a city still gets the engine's refused rent (rent 0, warning `rent_refused_too_few_comparables`). The risk-free rate is an owner-supplied `RISK_FREE_RATE` (unset: `CONTEXT_UNAVAILABLE`). The vision and OCR stages are wired (RM-244, L-023) but need an OpenRouter key on the host; without it every success is `succeeded_degraded` (`VISION_UNAVAILABLE`). The analyst audit is refused (403).
- **Workaround:** none needed for a private beta; do not present results as market-grounded until rental importers and a rate source land.
- **Target:** importers (#106 slice 2), rate source (N-12), vision/OCR integration, live evidence (level 3); docs/STATUS.md journey table

### L-019 — Password storage is an owned risk; policy and blocklist are not yet validated
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** email/password sign-in (#203-#205), `user_credential`, `auth_token`
- **Evidence:** inferred (specification only, `docs/PASSWORD-AUTH-SPEC.md`; no code yet)
- **Description:** ADR 0013 reverses the "no passwords" decision. Argon2id parameters (19456 KiB, t=2, p=1) are the OWASP minimum, not measured on the 4 GB VPS-1 next to the audit worker. The common-password blocklist source and size are open. Real Resend delivery of verification and reset mail is unverified (B-004).
- **Workaround:** none until implemented; parameters are settings, so they can be raised without a code change.
- **Target:** #203 (parameters measured, blocklist chosen), #205; gate 7 session-revocation timing

### L-021 — The arm64 image does not start under Docker Desktop on the developer Mac
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** local `make up` / `make smoke` on Apple Silicon; not the x86_64 VPS
- **Evidence:** confirmed (`python -c "import cryptography.exceptions"` exits 132, SIGILL, inside `rentmonitor-py:local` built for aarch64; `cryptography` 50.0.2 via `google-auth`; the same image built for linux/amd64 runs)
- **Description:** On Docker Desktop 27.3.1 (aarch64 VM) the native `cryptography` wheel crashes on import, so the API container restarts forever. The VPS is x86_64 and CI is x86_64, so neither is affected, but local smoke tests need an x86_64 build.
- **Workaround:** `DOCKER_DEFAULT_PLATFORM=linux/amd64 make smoke` (slower, emulated). Try a newer Docker Desktop or pinning `cryptography` if an arm64 image is ever needed.
- **Target:** none until an arm64 deployment is wanted
### L-020 — Paddle API response shapes are read from documentation only
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** `rm_core.paddle` (transaction totals, price and adjustment parsing), billing slices #217-#219
- **Evidence:** inferred (Paddle developer documentation via Context7; no sandbox call has been made, B-003 style blocker for Paddle sandbox access)
- **Description:** The client reads `data.details.totals.total` (falling back to `data.totals.total`), `unit_price.amount` as a string of minor units and `billing_cycle: null` for one-time prices. Documentation examples are not consistent about where totals sit, and webhook payloads are not modelled yet. Any difference found in the sandbox changes parsing, not the design.
- **Workaround:** sales stay disabled (`BILLING_PROVIDER=disabled`); `verify_catalog` must pass against the sandbox before enabling.
- **Target:** #220 (sandbox evidence), `test_paddle_pack_checkout_sandbox`

### L-022 — Rental comparables are a sample of Otodom's first result pages, imported on demand
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** `rm_worker.importers.otodom_rental`, `MarketContext.rent_input`, rent estimate quality
- **Evidence:** confirmed for the page shape (a live rent search for one city returned 200 with 36 offers a page under `pageProps.data.searchAds`, 2026-10-14); inferred for sampling bias and for sustained-load behaviour (L-002)
- **Description:** each city and month imports at most the first 5 pages (about 180 offers) in Otodom's default order, so promoted offers may be over-represented and big cities are under-sampled. Rents are the advertised `totalPrice` (Otodom lists the admin fee separately as `rentPrice`, which is never read: invariant 3; whether `totalPrice` excludes the fee is Otodom's convention, inferred); only offers priced in PLN with a visible price are kept. A city is imported only after an audit asks for it, so the first audit in a new city gets the refused rent and the next one is grounded. A month with fewer than 10 usable offers is skipped and the previous month stays.
- **Workaround:** none needed for a beta; a city list can be pre-imported by deferring `import_rental_city`.
- **Target:** #209/#49 and #16/#21/#282; the owner confirmed the complete verified 727-location catalogue, nightly last-24-hours collection, durable Postgres corpus and daily trend history as part of the next feature batch with BDL (2026-10-16). See [next-batch gaps and OTO-01–04 proposals](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md#0-next-implementation-batch-rynek-data-and-location-context), [nightly-import specification](OTODOM-NIGHTLY-IMPORT.md), and accuracy evaluation #94. No nationwide bootstrap, rental periodic dispatcher or durable daily-history implementation is claimed.

### L-023 — Vision quality and floor-plan advert shape are unverified
- **Status:** active
- **Discovered:** 2026-10-14
- **Affects:** `rm_worker.vision_stage`, `OPENROUTER_VISION_MODEL`, `Listing.floor_plan_urls`, grade and Max Bid when vision is on
- **Evidence:** confirmed for the photo shape (`images[].large` on `olxcdn.com`, one live listing, 2026-10-14); inferred for `floorPlans` (null on that listing; objects or strings are both accepted); estimate for model quality and cost
- **Description:** the stage is proven offline with a fake host and a fake model. The default model is a cheap placeholder chosen from OpenRouter's public list, not from an accuracy test; the prompt (`vision-v1`) is unevaluated. Photos are taken in advert order (up to 25), exterior shots included. The engine clamps every proposed adjustment to +/-15 %, so a bad answer moves capex and rent by at most that, but a systematically wrong `condition` still changes the capex base. One call carries photos and plans, so OCR text and condition share one answer.
- **Workaround:** `LEGAL_IMAGES_ENABLED=false` or an empty `OPEN_ROUTER_API_KEY` turns the stage off (audits end degraded); the monthly budget caps spend.
- **Target:** #94 (accuracy on an owner-labelled set), L-003 (measured cost), #211 (live run)

### L-014 — RPO 5 minutes and RTO 1 hour are targets, never measured
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** backups (WAL-G to R2, nightly dump), release gate 6 (#37), the privacy notice, PRE-DEPLOYMENT section 6
- **Evidence:** estimate (blueprint §4.7 calls them "targets, unverified until the first timed point-in-time restore" and says WAL-G was not tested against R2; only a 55-byte upload and read-back to R2 is confirmed, B-005c)
- **Description:** No WAL-G archive, base backup, lifecycle rule or restore has run against R2. Every statement of RPO or RTO is a target.
- **Workaround:** none; say "target" wherever it is stated. The local logical drill (`scripts/backup_drill.sh`) covers only the dump path.
- **Target:** gate 6 (#37), `docs/R2-SPEC.md` section 5; #15

### L-015 — MoR settlement and Polish KSeF treatment need accountant review
- **Status:** active
- **Discovered:** 2026-10-13
- **Affects:** proposed billing-provider selection, VAT invoices, blueprint §3 and release gate 1
- **Evidence:** confirmed (Ministry of Finance KSeF scope and Paddle reverse-invoice documentation, linked in [BILLING-ALTERNATIVES.md](BILLING-ALTERNATIVES.md)); application to Renti's entity and contract is unverified
- **Description:** A MoR handles the customer sale, but Renti's supplier/self-billing documents, VAT status, settlement reconciliation and applicable KSeF obligations have not been assessed. No evidence establishes a blanket KSeF exemption for Renti or vendor KSeF submission. The current Fakturownia API → KSeF workflow also remains untested.
- **Workaround:** Keep the accepted Stripe spec; treat MoR simplification as a proposal. Obtain sample customer and settlement documents and an accountant's assessment before changing the invoice pipeline.
- **Target:** accountant review #41; provider decision and invoice release gate

### L-016 — Renti acceptance by a merchant of record is unverified
- **Status:** active
- **Discovered:** 2026-10-13
- **Affects:** proposed Paddle/Lemon Squeezy onboarding and paid launch
- **Evidence:** confirmed (Paddle AUP restricts investment advice; Lemon Squeezy restricts regulated real-estate services and unlicensed content); Renti classification is unverified
- **Description:** General SaaS support does not establish acceptance of yield/IRR/Max Bid reports and investment rankings. No provider has reviewed the actual product. Paddle supports one-time PLN BLIK but not BLIK subscriptions; Lemon Squeezy's published methods omit BLIK.
- **Workaround:** Request written product assessment with representative reports, prepaid report-pack entitlements and data-rights information. Owner selected one-time packs on 2026-10-13, so recurring BLIK is outside the pilot. If Paddle rejects the offering, ordinary Stripe plus Polish invoicing remains a fallback requiring a separate decision.
- **Target:** provider evaluation in [BILLING-ALTERNATIVES.md](BILLING-ALTERNATIVES.md); decision before replacing ADR 0005

### L-028 — API samples are fake-provider data; the live capture path is unexercised
- **Status:** active
- **Discovered:** 2026-10-15
- **Affects:** `tests/smoke/`, `scripts/capture_api_samples.py`, `data/api-samples/` (local), the frontend fixtures derived from them (#268)
- **Evidence:** confirmed (source and a run of `make api-samples`, 174 of 174 scenarios, 36 of 36 operations over loopback HTTP)
- **Description:** The smoke test and the offline capture run the real API, Postgres, ledger, queue worker and engine, but the listing source, market context, vision model, Paddle and Google are in-memory fakes, and the API runs as a local uvicorn against a throwaway database in the Compose Postgres, not as the `api` container with a real provider configuration. Result numbers (grades, prices, Max Bid) come from five hand-built listings and a flat rent per m2; they say nothing about real listings or accuracy. `--mode live` (owner-authorised, needs `API_SAMPLES_LIVE_AUTHORISED=1` and a refs file) is written but has not been run: no real Otodom, OpenRouter or Paddle answer has been captured, so shapes only a live provider produces (for example a `result.vision` record from a real model, long descriptions, listings with unusual fields) are not in the samples. Statuses and codes that the document does not describe fail the smoke test, and the capture manifest lists any gap (none since #264).
- **Workaround:** Treat samples as shape evidence. Ask the owner to run the live capture once before the report page (#274) is finalised.
- **Target:** #263; the live run is an owner action recorded on #44.

### L-029 — The SPA's Google sign-in and mailed links are verified against stand-ins
- **Status:** active
- **Discovered:** 2026-10-15
- **Affects:** `frontend/features/auth` (`gis.ts`, `GoogleButton.tsx`), the e2e lanes, #281 (CSP)
- **Evidence:** confirmed (tests): the mocked lane replaces Google's script with `e2e/gis.ts`; the journey lane runs sign-up through a token that `scripts/e2e_session.py register-token` stores as registration does, because the journey stack has no mail provider. Real Google Identity Services, real Resend delivery and the production CSP have not been exercised.
- **Description:** The Google button needs `VITE_GOOGLE_CLIENT_ID` at build time (B-004: not set on the host) and the CSP must allow `accounts.google.com` scripts, frames and connections (#281, blueprint §4.3 currently lists Stripe only). Until then the button is hidden (or shows "niedostępne" if the script is blocked) and the e-mail methods work.
- **Workaround:** E-mail and password, and the sign-in link.
- **Target:** B-004 (client id on the host), level 3 evidence per `delivery.md`. **RM-281:** the Caddy CSP now allows the GIS script, style, frame and connections and the web image passes `GOOGLE_CLIENT_ID` as the build argument; the button under the real CSP is unverified until a client id is set.

### L-031 — GitHub checks do not enforce frontend validation
- **Status:** active
- **Discovered:** 2026-10-15
- **Affects:** `.github/workflows/ci.yml`, `security.yml`, npm dependency monitoring and frontend merge confidence
- **Evidence:** confirmed (workflow/config read): Python checks and two historical frontend filename checks exist; no SPA install/typecheck/lint/build/unit/browser lane or npm Dependabot entry exists. Local CI has frontend stages. **RM-296 (2026-10-15):** `ci.yml` now runs `frontend` (`pnpm check`), `frontend-e2e` (mocked lane with the interaction gate) and `frontend-journey` (Compose stack) on every PR; `security.yml` runs `pnpm audit --prod`; Dependabot covers npm.
- **Description:** The jobs run but are not yet **required** checks in the `staging`/`main` rulesets (a repository setting only the owner can change), so a merge does not wait for them. Firefox and WebKit are not run (#311).
- **Workaround:** Read the frontend jobs' result on the head commit before merging; keep running `make ci` locally.
- **Target:** owner adds `frontend`, `frontend-e2e`, `frontend-journey` to the required checks (B-019); cross-browser #311; release hardening #286.

### L-032 — Frontend localization and async edge cases remain outside the current guarantees
- **Status:** active
- **Discovered:** 2026-10-15
- **Affects:** `frontend/api`, auth and analysis forms, analysis submission recovery
- **Evidence:** confirmed source review and focused reproductions; see `frontend/docs/AUDIT-2026-10-15.md`, F05–F13 and F16; re-verified on `staging` `5444eb8`.
- **Description:** Copy lives in the typed catalog since RM-305; numbers are laid out by Intl since RM-306; body errors are normalised since RM-307. (Busy-button submission and the silent-stream gap were fixed in RM-273.) Unit-test coverage is reported per directory since RM-311; `ui/` and `features/` are mostly covered by the browser suite, which coverage numbers do not include.
- **Workaround:** Preserve exact decimal strings and use existing centralized formatters; do not infer acceptance of an ambiguous request from an unrelated recent audit. Treat current automated passes as scoped evidence.
- **Target:** open: #334 (visual snapshots), real devices and screen readers (#286); fixed: copy catalog RM-305, browser evidence and coverage scope RM-311, recovery RM-304, numbers RM-306, transport RM-307, guards RM-309 and RM-325, form errors RM-310, bundle RM-312; tracker #314; hardening #286.

### L-033 — Browser error reporting is built but off; Umami analytics not built
- **Status:** active
- **Discovered:** 2026-10-15
- **Affects:** `frontend/shell/observability.ts`, `deploy/Caddyfile` CSP, Better Stack
- **Evidence:** confirmed (code and tests): without `VITE_SENTRY_DSN` the SDK is never loaded and nothing is sent; delivery to Better Stack from a browser has not been observed (no browser DSN exists yet). RM-280 also found that both scrubbers (browser and `rm_core.observability`) let a token parameter at the very start of a text through (`token=…` with nothing before it); fixed in both with tests.
- **Description:** Unexpected browser errors are not visible to the team until the owner creates a Better Stack browser application, sets `VITE_SENTRY_DSN` (build) and `BROWSER_ERRORS_ORIGIN` (CSP) and the image is rebuilt. Umami page views (#280 acceptance 4) are not built: the Umami script host needs the CSP decision L-010.
- **Workaround:** server-side errors still reach Better Stack (`SENTRY_DSN`); a person can quote the request id shown with every problem.
- **Target:** B-020 (browser DSN), L-010 (Umami CSP), level 3 evidence per `delivery.md`.

### L-034 — The report's "city" price group is a list of names, not population bands
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** `apps/deal_analyzer/capex.py` (`city_tier`, `TIER_MULTIPLIER`), the renovation assumptions in the report
- **Evidence:** confirmed (code): `metro` is Warszawa, `major` a fixed list of eleven cities (Kraków, Wrocław, Gdańsk, Gdynia, Sopot, Poznań, Łódź, Katowice, Szczecin, Lublin, Białystok), everything else `other`. No population figure is read; the multipliers (1.25, 1.10, 1.00) are placeholders like the price list (L-007)
- **Description:** "pozostałe miasta" meant "not on the list", not "a small town", and no authoritative population threshold backs the tiers, so the UI does not show a population range. It shows the multiplier as "Współczynnik cen w mieście"; the `tier` stays in the stored report and the calculation is unchanged
- **Workaround:** none needed for the number itself; do not describe the tier as a population band
- **Target:** a sourced city classification (GUS population or the market-data bootstrap, #209) and sourced multipliers with B-015

### L-035 — "Moje analizy" cannot be sorted by the server
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** `GET /api/audits` (no `sort`/`order` parameter), `frontend/features/analyses/list/AnalysesTable.tsx`
- **Evidence:** confirmed (OpenAPI parameters: `limit`, `cursor`, `status`, `grade`, `q`, `request_key`; keyset order is newest first)
- **Description:** Filtering (status, grade, id prefix) and paging (cursor) are server requests, but ordering is fixed. The table therefore has no sort controls and says its order (`aria-sort="descending"` on the date column); sorting the loaded rows would look like ordering every analysis
- **Workaround:** the filters narrow the list; the date column is the order
- **Target:** an API ordering parameter with a keyset per order, then sortable headers

### L-052 — Visual lane: layout findings seen in the pictures, and its colour tolerance
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** `frontend/e2e/visual.spec.ts` and its baselines; the app shell at 1280 x 800 and 390 px
- **Evidence:** confirmed (pictures `report-failed-upstream-light.png` desktop, `dashboard-loaded-light.png` mobile; probe runs recorded in the RM-334 PR)
- **Description:** (1) At 1280 x 800 the sidebar's "Wyloguj się" button is cut off at the bottom of the viewport (the sidebar does not scroll when the window is short). (2) At 390 px the header's "Tryb ciemny" label touches the "Menu" button. (3) In full-page pictures the fixed sidebar is drawn only for the first viewport height (a property of full-page capture, not of the app). (4) The lane tolerates small colour differences: a 3-step RGB change of `--accent` was not detected, while a visible change failed 14 pictures. The baselines record these layouts as they are
- **Workaround:** none for 1 and 2; treat (3) and (4) as properties of the lane
- **Target:** a UI issue for 1 and 2 (they are shown in the committed baselines, so fixing them changes pictures on purpose)

### L-041 — Gates 4 and 5 have synthetic lower-bound numbers only
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** release gates 4 (memory) and 5 (connection budget), #35, #36, `scripts/load_check.sh`
- **Evidence:** confirmed for the numbers (run on VPS-3, 2026-10-16, `docs/DEPLOYMENTS.md`); the representativeness gap is inferred from what the run did not exercise
- **Description:** Twenty audits submitted together on VPS-3 used at most 28 database connections and 7.1 % of the audit worker's memory limit. They were hand-built listings without photos, so the vision stage (images are the expected memory peak) never ran, no batch import was running, there was no webhook traffic and the audit worker processes one audit at a time. The numbers cannot decide gate 4's "concurrency 2 only if peak < 60 %" or close gate 5
- **Workaround:** none needed for a private beta without customers
- **Target:** an owner-authorised run with real listings and photos (OpenRouter cost, one Otodom request per listing, L-002 applies), with the batch import running, recorded in #35 and #36

### L-037 — Saved listings: a full list is not proof of absence; concurrent note edits are last-write-wins
- **Status:** resolved (the 200-item cap and the note-wiping save); the residual limit below stays
- **Discovered:** 2026-10-16
- **Resolved:** 2026-10-16, RM-347 (`GET /api/saved` accepts `limit` up to the 500 per-account cap; `PUT` keeps the stored note when the body has no `note` key and only an explicit `null` clears it; the SPA asks for 500, saves with no note and shows no toggle for a listing missing from a full list)
- **Affects:** `GET /api/saved`, `PUT /api/saved/{otodom_id}`, `frontend/features/saved/`
- **Evidence:** confirmed (`tests/integration/test_me_saved_admin.py`, `frontend/features/saved/saved.test.tsx`)
- **Description:** The 500 cap is soft (two simultaneous saves may overshoot by one), so a list of exactly 500 may be incomplete; the SPA then treats an absent listing as unknown. The note editor sends the whole note; two tabs editing the same note are last-write-wins (no version check), so paging alone does not prevent a stale-tab overwrite of an explicit edit. Saving from a toggle can no longer touch a note
- **Workaround:** none needed for the toggle; edit one note in one tab
- **Target:** an `If-Match`/version on notes if concurrent editing matters

### L-038 — Purchases in the SPA are exercised against a stand-in for Paddle.js only
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** `frontend/features/billing/`, `frontend/e2e/paddle.ts`, `deploy/Caddyfile` CSP, `VITE_PADDLE_CLIENT_TOKEN`
- **Evidence:** confirmed (every browser lane replaces `window.Paddle`; the journey stack builds without a token and has billing disabled)
- **Description:** Checkout, the `/pay` default payment link and the success page are proven offline against the fake Paddle client behind the API and a Paddle.js stub. Real Paddle.js has never run with a real token in this app. 2026-10-16 (RM-277): the Caddy CSP got opt-in `PADDLE_CSP_*` values (hosts read from `paddle.js` and verified in Chromium against the Caddy image with a *fake* sandbox token, `docs/PADDLE-SANDBOX-SETUP.md` section 4b); they are empty by default. Overlay display needs `style-src-attr 'unsafe-inline'` (owner decision, evidence in 4b); with it empty the overlay is created but never shown. There is no client-side token on any host (B-017), and BLIK timing, a real transaction, the live hosts and the invoice link are unverified. Whether Paddle.js itself fetches from the page (`connect-src`, which gets no Paddle host today) or only inside its iframe is also unverified; a blocked fetch would show in the browser console on the first sandbox run. The SPA offers no purchase without a token, and `/pay` says it is not configured
- **Workaround:** none needed while billing is disabled; no purchase can be started
- **Target:** #220 (sandbox evidence, owner inputs B-017), CSP change with it, then level 3 in `docs/STATUS.md`
### L-036 — Settings cannot tell a password account from a Google-only one
- **Status:** resolved
- **Discovered:** 2026-10-16
- **Resolved:** 2026-10-16, RM-345 (`GET /api/me` returns `has_password`, true when a credential row exists; the settings page shows the change form only then and the recovery notice otherwise; nothing is inferred from the sign-in method or e-mail)
- **Affects:** `GET /api/me`, `frontend/features/settings/SettingsPage.tsx`
- **Evidence:** confirmed (`tests/integration/test_me_saved_admin.py::test_me_says_whether_the_account_has_a_password_for_each_way_of_signing_in`, `SettingsPage.test.tsx`)
- **Description:** Before, the password form was shown to every account and a Google or magic-link account got "To nie jest Twoje obecne hasło"
- **Workaround:** none needed
- **Target:** done

### L-042 — Multi-level BDL location context and fundamentals rankings are not integrated
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** #48 BDL contract, #21 market API, #282 Rynek, worker context, audit reports and agent fact inputs
- **Evidence:** confirmed by reading live #48/#49 and target source at `51e45fa`; read-only GUS-reference inspection at `fd25b15` plus identified working-tree modifications. No fresh external BDL verification or POC test run.
- **Description:** #48 names `gus-stats-poc` but does not explicitly require its location profiles, indicator history/comparisons/rankings, separate fundamentals index or agent/report consumers. The production worker context currently loads rent comparables and a configured risk-free rate only; price/rent sidecar types cannot represent demographic/fiscal facts faithfully. The reference has 22 resolved raw candidate metrics, ten derived definitions, hierarchical reference identities and REIS v3, but historical review documents differ from current code and are not product acceptance evidence. Owner inclusion/inspection scope is confirmed; exact metric/scoring/publication policy remains to be recorded.
- **Workaround:** do not claim municipal/ranked context is used by an audit; keep existing financial reports available without invented local facts or proxy precision.
- **Target:** [BDL location-context contract proposal](BDL-LOCATION-CONTEXT-CONTRACT.md), amendments to #48/#21/#282 and proposed LCTX-01–03; remaining B-023 policy decisions. Keep location index separate from property grade and all finance unchanged until a separate approved engine-spec change.

### L-043 — Parallel feature protocol is not an automated multi-lane dispatcher
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `scripts/dispatch_next.py`, `.github/workflows/{dispatch,claude}.yml`, feature-batch coordination
- **Evidence:** confirmed in source: any active Claude run or in-flight PR makes the dispatcher idle. Claude workflow concurrency is per issue, not a global capacity/path-ownership controller. Recent five queried Claude runs were skipped; headless authentication was not verified by this audit.
- **Description:** Parallel-work rules and unique documentation handoffs now define isolated ownership and same-PR integration, but do not enforce runtime file leases, worker caps, branch handoff, integration readiness or multi-lane scheduling. Existing dispatcher tests cover serial behavior only. B-021 remains historical unclosed headless-auth evidence, not a newly confirmed current auth failure.
- **Workaround:** coordinate a bounded isolated-session/manual-run pilot through the assigned integrator; retain all required checks and record actual launch/auth/test evidence. No automatic dispatch enablement or new paid run is implied.
- **Target:** [parallel delivery guide](PARALLEL-FEATURE-DELIVERY.md), optional dispatcher issue proposal in §8; implement/test explicit capacity, ownership, recovery and merge coordination before claiming unattended parallel delivery.

### L-044 — Analysis reports lack durable visual/item evidence and seller questions
- **Status:** active
- **Discovered:** 2026-10-16
- **Affects:** `apps/deal_analyzer/vision.py`, `listing.py`, `analysis.py`; `services/rm_worker/vision_stage.py`; `frontend/features/analyses/report/`
- **Evidence:** confirmed in source at `51e45fa`; focused extraction/vision/contracts/schema tests (219 passed) and report/adapter tests (35 passed). These tests cover existing behavior, not the missing features.
- **Description:** Listing photo and floor-plan URLs are extracted and downloaded for vision, but the report renders no gallery and has no authenticated durable media contract. The production CSP permits only same-origin/data images. `VisionRecord` retains condition, counts and financial adjustments, but drops per-image classifications, parsed floor-plan text and notes. The typed listing/vision/report models have no equipment inventory. “Co sprawdzić” is warning-derived copy; no generated seller-question artifact or operation exists. Manual input and the interior tool remain separate planned features (#283/#284), not alternative working ways to supply this evidence.
- **Workaround:** The report links to the source listing where available; its availability and image retention are external. Use the existing checklist for known warnings; do not present it as generated seller questions or treat unobserved equipment as absent.
- **Target:** [feature-gap audit and implementation guide](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md), proposed G-01/G-02/G-03 (not filed); existing #211, #283, #284. Implement media/evidence contracts before dependent UI and preserve historical report compatibility.

### L-045 — No BDL metric is selected and no publication threshold is set
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `packages/rm_core/location_contracts.py` (`evaluate_gate`, `require_publishable`), LCTX-01 phase 2, #48, #21, #282
- **Evidence:** confirmed (`tests/unit/test_bdl_metrics.py`: every undecided threshold fails closed)
- **Description:** The ranking and comparison logic is implemented, but `PublicationPolicy` thresholds (`min_coverage`, `min_cohort_size`) and the selected metric list with reviewed `bdl_variable_id`s are owner decisions (B-023). Until they are recorded, gates return `undecided` and nothing can be published.
- **Workaround:** none; do not present municipal or ranked context as available
- **Target:** B-023 items 1 and 3, then LCTX-01 phase 2

### L-046 — BDL source staleness is not modelled
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `packages/rm_core/location_contracts.py`, LCTX-01 phase 2
- **Evidence:** confirmed (no age field or limit in the gate)
- **Description:** The maximum source age is undecided, so an old observation year is never refused for age. Fiscal comparability across years is likewise not decided.
- **Workaround:** none needed while nothing is published (L-045)
- **Target:** B-023 item 3

### L-047 — BDL attribution text and terms review are missing
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `packages/rm_contracts/location_context.py`, future reports and API results (`LEGAL[third-party-data]`)
- **Evidence:** confirmed (no attribution field populated; counsel review not done, B-012)
- **Description:** Contracts carry a source digest but no attribution wording or redistribution terms. Tags mark the code; they are not a legal verdict.
- **Workaround:** none needed while nothing is published
- **Target:** B-023 item 2, B-012

### L-048 — Rental offer expiry says nothing about whether the offer is still live
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `packages/rm_contracts/market.py` (`RentalOffer.expires_at`), future `market_offer` archival (`LEGAL[scraping]`, `LEGAL[third-party-data]`)
- **Evidence:** confirmed by design (`tests/unit/test_otodom_corpus.py`)
- **Description:** An offer expires 90 elapsed days after its publication time (first seen when that is missing or in the future). Expiry is an age archive rule only; it does not show that the advertisement was withdrawn or let.
- **Workaround:** do not present archived or aged offers as currently available
- **Target:** OTO-01 phase 2 and the nightly importer (`docs/OTODOM-NIGHTLY-IMPORT.md`)

### L-049 — Offers seen under two locations are flagged, first assignment wins
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `CorpusRepository` semantics in `packages/rm_contracts/market.py`, future importer
- **Evidence:** confirmed (`tests/unit/test_otodom_corpus.py`, reference repository `tests/market_corpus_fake.py`)
- **Description:** A conflicting sighting is counted and flagged on the run; the first location stays. There is no review tool.
- **Workaround:** none needed before an importer exists
- **Target:** OTO-01 phase 2

### L-050 — The Otodom filtered-listing contract is unverified; coverage relies on `pages_expected`
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** OTO-01 importer, `coverage_complete`, `docs/OTODOM-NIGHTLY-IMPORT.md` §4
- **Evidence:** inferred (nothing fetches yet; filtered listing operation, last-24-hours semantics, partitioning past 50 pages and timestamp meanings not checked live)
- **Description:** Publishing a location requires proven page coverage, which a future importer must supply as `pages_expected`. Until the live contract is verified (an owner-authorised request, L-002 applies), the value is not trustworthy. The verified 727-location catalogue artifact is also unidentified (B-023 item 4); nothing was seeded.
- **Workaround:** none; no import runs
- **Target:** `docs/OTODOM-NIGHTLY-IMPORT.md` §4, B-023 item 4
- **Update (2026-10-19, RM-392):** the client now has typed search options but refuses created-date filters until `filters_verified` is set; `createdAtFrom`/`createdAtTo` are guesses from the count query (L-070).

### L-051 — Media manifest is metadata only: no binary store, no population, no expiry sweep
- **Status:** active
- **Discovered:** 2026-10-17
- **Affects:** `app.media_evidence`, `GET /api/audits/{audit_id}/media`, G-01 gallery (`LEGAL[images]`, `LEGAL[republication]`)
- **Evidence:** confirmed (`tests/integration/test_media_manifest.py`); the retention gap is inferred from scope
- **Description:** The manifest contract, table and read route exist, but nothing fills the manifest: the worker does not write it, no binary store exists, `expires_at` has no sweep job and retention values are undecided. The route returns an empty manifest for every audit today.
- **Workaround:** none; no UI should present a gallery yet
- **Target:** G-01 follow-up slices; owner decision on binary storage (Postgres `bytea` for the beta or a private object store) and retention values

### L-053 — BDL response shapes are unverified against the live API
- **Status:** active
- **Discovered:** 2026-10-18
- **Affects:** `services/rm_worker/clients/bdl.py` (`variableId`, `results[].values[].attrId`, `measureUnitName`, `X-ClientId` header), LCTX-01b
- **Evidence:** inferred (public API description; no BDL call made)
- **Description:** The client and validator were built and tested offline against hand-built fixtures only.
- **Workaround:** none needed offline; no metric is selected or activated
- **Target:** one owner-authorised live BDL read (B-023), then LCTX-01b part 2

### L-054 — BDL request quota limits are not encoded and the gate is per process
- **Status:** active
- **Discovered:** 2026-10-18
- **Affects:** `SlidingWindowQuota`, BDL ingestion (LCTX-01b)
- **Evidence:** confirmed (code); the real limits for the key tier are unknown
- **Description:** Windows are caller-supplied; none are baked in. The gate is not shared across workers, and `BDL_API_KEY` has no field in `rm_core.settings`.
- **Workaround:** a single worker with conservative caller-supplied windows
- **Target:** LCTX-01b part 2 (Postgres-shared gate, setting, migration 0016)

### L-055 — Meaning of BDL `attrId` values is an unreviewed per-binding input
- **Status:** active
- **Discovered:** 2026-10-18
- **Affects:** `BdlMetricBinding`, which values count as valid, suppressed or invalid
- **Evidence:** inferred
- **Description:** The validator maps attribute ids per binding; no real binding is approved.
- **Workaround:** none; no binding ships
- **Target:** B-023 reviewed metric list

### L-056 — Location conflicts in the rental corpus are counted, not stored for review
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `rm_core.market_corpus.PgCorpus.record_offers`, OTO-02
- **Evidence:** confirmed (behaviour); the need for a review list is inferred
- **Description:** The first location assignment wins; conflicts are counted on the run and returned by `record_offers`, with no persistent list.
- **Workaround:** none
- **Target:** OTO-02 importer slice

### L-057 — Corpus `location_id` columns have no foreign key
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `market_offer.location_id`, `market_import_run.location_id`
- **Evidence:** confirmed
- **Description:** Locations are versioned (key `(catalogue_version, location_id)`), so no FK exists; `start_run` checks the id against any catalogue version.
- **Workaround:** repository-level check
- **Target:** revisit when a catalogue is seeded

### L-058 — Corpus source ids lose leading zeros
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `market_offer.source_offer_id` (`NUMERIC(20,0)`)
- **Evidence:** confirmed
- **Description:** The contract allows leading zeros; the column does not preserve them.
- **Workaround:** none known to matter for Otodom numeric ids
- **Target:** OTO-02 once real ids are seen

### L-059 — No retention job for the rental corpus
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `market_offer` (follows L-048)
- **Evidence:** confirmed
- **Description:** Archive state is derived from `expires_at` at read time; no rows are deleted.
- **Workaround:** none needed while the table is empty
- **Target:** OTO-03/OTO-04, with `GDPR[retention]` review

### L-060 — `market_import_item` and `market_daily_summary` are not built
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `docs/OTODOM-NIGHTLY-IMPORT.md` §5
- **Evidence:** confirmed
- **Description:** Only the five tables of migration 0015 exist.
- **Workaround:** none
- **Target:** OTO-03 and OTO-04

### L-061 — Equipment observations are unverified model claims
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `vision.equipment` (`sale_status`, confidence), report consumers
- **Evidence:** general accuracy unmeasured; one live `vision-v2` sample checked on 2026-10-19 (`docs/LIVE-VISION-ID4DACX-2026-10-19.md`)
- **Description:** `included` in a sale is a model claim; accuracy is unmeasured and the UI must not present it as fact. The live sample returned five `visible_only` observations, with two incorrect source-image references despite confidence 0.8; a successful provider call is not extraction/grounding accuracy proof.
- **Workaround:** none; no UI panel exists yet
- **Target:** #94 accuracy set, G-02b panels

### L-062 — OCR text and notes may contain personal data printed on a plan
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `vision.floor_plan_text`, `vision.notes` in `audit.result` (`GDPR[personal-data]`, `GDPR[erasure]`, `LEGAL[images]`)
- **Evidence:** inferred
- **Description:** Free text from a third-party model; the prompt forbids personal data in notes only. Stored with the audit, erased by cascade, retention follows the audit.
- **Workaround:** none
- **Target:** counsel review (B-012)

### L-063 — `media_ordinal` matches the media manifest only by convention
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `vision.equipment[].media_ordinal`, `app.media_evidence` (see L-051)
- **Evidence:** confirmed in code
- **Description:** Photos then plans in selected order; no foreign key, and the worker does not populate the manifest yet. In the 2026-10-19 live ID4DACX sample, intercom/doorbell references pointed to an exterior photo while the devices were visible in the preceding entrance photo. A one-based model index is a possible cause, not a proven parser offset; do not automatically subtract one from every reference.
- **Workaround:** none
- **Target:** G-01b media population

### L-064 — BDL unit-level numbers are inferred, not verified live
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_territory` level codes (gmina 6, powiat 5, voivodeship 2, country 0), LCTX-01b
- **Evidence:** inferred (with L-053)
- **Description:** Not checked against the live API.
- **Workaround:** none; nothing is ingested
- **Target:** one owner-authorised live BDL read

### L-065 — `BDL_REQUESTS_PER_MINUTE=10` is a placeholder cap
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `PgQuotaGate`, ingestion pacing
- **Evidence:** estimate
- **Description:** The real quota for the key tier is unknown. Sharing across workers is resolved (Postgres-shared gate); that half of L-054 is closed.
- **Workaround:** conservative default
- **Target:** owner confirms the key tier

### L-066 — The territorial reference has no loader
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_reference`, `ensure_reference`
- **Evidence:** confirmed
- **Description:** Hierarchy and TERYT crosswalk content must come from a reviewed source (B-023).
- **Workaround:** none
- **Target:** after B-023 reference-source decision

### L-067 — A failed BDL ingest run is terminal with no reset path
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_ingest_run`
- **Evidence:** confirmed
- **Description:** Bad data marks the run `failed`; an owner/ops decision on reset is needed.
- **Workaround:** none
- **Target:** ops decision

### L-068 — Source revisions of BDL observations are counted, not stored
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_observation` (insert-once)
- **Evidence:** confirmed
- **Description:** The first stored fact stays; a changed value counts as a conflict. A new-vintage policy is undecided.
- **Workaround:** none
- **Target:** owner policy

### L-069 — No scheduled cleanup of BDL run and quota rows
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_ingest_run`, `location_quota_stamp` (`GDPR[retention]`, no personal data)
- **Evidence:** confirmed
- **Description:** Only the gate prunes its own stamps.
- **Workaround:** none
- **Target:** ops retention job

### L-070 — Corpus window restarts re-read pages; page budget and deadline are constants
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `otodom_corpus.py` (RM-392), `sync_corpus_location`
- **Evidence:** confirmed (design); per-partition resume needs the unbuilt `market_import_item` (L-060)
- **Description:** A restarted window re-reads from its first page. Page budget 3000 and a 3600 s deadline apply, so a very large location may stay `incomplete` (visible, not published) across runs. The date-filter parameter names and boundary behaviour are unverified, so `filters_verified` stays false (see L-050).
- **Workaround:** none
- **Target:** OTO-02 live check; `market_import_item` slice

### L-071 — `createdAtFirst` as original publication time is unverified
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `RentalOffer` age anchor, 90-day archive dates of bootstrap offers
- **Evidence:** inferred
- **Description:** Used instead of `pushedUpAt` (never used). A wrong choice shifts archive dates.
- **Workaround:** none
- **Target:** owner-authorised live check

### L-072 — Unpublished runs leave offers visible; bootstrap lower bound is a constant
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `list_offers`, freshness readers; bootstrap lower bound `2010-01-01`
- **Evidence:** confirmed
- **Description:** Offers are inserted per page before a run is published. Readers must judge freshness from the checkpoint, not the offer table.
- **Workaround:** use the checkpoint
- **Target:** OTO-04 publication slice

### L-073 — Corpus scheduling knobs are module constants, with no import switch
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** cron (01:00 UTC), night window end 05:00 UTC, overlap 60 min, 7-day chunk, 23 h due-after, catalogue version 1
- **Evidence:** confirmed
- **Description:** No `OTODOM_MARKET_IMPORT_ENABLED`; the only kill switch is `LEGAL_SCRAPING_ENABLED`. Proposed names are in `docs/parallel-handoffs/RM-392.md`.
- **Workaround:** the dispatcher is inert until catalogue version 1 is seeded
- **Target:** settings slice (settings.py is free after #394)

### L-074 — Published days are immutable, so late-discovered offers miss past `additions`
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `market_daily_summary` additions series (`first_observed_count` holds the discovery-day count)
- **Evidence:** confirmed (design)
- **Description:** Offers found later by recovery appear only in later cohorts.
- **Workaround:** read `first_observed_count`
- **Target:** OTO-04 consumers

### L-075 — Backfilled cohort rows for old days reflect what was known at the bootstrap
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** cohort rows with `backfilled=true`
- **Evidence:** confirmed
- **Description:** Bootstrap offers are old but first seen on the bootstrap day, so early cohort days hold the whole bootstrap sample.
- **Workaround:** the `backfilled` flag is stored
- **Target:** OTO-04 consumers

### L-076 — No retention for daily history
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `market_daily_summary` (up to about 20 rows per location-day)
- **Evidence:** confirmed
- **Description:** No deletion job; the retention period is an owner decision.
- **Workaround:** none
- **Target:** owner decision, ops job

### L-077 — Sufficiency minimum and cohort bands are implementation constants
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `MIN_PRICED = 10` (also a CHECK), rooms and size bands, published median and quartiles per m2
- **Evidence:** confirmed; thresholds are not owner-approved (compare L-045)
- **Description:** Chosen by the implementer.
- **Workaround:** none
- **Target:** owner approval

### L-078 — `usable_for_ranking` ignores catalogue-wide completeness
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `PgMarketHistory.view`
- **Evidence:** confirmed
- **Description:** There is no catalogue-wide manifest of summary coverage yet.
- **Workaround:** none
- **Target:** OTO-04 consumers

### L-079 — Market settings are defined but mostly unread; the summary cron is a constant
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `OTODOM_MARKET_*` settings; `publish_market_summaries` cron `30 5 * * *`; importer constants (see L-073)
- **Evidence:** confirmed
- **Description:** Only `IMPORT_ENABLED`, `FRESH_HOURS`, `STALE_HOURS` and `CATALOGUE_VERSION` are read; the importer still uses its own constants.
- **Workaround:** none
- **Target:** follow-up wiring slice (resolves L-073)

### L-080 — Gmina values for powiat-native metrics are proxies
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `location_indicators.resolve_measured` direct/proxy labels
- **Evidence:** confirmed
- **Description:** A proxy names the unit actually measured; no property-grade claim and no financial multiplier. Whether rank and percentile wording is acceptable for proxies is undecided.
- **Workaround:** labels travel with every value
- **Target:** B-023

### L-081 — No composite index or cross-metric score
- **Status:** deferred
- **Discovered:** 2026-10-19
- **Affects:** LCTX-02b
- **Evidence:** confirmed
- **Description:** Blocked on the B-023 metric list, thresholds and composite policy.
- **Workaround:** none
- **Target:** B-023 approval

### L-082 — No database index tuned for rank reads
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `observations_for_years` (scans one metric-year)
- **Evidence:** estimate (fine at about 2.5k gminas, unmeasured)
- **Description:** Needs a migration slot after 0017.
- **Workaround:** none
- **Target:** when a metric is activated

### L-083 — Peer cohort is siblings under one parent only
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `compare_to_peers`
- **Evidence:** confirmed
- **Description:** Voivodeship-wide and size-band cohorts are undecided.
- **Workaround:** none
- **Target:** B-023

### L-084 — Boundary breaks are an input but nothing stores or loads them
- **Status:** active
- **Discovered:** 2026-10-19
- **Affects:** `trend`
- **Evidence:** confirmed
- **Description:** Territorial boundary changes cannot yet be applied from data.
- **Workaround:** caller supplies them
- **Target:** reference loader slice

## Deferred

### L-039 — Audit cancellation is in the blueprint but not built
- **Status:** deferred
- **Discovered:** 2026-10-16
- **Affects:** `POST /api/audits/{id}/cancel` (blueprint §2 route map and §4.5), the `cancelled` audit status, `docs/FRONTEND-PLAN.md` (no cancel button)
- **Evidence:** confirmed (OpenAPI has no such operation; `cancelled` exists as a status and in the failure paths)
- **Description:** The blueprint says cancel "sets `cancelled` and releases the credit if the job has not started". It does not say what happens to a running audit (kill the engine child? release or capture the credit?). That is a credit-ledger decision, so the route is not implemented and the SPA offers no cancel
- **Workaround:** an audit finishes or fails by itself within its 900 s deadline and the credit follows the existing outcome rules
- **Target:** owner decision (B-022), then a ledger-safe implementation with concurrency tests


### L-025 — V2 manual analysis and creative tools are local design flows
- **Status:** deferred
- **Discovered:** 2026-10-15
- **Affects:** `design/v2/new-analysis.html`, `interior.html`, `create-listing.html`, `app-pages.js`
- **Evidence:** confirmed (prototype source): local form validation, object-URL image previews, factual description template, generic guidance and CSS brightness preview; no backend or AI requests.
- **Description:** Manual/URL preflight does not run an analysis. Interior guidance and photo tips do not assess uploaded images. Listing text is a local template; image export, generation/enhancement and Otodom publication are absent. Form inputs, image previews and drafts have no persistence.
- **Workaround:** Review these as Phase 2 interaction prototypes; labels state the example/integration boundaries. Only fictional reports are linked.
- **Target:** Phase 2 UX and separately specified backend/provider integrations (blueprint §4.8 step 6); personal-data, image-processing and third-party publication review before integration.

### L-024 — V2 analysis collection and market views are placeholders
- **Status:** deferred
- **Discovered:** 2026-10-15
- **Affects:** `design/v2/analyses.html`, `design/v2/market.html`; Phase 2 UX handoff
- **Evidence:** confirmed (owner design assessment and prototype source review): twelve in-memory analysis fixtures with search/status filters; no pagination or table-view switch; three fictional city/rent summaries. The owner confirms substantially more market data is available than this view includes; completeness was not audited in this change.
- **Description:** The analysis cards are temporary, inadequately designed placeholders and will be replaced. The market view exists to avoid a blank page and omits the breadth of the project's market data. Neither view is an approved complete product design.
- **Workaround:** Use the prototype for navigation/appearance review only; see `design/v2/README.md` for explicit scope.
- **Target:** Phase 2 design (blueprint §4.8 step 6): replacement analysis cards, proper pagination, a table-view option and a fuller market information architecture. 2026-10-15 (#262): the market data lives in Postgres only; no `/api/market/*` route exists yet (#21), so the Rynek redesign (#282) waits on it; collection paging is #265.

## Resolved

### L-030 — Frontend session transitions do not consistently purge tenant state
- **Status:** resolved
- **Discovered:** 2026-10-15
- **Affects:** `frontend/shell/session.tsx`, `AccountBlock.tsx`, tenant query cache and progress streams
- **Evidence:** confirmed in code and a focused Vitest reproduction. **RM-301 (2026-10-15):** expiry, account switch and late answers now purge through one door (`shell/sessionTransitions.test.tsx`); **RM-302:** an unconfirmed sign-out stays visibly pending with a retry, also across reload (`shell/signOut.test.tsx`).
- **Description:** Session revalidation and changes of authenticated identity do not all pass through a cleanup boundary. Prior tenant queries can survive expiry/account switching; a failed sign-out may leave a valid cookie that restores the session. Browser-cache exposure is established; no backend authorization bypass was demonstrated. See frontend audit F02–F03 and F10.
- **Workaround:** Do not treat a failed network sign-out as confirmed revocation. Reloading clears in-memory query data but does not revoke a server session.
- **Resolved:** 2026-10-15, #322 (RM-301) and RM-302
- **Target:** #301 (session cleanup/cancellation), #302 (failed sign-out), before release #286; regression tests and remediation in `frontend/docs/AUDIT-2026-10-15.md`, tracker #314. Re-verified open on `staging` `5444eb8` (audit re-verification section).

### L-026 — Frontend collection and report typing need contract work
- **Status:** resolved
- **Discovered:** 2026-10-15
- **Affects:** `services/rm_api/audits.py` list endpoint, `packages/rm_contracts/audits.py`, Phase 2 collection/report implementation
- **Evidence:** `GET /api/audits` now pages by cursor with `status`, `grade` and `q` filters (RM-265, no total by design: an exact count under filters is a scan per request). `AuditOut.result` stays an opaque object in OpenAPI on purpose; its shape is `docs/deal-analysis.schema.json` (RM-266, `docs/REPORT-SCHEMA.md`).
- **Description:** Complete-history pagination/search cannot be implemented honestly by slicing the current capped response. OpenAPI generation alone does not produce typed internal report sections from the opaque result object.
- **Workaround:** Keep collection completeness explicit; design against separately labeled contract fixtures. Use a reviewed versioned report schema/adapter before rendering internal sections; do not bypass with unchecked casts.
- **Target:** Phase 2 frontend/API interface work (blueprint §4.8 step 6); pagination/search contract and report-version typing with integration tests. See `design/v2/implementation-guide.md` §5.
- **Resolved:** 2026-10-15: paging and filters by RM-265 (#265), the versioned report schema by RM-266 (#266); the frontend adapters (#268, #274) consume them.


### L-027 — OpenAPI does not describe the problem+json error responses
- **Status:** resolved
- **Discovered:** 2026-10-15
- **Affects:** `docs/openapi.json`, `services/rm_api/problems.py`, generated frontend types
- **Evidence:** confirmed in source: the API answers errors as `application/problem+json` (validation errors converted at `problems.py:138`), but the OpenAPI components contain no problem schema and operations advertise FastAPI's `HTTPValidationError` for 422.
- **Description:** A client generated from the schema gets wrong types for every error body, including 422, and cannot see which statuses or `code`s an operation returns.
- **Workaround:** None in production code; the frontend must not start before the schema is fixed.
- **Target:** #264 (FE-A1), before #268 (FE-02); plan in `docs/FRONTEND-PLAN.md`.
- **Resolved:** 2026-10-15, RM-264 (#264): `Problem` and `ProblemField` schemas, `HTTPValidationError` removed, every operation lists its error statuses as `application/problem+json` with `x-problem-codes`; `tests/unit/test_openapi_problems.py` and the strict smoke contract check keep it true.


### L-013 — Error events may carry stack-frame variables and unscrubbed free text
- **Status:** resolved
- **Discovered:** 2026-10-12
- **Affects:** `rm_core.observability` (every error event sent to Better Stack), auth handlers
- **Evidence:** confirmed (sentry-sdk 2.71 defaults `include_local_variables=True`; `scrub_event` was run on a sample event and left frame `vars`, breadcrumbs and `extra` untouched; the SDK's own denylist hides keys like `token` but not `email`, `credential` or a `url` holding a magic-link token)
- **Description:** An unhandled exception inside a sign-in or mail handler could send local variables with emails, Google credentials or links to Better Stack (GDPR[processor]).
- **Workaround:** none was needed: error tracking is off while `SENTRY_DSN` is empty, so nothing was ever sent.
- **Resolved:** 2026-10-12, RM-149: `include_local_variables=False`; `scrub_event` drops frame `vars`, breadcrumb data and `logentry` params, redacts emails, JWTs, bearer tokens and token-like URL parameters in messages, breadcrumb text, `extra` and the request URL, and drops the event if scrubbing fails.
- **Target:** #149 (must land before `SENTRY_DSN` is set); `docs/OBSERVABILITY-SPEC.md` section 1


_None yet._
