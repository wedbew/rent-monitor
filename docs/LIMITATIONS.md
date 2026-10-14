# Limitations register

Entry format and rules: `.agent/rules/limitations.md`. IDs never reused. Seeded from blueprint "Limitations to carry into planning" and §5.

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
- **Evidence:** inferred (default hosts `olxcdn.com`, `otodom.pl` were not verified against a live listing; the per-call estimate of 0.02 USD is a placeholder)
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
- **Description:** Crash recovery, the killable engine child and the SSE stream are built and tested offline (RM-185, RM-186). The real Otodom client and market context are wired behind `AUDIT_PROVIDERS=real` (RM-187) but have only run against a fake transport; one live fetch was confirmed for payload shape (L-005). The comparable-rent store is filled on demand by the rental importer (RM-240, L-022); the first audit in a city still gets the engine's refused rent (rent 0, warning `rent_refused_too_few_comparables`). The risk-free rate is an owner-supplied `RISK_FREE_RATE` (unset: `CONTEXT_UNAVAILABLE`). The vision and OCR stages are not called, so every success is `succeeded_degraded` (`VISION_UNAVAILABLE`). The analyst audit is refused (403).
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
- **Target:** #209 (city list, coverage policy #49), accuracy evaluation #94

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

## Resolved

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
