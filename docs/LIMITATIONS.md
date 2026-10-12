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
- **Workaround:** Log tokens and USD per audit from day one; monthly budget kill-switch.
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

## Resolved

_None yet._
