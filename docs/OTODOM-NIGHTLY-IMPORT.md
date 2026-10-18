# Otodom launch coverage: bootstrap, nightly new offers and 90-day archive

**Date:** 2026-10-14. **Purpose:** implementation guide for the city/import work tracked under #209,
with coverage and provenance work under #49 and #48. This document describes intended work, not delivered
capability. `STATUS.md` remains the delivery-state source. No new command, setting, table or job named below
exists until implemented and tested.

**Scope revision, 2026-10-16:** the owner confirmed this and GUS BDL as the **next implementation batch**. The completion target is **all locations in the verified 727-location catalogue**, persisted in Postgres with full bootstrap, nightly last-24-hours new-offer capture and durable daily trends. This supersedes the original largest-city launch-subset restriction below and the historical backend-only phase wording. See the [feature-gap batch and issue proposals](FEATURE-GAP-IMPLEMENTATION-GUIDE-2026-10-16.md#0-next-implementation-batch-rynek-data-and-location-context) and [BDL location-context contract](BDL-LOCATION-CONTEXT-CONTRACT.md). No job is installed or scraping run by this documentation change.

## 1. Owner decisions and scope

- The owner has verified the 727-location catalogue against Otodom. Use that catalogue; do not replace it
  with an inferred city list. Cover every catalogue location. Roll out in bounded groups if needed, but a
  largest-city subset is an intermediate state, not completion of this feature.
- GUS SIMC is useful for future identity validation, but is neither a bootstrap dependency nor a launch gate.
- Fetch all offers for each enabled location once, then fetch newly created offers every night using
  Otodom's last-24-hours filter. Read all pages of both full and incremental searches.
- Insert an offer once. Do not refresh its price, details or activity, and do not visit individual listing pages.
- Use **90 elapsed days**, not three calendar months, for age-based archiving. Archive means removed from
  the current analytical cohort; it does not mean rented, sold, deleted or confirmed inactive on Otodom.
- Preserve historical evidence for trend analysis. Launch scope is the existing flat-for-rent importer
  (`estate=FLAT`, `transaction=RENT`). Sale-asking data needs a separate pipeline and price basis.
- Phase 2 SPA work is authorized. Deliver the collection/publication contracts before the consuming
  Rynek UI; the frontend displays server results and does not calculate finance.

The catalogue's verification is owner-provided evidence. Its actual artifact has not
been located in this checkout during this review. Identify its source before writing a seed; do not
invent city names, location paths or copy the POC corpus. The target is the complete verified catalogue,
not an undecided subset. If the list lives in reference-only
POC material, resolve an approved data acquisition path rather than copying it under ADR 0001.

## 2. What has been verified

On 2026-10-14, two read-only requests from the development machine used the repository's
`CurlCffiTransport`, with bounded deadlines and no persistence:

| Request | Observed result | What it proves |
|---|---|---|
| Supplied `UnifiedCountAdsQuery`, Bydgoszcz, `daysSinceCreated=1` | HTTP 200; `data.unifiedCountAds.count=5` | The supplied persisted count query worked at that moment |
| Unfiltered Bydgoszcz rental search, page 1 | HTTP 200; pagination: 294 items, 36 per page, 9 pages; response contained 37 tiles | Search results contain IDs, rents, areas and pagination; tile count can differ from pagination size |

Search item keys included `id`, `totalPrice`, `rentPrice`, `areaInSquareMeters`, `roomsNumber`,
`createdAtFirst`, `dateCreated` and `pushedUpAt`. Their presence does not establish timestamp semantics.
The supplied persisted-query hash was
`608233a7d89412b20ab40ff8a98bb6ae1dd208428a699e258169d0c3a63647bb`.
It is an observed upstream identifier, not a stable public API contract.

**Not yet verified:** the filtered listing-results operation/URL, its pagination and sorting, date-boundary
behavior, wider recovery windows, timestamp meanings, large-city partitioning and sustained VPS traffic.
The count query does not return offers. Do not implement listing ingestion by treating its count as a list.

## 3. Existing integration points

| File | Existing behavior | Required change |
|---|---|---|
| `services/rm_worker/clients/otodom.py` | Validated location path, HTML search parsing, shared request slots, retries, breaker; max page 50 | Add typed full/new-offer search options and validate upstream pagination instead of silently capping completeness |
| `services/rm_worker/listing_source.py` | Injectable search source behind `LEGAL_SCRAPING_ENABLED` | Pass the new search options through the gated source |
| `services/rm_worker/importers/otodom_rental.py` | At most five pages, ID deduplication in memory, rent/area only, monthly replacement; fewer than ten usable rows rejected | Separate append-only ingestion from estimate eligibility; persist IDs; support complete paginated runs |
| `services/rm_worker/tasks/batch.py` | One on-demand import job | Add bootstrap, incremental and recovery jobs plus a daily dispatcher |
| `services/rm_worker/importers/demand.py` | Queue lock keyed by city and month | Replace launch-city monthly demand with checkpoint-based scheduling; avoid bypassing launch coverage |
| `packages/rm_core/comparables.py` | Latest monthly sidecar; hash-keyed cache | Load a successfully published daily cohort and its freshness metadata |
| `services/rm_worker/context.py` | Current-month data treated as current | Use latest successful refresh timestamp and sample quality |
| `packages/rm_contracts/jobs.py` | Shared task/queue names | Register new task names without making the API import worker code |
| `services/rm_worker/app.py` | Registers batch and ops task modules | Register any new task module |
| `deploy/compose.yml`, `deploy/compose.prod.yml` | `worker-ops` consumes `ops,batch` | Give `batch` a dedicated worker, leaving ops available for billing, mail and recovery |

Do not turn the existing audit `ListingSnapshot` into the market corpus: it contains raw seller payloads
with a separate retention policy. Search IDs are numeric; audit URL short IDs are strings. Do not join them
by assumption or coerce a numeric search ID into the existing listing identity without a verified mapping.

## 4. Verify the provider contract first

1. Inspect Otodom's actual search request when selecting flat rentals, one launch location and the
   last-24-hours filter. Record operation name, input schema, page controls and returned fields. Do not
   guess a GraphQL listing operation, a persisted hash or an HTML query parameter.
2. Verify page 1 and another page when available. Check the filter is applied on every page; exclude
   recommendations and out-of-location tiles from the corpus using validated fields. Deduplicate promoted IDs.
3. Establish which timestamp is original publication and which represents promotion or republication.
   Compare `createdAtFirst` and `dateCreated`; never use `pushedUpAt` as original publication by default.
4. Verify whether `daysSinceCreated=1` is a rolling 24 hours or a calendar-day filter. Check timezone and
   inclusive/exclusive boundaries, and whether existing offers can be returned after promotion.
5. Verify bounded `createdAtFrom`/`createdAtTo` or a wider relative-day filter for catch-up. Those input
   names appear in the supplied count request, but listing-query support remains unconfirmed.
6. Establish a complete bootstrap strategy for cities exceeding 50 pages: validated date or other disjoint
   partitions, a supported cursor, or supported pagination beyond that limit. A truncated run is not complete.
7. Reduce live responses to small hand-built, anonymised fixtures for offline tests. Do not store full
   seller responses, cookie headers or credentials in docs, fixtures or logs.

Keep count queries optional: if the listing response supplies adequate pagination, a separate count adds
traffic without supplying offers. A zero count is not evidence of an empty corpus unless the complete
listing response is valid and consistent with that search.

## 5. Proposed Postgres data model

> **Implemented contracts (RM-377):** `market_location`, `market_offer`, `market_import_run` and `market_import_checkpoint` are mirrored by `LocationEntry`/`LocationCatalogue`, `RentalOffer`, `ImportRun` and `LocationCheckpoint` in `packages/rm_contracts/market.py`; the migration should keep that mapping.

Implement expand-only Alembic migrations in the existing `app` schema. The names below are proposals.
Use typed repository methods, aware UTC timestamps and `Decimal`/`NUMERIC` for money.

| Table | Fields and constraints |
|---|---|
| `market_location` | Stable internal ID, display name, unique verified Otodom domain path, `launch_enabled`, catalogue source/version; optional SIMC later |
| `market_offer` | Source, transaction, estate, numeric source ID, location FK, advertised rent, area, optional rooms, optional validated original publication timestamp, `first_seen_at`, `age_basis`, `expires_at`, provenance run ID; unique `(source, source_offer_id)` for the current Otodom-only corpus |
| `market_import_run` | Location, mode (`bootstrap`, `incremental`, `recovery`), intended window, query start/finish, state, page checkpoint, pages expected/fetched, seen/duplicate/accepted/rejected counts, error category, completion evidence |
| `market_import_checkpoint` | One per location and dataset; bootstrap completion, last covered source window, last successful refresh, next due time and last published run |
| `market_import_item` | Run-owned staging rows, unique `(run_id, source_offer_id)`; bounded payload consisting only of whitelisted analytical fields |
| `market_daily_summary` | Unique location/dataset/UTC date; new-offer cohort and eligible 90-day cohort statistics, sample counts, coverage, input digest, calculation version and publication timestamp |

Index offers by `(location_id, expires_at)`, source ID uniqueness, due checkpoints and run state.
Keep `market_offer` content immutable: use `INSERT ... ON CONFLICT DO NOTHING`. Neither a retry nor a
later sighting changes its rent, original location, publication time, `first_seen_at` or expiry. Count duplicate
and conflicting sightings in run metadata without overwriting the offer. Flag location conflicts for review.

Separate content validity from price-estimate usability. An offer with a hidden/invalid price can have an
identity observation without entering priced comparables. Report observed IDs and usable rents separately.
Do not later fill missing values on an existing offer under the insert-only policy.

Age rules:

- `expires_at = validated_original_publication_at + 90 days` when that timestamp is usable.
- Otherwise `expires_at = first_seen_at + 90 days`, with `age_basis=first_seen` recorded explicitly.
- Reject malformed/future publication times as a source-date issue; use the documented fallback, never
  a naive datetime or an arbitrary timestamp silently substituted as original publication.
- At exactly `expires_at`, the offer is outside the current cohort. An old bootstrap offer can therefore
  enter history already archived. A duplicate ID never resets the clock or reactivates an expired offer.
- A new source ID is a new observation. It may be a relisted property; do not claim property-level deduplication.

Prefer deriving `archived_by_age` from `expires_at <= now()` so reads stay correct even if the nightly
maintenance job fails. Optional materialized archive markers belong in separate lifecycle metadata, not in
the immutable offer content. Archive is not physical deletion.

## 6. Bootstrap and nightly algorithms

### Bootstrap: once per enabled location

1. Idempotently seed the complete owner-verified catalogue. No name-only city keys. Track bootstrap
   and refresh status for every entry; disabled/not-yet-rolled-out locations still count as uncovered.
2. Create a durable bootstrap run with the location's dataset and source-window start time.
3. Fetch all validated search pages/partitions through the existing throttle, breaker and kill switch.
   Stage minimal fields; deduplicate IDs across pages. Persist progress between bounded page batches.
4. Do not hold a database transaction during network calls. Use explicit request and total chunk deadlines.
   The current 300-second import deadline is not a whole-large-city bootstrap budget.
5. Validate completion and account for pagination drift. Unexpectedly short/malformed pages or a cap must
   produce an incomplete run, not a successful truncated import. Do not assume page size equals tile count.
6. In one publication transaction, lock the location checkpoint, insert new offers, record completion,
   publish eligible comparables and summary, then mark bootstrap complete. Replays are idempotent.
7. Start the first incremental catch-up from the bootstrap's query start, with boundary overlap, not its
   finish. Otherwise offers created while bootstrap was running can fall into a gap.

Offset pagination on a changing website is not a point-in-time snapshot. Prefer a verified fixed upper
date bound and deterministic order. If unavailable, record the coverage limitation and overlap the handoff;
do not claim mathematically exhaustive coverage from a single changing paginated sweep.

### Normal nightly incremental run

1. Dispatcher selects only enabled, bootstrapped locations due for refresh. Capture a UTC target time and
   create a durable run; unique run keys and a per-location execution lock prevent concurrent publication.
2. Fetch every page matching the last-24-hours creation filter. Do not stop at an already known ID:
   promotion, repeated tiles and unstable ordering can put unseen IDs on later pages.
3. Stage and validate results, including valid empty searches. A city with zero new offers is a successful
   refresh; the existing `MIN_ROWS=10` gate must not discard it.
4. Publish inserts and the covered-window checkpoint atomically after all pages complete. Failed or
   partial runs preserve the prior checkpoint and published cohort. Resume/retry using the same window.
5. Compute that day's new-offer statistics and the surviving 90-day cohort. Publish freshness metadata
   even if no offers were inserted and the content digest is unchanged.
6. Apply the age cutoff locally. No listing checks, removed-offer reconciliation, price updates or daily
   full sweeps are part of this policy.

### Delays, downtime and window boundaries

A nightly cron alone does **not** guarantee contiguous 24-hour coverage. If a city runs at 02:10 today
and 02:25 tomorrow, tomorrow's rolling-24-hour query misses 15 minutes. Retries and queue waits can
cause this even when the dispatcher fires precisely every day.

- Track source-window coverage per city; the job's completion time is not a coverage watermark.
- Normal runs use the 24-hour filter. When the previous covered interval does not reach the next window,
  use a verified wider/date-bounded recovery query with a small configurable overlap, then insert only
  unknown IDs. Recovery may return existing offers, which remain unchanged.
- Freeze a recovery run's intended bounds. Rolling queries move with each request; do not advance the
  checkpoint past a range you can prove covered. Verify per-page boundary behavior in section 4.
- Add a startup/periodic due-checkpoint reconciler. In the installed Procrastinate implementation, the
  periodic deferrer defaults to ignoring schedules older than ten minutes; do not rely on cron to replay nights.
- If wider queries are unsupported, leave the gap visible and checkpoint unresolved. A rate-limited,
  explicit full catch-up can insert missing IDs without updating existing offers; do not silently claim
  continuous coverage or introduce routine full refreshes as a substitute for the agreed nightly policy.

## 7. Scheduling and server configuration

Proposed nightly dispatcher: **01:00 UTC**, equivalent to 02:00 Warsaw in winter and 03:00 in summer.
This keeps a fixed daily interval and avoids DST duplication/gaps. Verify the actual scheduler timezone
against the installed library and test timestamps; record the configured time in the runbook.

Use the existing `@app.periodic` / `@app.task` pattern. The short dispatcher belongs on `ops`; fetch jobs
belong on `batch`. Add `worker-batch` with concurrency 1 and remove `batch` from `worker-ops`.
Bootstrap and recovery use bounded chunks so one large location cannot monopolize the entire night.

Honor the existing shared one-request-per-second host slot and interactive audit priority. Nighttime is
a preference, not evidence that user requests or provider limits disappear. Set an end-of-night request
budget/window; jobs that cannot finish remain resumable and overdue. Do not mark them complete or
increase concurrency to get around provider blocking. Alert when the launch subset consistently exceeds
the available window. Measure page totals and response times before setting the final budget.

Proposed settings to add to `rm_core.settings`, `.env.example` and the deployment runbook:

| Setting | Proposed value/purpose |
|---|---|
| `OTODOM_MARKET_IMPORT_ENABLED` | Default-on gate for installed market import capability; independent of audit fetching |
| `OTODOM_MARKET_NIGHTLY_CRON` | `0 1 * * *`, UTC; verify validated registration with the installed Procrastinate API |
| `OTODOM_MARKET_NIGHT_WINDOW_END_UTC` | `05:00`; stop issuing normal batch fetches and retain remaining work |
| `OTODOM_MARKET_ARCHIVE_DAYS` | `90`; documented policy version, not a provider inactivity claim |
| `OTODOM_MARKET_OVERLAP_MINUTES` | `60`, initial recovery margin; subject to verified upstream date granularity |
| `OTODOM_MARKET_REQUEST_BUDGET` | Set from measured launch pages; never an implicit completeness cap |
| `OTODOM_MARKET_FRESH_HOURS` | `36` |
| `OTODOM_MARKET_STALE_HOURS` | `72` |

These are proposed names, not settings operators can use today. The catalogue defines launch enablement;
do not duplicate city scope in a separate environment variable. `LEGAL_SCRAPING_ENABLED` remains the
global fetch gate; in current deployments changing environment settings requires worker restart/recreation.
No credentials are required for this guide; never read or copy `.env` values.

Update blueprint resource/connection budgets when adding the worker; keep peak DB connections below
the repository's limit. Document the approved queue split in the implementation PR/ADR. Deploy only from
a commit merged to `staging`, following `PRE-DEPLOYMENT.md` and `RUNBOOK-DEPLOY.md`.

## 8. Comparables, trends and freshness

The 90-day cohort is a **rolling collection of original asking rents**, not a verified set of active offers.
Early withdrawals remain until expiry; price reductions on existing IDs are intentionally not captured.
New-ad counts measure observed source IDs, not unique properties or completed rental transactions.

Keep two distinct daily datasets:

- **New-offer cohort:** newly published offers captured for that source date, with a separate count of
  all IDs first observed today. A recovery day must not attribute all late observations to today's publication.
- **90-day cohort:** stored offers whose `expires_at` is later than the summary's cutoff, using original
  prices. Exclude invalid prices from estimates and publish observed/priced counts separately.

Implement financial/statistical calculation helpers in `apps/deal_analyzer`; worker/repositories persist
their typed outputs rather than deriving financial numbers themselves. Preserve `totalPrice` as the
advertised rent according to the verified source contract; `rentPrice` is admin fee/OPEX, never income.
Do not blend rent, sale asking and deed data. Persist calculation version and input provenance.

Use daily dates for newly published sidecars (or an explicit daily grain introduced by migration).
Do not overwrite the same monthly sidecar every night and lose history. Before using existing `period`
for daily dates, inventory all consumers; remove `month_start` freshness assumptions and avoid mixing
legacy monthly rows with new daily data. A one-time bootstrap can supersede the legacy sample without
pretending its missing listing IDs can be reconstructed.

Expose `last_successful_refresh_at`, last covered window, snapshot date, launch coverage, observed/usable
counts, archive policy and `data_status`. Unchanged content must still get a new successful refresh timestamp.
Ensure the SHA cache handles expiry: a cohort digest changes when offers age out even without insertions;
freshness metadata must be read independently of cached prices.

| Refresh age / coverage | Reader behavior |
|---|---|
| At most 36 hours, no unresolved source-window gap | Fresh new-offer coverage |
| Over 36 and at most 72 hours | Delayed; show timestamp and reduced confidence |
| Over 72 hours or unresolved coverage gap | Stale/incomplete; exclude from fresh rankings; audit estimate explicitly degraded or refused according to engine policy |
| Bootstrap pending | Unavailable; no invented market estimate |
| Valid refresh, too few priced observations | Fresh ingestion, insufficient evidence for a reliable estimate |

User-facing text: “New offers checked at …”, “Original asking rents collected over 90 days”, and
“Archived by age”. Do not say “All offers are active” or “Prices updated today”. Audit results preserve
their original evidence; a market refresh does not rewrite completed audits. Define freshness fields in
contracts and regenerate OpenAPI if routes change; frontend implementation remains Phase 2.

Archive retention is a separate decision: 90 days controls analytical eligibility, not deletion. Retain
minimal archived observations and daily summaries initially; define a bounded physical retention/erasure
policy before the corpus grows, without inventing a seller-data retention period. Do not persist seller
names, phones, descriptions or photos. Add source/runtime legal tags for scraping, third-party reuse and
republication where applicable; carry the current kill switch through every new fetch path.

## 9. Required offline tests

Use fake HTTP responses, a frozen clock and real Postgres 17 for persistence/concurrency. Extend existing
`tests/unit/test_rental_search.py` and `tests/integration/test_rental_importer.py`; add focused scheduling,
archive and context tests. Never weaken an invariant to accept an upstream payload.

- Full/filtered URLs and query options validated; every page preserves location and creation filters.
- Duplicate and promoted IDs across pages insert once; conflicting prices never overwrite existing values.
- Concurrent imports of the same city and overlapping runs publish exactly once with safe checkpoints.
- Pagination beyond five pages; over-50-page bootstrap strategy; capped/short/schema-drift runs stay incomplete.
- Zero new offers completes successfully; thin priced samples persist ingestion and yield insufficient evidence.
- 403/429, `Retry-After`, captcha, timeout, cancellation and kill switch keep checkpoint/publication unchanged.
- Crash after staging resumes; crash during publication rolls back; duplicate delivery does not reset offer age.
- Publication-date fallback, future/malformed times, old bootstrap rows, exact 90-day boundary, leap day and DST.
- Expired offers are excluded even if maintenance did not run; re-seen expired ID stays expired.
- No individual listing request during bootstrap, incrementals, catch-up or archive.
- Delayed city start and missed nights select wider recovery bounds; unsupported recovery leaves a visible gap.
- Dispatcher/reconciler/startup overlap does not enqueue overlapping work; pending bootstrap cannot run incrementals.
- Known IDs on page 1 do not stop pagination; excluded recommendations do not count as local offers.
- Unchanged or empty refresh advances freshness; failed refresh does not. Cache changes at expiry without inserts.
- Daily history survives later runs; recovery observations retain source dates; archived rows stay out of current estimates.
- Admin fee remains OPEX, asking is not deed, and tenant-owned API access continues through `Principal` repositories.

Before pushing implementation: `make lint`, `make types`, `uv run pytest -m "not e2e"`, migration tests and
`squawk`, plus required repository CI gates. All ordinary tests stay offline. Provider probes are explicit,
bounded verification and must record location, date, status, sanitized contract evidence and limitations.

## 10. Delivery sequence and operator acceptance

1. Identify the complete catalogue artifact; verify filtered list/date/pagination contract and planned
   coverage for every catalogue location. No launch-subset decision is outstanding.
2. Add schemas, repositories, immutable offers, staging and durable runs/checkpoints; test concurrency.
3. Add resumable full bootstrap and filtered incremental/recovery clients behind existing policies.
4. Add daily dispatcher, due-work reconciler, local expiry handling and dedicated batch worker.
5. Publish daily evidence, engine cohort calculations and reader freshness; retire monthly launch-city demand.
6. Update blueprint/ADR as required, `CONTEXT.md`, `.env.example`, `LIMITATIONS.md`, changelog and runbook
   in the relevant implementation PRs. Record delivery levels only in `STATUS.md` with named evidence.

**Completion evidence:** a catalogue-wide manifest accounts for all 727 owner-verified entries (or an
explicitly reviewed replacement catalogue version), including successful-empty, incomplete and failed
locations; uncovered locations prevent a full-coverage claim. Rehearse nightly dispatch, missed-window
recovery, restart/resume and a no-new-offer day. Verify durable daily history and reader freshness through
the API and Rynek, with source dates and coverage visible. Full coverage is a demonstrated property, not
the number of queued jobs. Link the feature-gap OTO-01–04 proposals and BDL LCTX-01–03 to real issues
before implementing; these proposal labels are not GitHub issue numbers.
7. Deploy to the authorized beta VPS from merged `staging`; canary a small launch subset before enabling
   all already-selected launch locations. This rollout does not expand geographic scope.

Operator tooling to implement (names/options to be finalized and documented, not runnable commands yet):
catalogue validation/seed, bootstrap enqueue, run status/coverage report, resume/recovery enqueue and
publish/rebuild summaries from stored inputs. Tools must be idempotent, validate location IDs and avoid
direct DB secrets or raw payload output. A rebuild preserves offer content and historical summary versions.

Acceptance evidence must show: one complete bootstrap; a subsequent filtered night; duplicate preservation;
a valid empty run; forced failure without watermark movement; successful catch-up; 90-day cutoff without
network calls; audit/ops availability during batch work; measured request totals; and dated data freshness.
Do not claim load safety from the two development probes in section 2.

Monitor per-location bootstrap state, last successful coverage, oldest due job, run failures, requests,
429/403 rate, breaker state, accepted/rejected rows and backlog. Notify on a missed window, schema drift,
coverage gap or repeated night-budget overrun; successful empty nights should not page an operator.
If blocking rises, pause market fetches, preserve data and checkpoints, and resume within the verified
recovery strategy. Do not wipe volumes, reset IDs or repeatedly bootstrap to conceal missing intervals.

## References

- [Repository architecture](BLUEPRINT.md), [delivery state](STATUS.md), [current limitations](LIMITATIONS.md)
  (especially L-002 and L-022), [deployment runbook](RUNBOOK-DEPLOY.md).
- [GUS locality catalogue downloads](https://eteryt.stat.gov.pl/eTeryt/rejestr_teryt/udostepnianie_danych/baza_teryt/uzytkownicy_indywidualni/pobieranie/pobieranie.aspx):
  SIMC identifies localities and WMRODZ describes locality types; later identity validation only.
- Existing source files listed in section 3; `tests/unit/test_rental_search.py`,
  `tests/integration/test_rental_importer.py`, and the installed Procrastinate `periodic.py` for the
  scheduler catch-up observation. Verify library behavior again when implementation changes its version.
