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
- **Evidence:** inferred (no test from OVH ranges)
- **Description:** Unknown whether OVH VPS addresses are blocked.
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
- **Evidence:** inferred (path `props.pageProps.ad` with a truthy `id` was confirmed only from reading the POC; never fetched live from this repo)
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
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** blueprint Caddy `Content-Security-Policy` (`connect-src`), the SPA analytics loader (Phase 2), B-002
- **Evidence:** confirmed (the script served at `https://cloud.umami.is/script.js` on 2026-10-12 posts to `https://gateway.umami.is/api/send`; the blueprint `connect-src` lists only `https://cloud.umami.is`); whether the script host ever changes is unverified
- **Description:** With the blueprint CSP the browser would block every analytics event while the script itself loads. The blueprint is not edited until the maintainer decides (`rules/architecture.md`).
- **Workaround:** none needed in Phase 1 (no frontend). Options: allow `https://gateway.umami.is` in `connect-src`, or proxy events through our own domain.
- **Target:** #143 (`docs/ANALYTICS-SPEC.md` section 2 lays out both options); decide before the Caddy config (#15) and N-30 (#72)

### L-014 — RPO 5 minutes and RTO 1 hour are targets, never measured
- **Status:** active
- **Discovered:** 2026-10-12
- **Affects:** backups (WAL-G to R2, nightly dump), release gate 6 (#37), the privacy notice, PRE-DEPLOYMENT section 6
- **Evidence:** estimate (blueprint §4.7 calls them "targets, unverified until the first timed point-in-time restore" and says WAL-G was not tested against R2; only a 55-byte upload and read-back to R2 is confirmed, B-005c)
- **Description:** No WAL-G archive, base backup, lifecycle rule or restore has run against R2. Every statement of RPO or RTO is a target.
- **Workaround:** none; say "target" wherever it is stated. The local logical drill (`scripts/backup_drill.sh`) covers only the dump path.
- **Target:** gate 6 (#37), `docs/R2-SPEC.md` section 5; #15

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
