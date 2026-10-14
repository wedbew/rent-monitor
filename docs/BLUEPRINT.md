# RentMonitor SaaS — Architecture & Implementation Blueprint

Oct 11, 2026 · @Marcin B

> **Pilot billing direction, owner 2026-10-13:** use one-time Paddle packs of 1, 5 and 10 reports,
> without subscriptions or 30-day passes. [PADDLE-INTEGRATION.md](PADDLE-INTEGRATION.md) defines
> the implementation design and recommended pricing (final prices pending). Older Stripe subscription,
> pass, invoice-outbox and associated billing-gate sections below are historical for this pilot;
> reconcile their detailed schemas/routes/tests in the implementation PR. Product approval and Polish
> accounting/KSeF review remain required; other architecture and engine invariants are unchanged.

## Executive verdict

Ship RentMonitor as a single 12 GB VPS running Docker Compose, with Postgres as the only stateful service — no Redis. Infrastructure lands at 52.20 zł net/month (≈ $13.38) against a $20 ceiling, dropping to 44.37 zł (≈ $11.37) once committed for 12 months. OpenRouter vision spend is cost of goods, not infrastructure, and is governed by the credit ledger.

**Not launch-ready until the seven release gates in Section 6 pass.** The architecture holds; the remaining work is proving its guarantees under concurrency, load and a real restore.

| Decision | Choice | Why it wins |
| --- | --- | --- |
| Host | One OVHcloud VPS-3 (6 vCore, 12 GB, 100 GB NVMe), Poland location, 52.20 zł net/month without commitment; commit to 12 months (44.37 zł) in the Black Friday window | Most RAM per złoty of the options checked, monthly exit, daily backup included. Splitting Postgres and the app across two cheaper VPS costs more for the same 6 vCore / 12 GB (Section 1) |
| Runtime | **Python only** on the server: FastAPI, Procrastinate workers, Postgres. Node exists only at build time to bundle the SPA | One language, one image, one migration tool, one test suite |
| Topology | Option B: Caddy + FastAPI + 2 worker pools + Postgres 17 | One bill, one failure domain you control, no cold starts, no per-invocation pricing |
| Frontend | Keep the existing Vite + React 19 SPA, served by Caddy on the same origin | Same-origin cookies, no CORS, no SSR runtime to host |
| Sign-in | **Google first**: "Zaloguj się przez Google" button at the top of every auth screen plus One Tap on the landing page; email magic link as the secondary path; email and password added by owner request (ADR 0013) | One click for most users, nothing to reset or leak; Google-verified emails unlock the 3 free audits at once |
| Auth engine | In FastAPI: Google ID-token verification with `google-auth`, own sessions in Postgres | No second runtime; FastAPI-Users is in maintenance mode and password-centric; cookies work with `EventSource` |
| Payments | Pilot: **one-time Paddle packs of 1, 5 or 10 reports**, card + one-time PLN BLIK; no subscription | Owner direction 2026-10-13; see `PADDLE-INTEGRATION.md`. Provider/product acceptance and final pricing pending |
| Job queue | Procrastinate (Postgres-backed, async) | arq is in maintenance-only mode; Celery + Redis costs a stateful service for no gain at this scale |
| Progress | SSE fed by Postgres `LISTEN/NOTIFY` + an `audit_event` table for replay | Survives reconnects via `Last-Event-ID`; no broker |
| Billing ledger | Pilot: completed Paddle transaction grants report credits; append-only ledger with purchase provenance | Transaction-keyed idempotency; report packs replace monthly allowances and timed passes; see `PADDLE-INTEGRATION.md` |
| Persistence | SQLAlchemy 2.0 (async, psycopg 3) + Alembic, one `app` schema; JSONB for `DealAnalysis` and sidecars, typed columns for what you filter on | One store for users, business data, documents and the queue |

**Confirmed vs inferred.** Prices, quotas and library status below were read from vendor pages on 11 Oct 2026 and are linked in Sources. Memory caps, latency figures and per-audit cost are engineering estimates — each is labelled *estimate* and has a measurement step in the blueprint.

**Limitations to carry into planning:**

- Commercial scraping of Otodom is a terms-of-service and EU database-right exposure, not only a technical one. Get Polish legal advice before charging for it; this document is not legal advice.
- A datacenter IP may be blocked by Otodom. I have no evidence either way for OVH's ranges — test before launch (Section 2 has the error contract).
- Per-audit OpenRouter cost is unknown here. The Pro allowance (40 audits/month below) is a placeholder until you measure it.

## 1. Architecture and deployment bake-off

Option B wins: both options can fit $20, but only B has a fixed bill, no cold starts, and runs the 727-city batch natively. Option A spreads one product across four metered vendors.

### Option A — hybrid serverless

| Component | Vendor and tier | Quota or rate (verified 11 Oct 2026) | Monthly cost at launch scale |
| --- | --- | --- | --- |
| Static SPA | Cloudflare Pages (free) | Vercel Hobby is excluded: its terms restrict Hobby to non-commercial use; Vercel Pro alone would eat the budget | $0 |
| Postgres | Neon Free | 100 CU-hours per project, 1 GB storage per project, suspends after 5 min idle (cannot disable), 5 GB egress | $0 while it fits; Launch is $0.106/CU-hour + $0.35/GB-month, so an always-on 0.25 CU is ≈ $19.35 |
| API + workers | Modal Starter | $30/month credits; CPU $0.0000131 per physical core-second, memory $0.00000222 per GiB-second, min 0.125 cores | One 3-minute audit at 1 core + 2 GiB ≈ $0.003 (*estimate* of runtime). An always-warm 1 core + 1 GiB API ≈ $40 — above credits, so the API must scale to zero |
| Queue / progress | Modal spawn + Upstash or Neon | — | $0 |
| Total |  |  | $0–20, but variable |

What breaks Option A for this product:

- **Cold starts stack.** A first request after 5 idle minutes waits for Neon to resume and for a Modal container to boot. I have not measured either; budget seconds, not milliseconds, until you benchmark.
- **The 1 GB Neon free storage is tight.** Raw `_next/data` snapshots, 727 cities × 4 sidecar families × monthly periods, and `DealAnalysis` JSONB will cross it within months (*estimate*).
- **Long batch jobs fight the model.** The 727-city refresh and screener sweeps are hours of rate-limited I/O; on Modal that is paid wall-clock spent sleeping between polite requests.
- **Four consoles, four failure modes, four billing alerts.** Developer velocity drops as soon as something fails between vendors.

### Option B — single VPS, Docker Compose, Caddy

All services run on one OVHcloud VPS-3 (6 vCore, 12 GB RAM, 100 GB NVMe, 2 Gbps unmetered) in the Poland location. The frontend is not a separate container: `vite build` output is baked into the Caddy image and served from the same origin as the API. Redis is dropped because Procrastinate keeps the queue in Postgres.

&#91;embedded content: Option B topology · 6 containers, 1 stateful\]

Every container talks to Postgres and nothing else stateful; only the workers and the backup job reach the outside world.

Resource matrix — limits sum to ≈ 9.9 GB of 12 GB leaving about 2 GB for the kernel, Docker and page cache. That makes a host-wide OOM unlikely, not impossible: limits are per-container ceilings, mem\_reservation is only a soft hint, and the margin stays unmeasured until the Section 6 load test; a runaway worker hits its own cgroup limit, is killed, and Procrastinate retries the job.

| Service | Role | `mem_limit` (12 GB, OVH VPS-3) | `mem_reservation` | `cpus` / `cpuset` | `oom_score_adj` | 8 GB fallback limit |
| --- | --- | --- | --- | --- | --- | --- |
| `postgres` | Postgres 17: app data, auth tables, job queue | 3 GB (`shared_buffers=768MB`, `effective_cache_size=5GB`, `work_mem=8MB`, `max_connections=100`) | 2 GB | 2.0 / `0-5` | -900 | 2 GB (`shared_buffers=512MB`) |
| `worker-audit` | Procrastinate, queue `audit`, concurrency 1 at launch (2 only after the memory load test) | 3 GB | 1.5 GB | 3.0 / `2-5` | 500 | 2 GB, concurrency 2 |
| `worker-batch` | Queues `city_refresh`, `ranking`, `screener`, concurrency 1 | 2 GB | 512 MB | 1.5 / `4-5` | 600 | 1.5 GB |
| `api` | FastAPI on uvicorn, 3 workers | 1.5 GB | 768 MB | 2.0 / `0-5` | 0 | 1 GB, 2 workers |
| `caddy` | TLS, static SPA, reverse proxy | 128 MB | 64 MB | 0.5 / `0-5` | -500 | 128 MB |
| `backup` | Nightly `pg_dump` to R2 | 256 MB | — | 0.5 | 800 | 128 MB |

Memory rules that make the matrix hold:

- Set `memswap_limit` equal to `mem_limit` on every container, so a leaking worker dies fast instead of thrashing the disk Postgres reads from.
- Keep a 2 GB host swapfile with `vm.swappiness=10` as a last-resort buffer for the host, not for containers.
- `cpuset` partitions the guest scheduler only. I have not confirmed whether OVH VPS vCores are dedicated or shared; treat them as shared. A cpuset of 0-5 on Postgres and the API means "unrestricted", not reserved: the only guarantee is that both worker pools are confined to cores 2–5 and can never run on 0–1. CPU quotas (cpus) cap consumption; they reserve nothing for anyone else. Pinning keeps cores 0–1 free of worker load for Postgres and the API but cannot guarantee physical isolation.
- The 12 GB box lets `worker-batch` run in daytime. On the 8 GB fallback, confine it to 02:00–06:00 Europe/Warsaw.

### Monthly cost, Option B

| Line | Tier | Monthly cost |
| --- | --- | --- |
| VPS | OVHcloud VPS-3, no commitment (now) | 52.20 zł net = 64.21 zł gross ≈ $13.38 net / $16.45 gross |
| VPS after commitment | OVHcloud VPS-3, 12 months (−15%) | 44.37 zł net = 54.58 zł gross ≈ $11.37 net / $13.99 gross |
| DNS, CDN, TLS edge | Cloudflare free | $0 |
| Off-site backups | Cloudflare R2: 10 GB-month, 1M Class A and 10M Class B ops free, zero egress | $0 up to 10 GB |
| Errors and uptime | Better Stack free (ADR 0009): 100k exceptions/month (90 days), 10 uptime monitors, 10 heartbeats, 1 status page, 3 GB logs/month (3 days); errors sent with the Sentry SDK | $0 |
| Product analytics | Umami Cloud Hobby: 100K events/month, 1 website, 6-month retention | $0 |
| Transactional email | Resend Free: 3,000 emails/month, 100/day | $0 |
| **Total now** |  | **≈ $13.38 net (≈ $16.45 gross)** |

Conversions use the NBP table A rates of 9 Oct 2026: 1 USD = 3.9022 zł, 1 EUR = 4.3775 zł. The net figure is the real cost if the company deducts input VAT.

The domain is excluded (not priced here). Headroom under $20 is ≈ $6.60 net now, or ≈ $3.55 if VAT is not recoverable. That is enough for a residential-proxy trial if Otodom blocks the datacenter IP, but not for a second VPS as staging. Use a local Compose stack as staging instead.

### Hosting comparison and purchase plan

OVH VPS-3 replaces netcup as the primary host: 50% more RAM and vCores than netcup's 8 GB VPS 1000 G12, Polish datacenter, Polish invoicing in zł, and no 12-month lock-in to start.

| Option | vCore | RAM | NVMe | Term | Monthly price | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **OVHcloud VPS-3** | 6 | 12 GB | 100 GB | none | 52.20 zł net | **Chosen** — fits budget, monthly exit, daily backup included |
| OVHcloud VPS-3, 12-month commitment | 6 | 12 GB | 100 GB | 12 months | 44.37 zł net | Target after promo window |
| netcup VPS 1000 G12 | 4 | 8 GB | 256 GB | 12 months | €8.45 gross (DE VAT) | Fallback; cheaper but less RAM and a year lock-in |
| netcup RS 1000 G12.5 | 4 dedicated | 8 GB | 128 GB | 1 month | €25.84 incl. 23% VAT | Rejected: ≈ $29, over budget |
| Hetzner CPX22 | 2 | 4 GB | — | hourly | €19.99 net | Rejected: half the RAM at a higher price |

What I verified about the plan to buy monthly now and commit around Black Friday or Cyber Monday (27–30 Nov 2026):

- **Confirmed:** OVH's control panel lets you add a commitment to a no-commitment VPS (`My offer` → `Commit`), for eligible VPS ranges. The commitment **starts at the next renewal date**, not immediately. OVH's guide also describes commitments as billed annually up front, which conflicts with the order page's monthly-discount wording; check which applies in your panel before committing.
- **Confirmed:** the 12-month rate is 44.37 zł net, exactly 15% below 52.20 zł.
- **Not confirmed:** whether a Black Friday price can be applied to an existing VPS. OVH's 2025 Black Friday page states no conditions for VPS. My inference is that such promos target new orders, so expect to order a **new** promo VPS and migrate rather than convert the current one.
- **Cost of waiting:** about 7.83 zł net per month versus committing today, so ≈ 16 zł by the end of November. A promo only wins if it beats 15% by more than that over the term.

Purchase steps:

1. Order VPS-3 with **no commitment**, location **Poland** (not Gravelines, the configurator default in your screenshot). Confirm the Polish location shows the same 52.20 zł; OVH's English Poland page quotes VPS-3 at $12.32 from, which does not match 44.37 zł at today's rate, so the price may differ by location.
2. Choose Ubuntu 24.04 LTS rather than 26.04 for the first deploy: Docker and Postgres images are most tested on the previous LTS (*inference*).
3. Build with the provider-agnostic bootstrap in 4.4. Nothing in the stack depends on OVH.
4. In the promo window: if the deal applies to the existing VPS, commit in the panel. If it applies only to new orders, buy the promo VPS and migrate with the recovery runbook in 4.7 — this doubles as your first timed restore drill. Cancel the old VPS only after DNS has pointed at the new one for 48 hours.
5. If no promo beats 15%, commit the existing VPS to 12 months at 44.37 zł.

### Two cheaper servers instead of one? No

Splitting Postgres onto a VPS-1 and the app onto a VPS-2 buys exactly the same 6 vCore and 12 GB as one VPS-3, for more money, with a network hop between every query and two machines to run.

| Layout | vCore | RAM | NVMe | Monthly, no commitment (net) | 12-month (net) |
| --- | --- | --- | --- | --- | --- |
| **One VPS-3** | 6 | 12 GB | 100 GB | **52.20 zł** | **44.37 zł** |
| VPS-1 (Postgres) + VPS-2 (app) | 2 + 4 | 4 + 8 GB | 40 + 75 GB | 19.20 + ≈ 36.20 = ≈ 55.40 zł | 16.32 + 30.77 = 47.09 zł |

VPS-1 at 19.20 zł comes from your screenshot. The VPS-2 monthly price is derived (30.77 ÷ 0.85), because the 15% gap holds for VPS-1 and VPS-3; check it in the configurator.

What the split would cost you:

- **Rigid memory.** Postgres is boxed into 4 GB (minus the OS) while spare RAM on the app box cannot help it. On one box, cgroup caps already stop a runaway worker from touching Postgres's memory.
- **Network on every query.** I could not confirm that OVH VPS plans join a private network (vRack). Without it, Postgres listens on a public interface, so you add TLS, a firewall allowlist and an exposed port 5432.
- **Lower availability.** The site needs both machines up, so two failure points instead of one, plus two hosts to patch, monitor and back up.
- **Nothing you need now.** Its two real benefits — isolating the database and scaling app nodes independently — are already handled by the memory caps, or not needed at launch.

Revisit when Postgres needs more than about half of the box's RAM, or the app needs more than one node. At that point move Postgres to a managed service, not to a second self-run VPS.

Your latest screenshot has the location set to Canada (Beauharnois); switch it to Poland before ordering.

### Verdict

Option B on OVH VPS-3. It runs at about two-thirds of the $20 ceiling, its bill does not move with traffic, it keeps the existing uv workspace running as-is inside containers, and failures stay on one box you can `ssh` into. Re-open Option A only if you need multi-region latency or burst to dozens of concurrent audits — neither is a launch requirement.

## 2. Backend architecture and auth integration

FastAPI is stateless: every byte of state — sessions, audits, credits, jobs, progress — lives in Postgres, so any API process can serve any request and a restart loses nothing.

### Process model and state

- **Lifespan-owned singletons** (created once per uvicorn worker in `lifespan`): async SQLAlchemy engine (`pool_size=5`, `max_overflow=3`), Procrastinate app, one `ProgressHub` holding a single `LISTEN audit_progress` connection, a shared `httpx.AsyncClient`, and a `StripeClient`.
- **Per-request**: an `AsyncSession` from a dependency, committed or rolled back by the dependency, never by route code.
- **Connection budget** (*estimate*, verify with `pg_stat_activity`): every pool in every process is counted in Section 6 — peak ≈ 67 including a 10-connection admin reserve, under `max_connections=100`.
- **Engine seam**: `deal-analyzer` stops reading `agent-context/` from disk. Its entry point becomes `analyze_listing(ref, *, context: ContextRepository, progress: ProgressSink) -> DealAnalysis`; the Postgres-backed `ContextRepository` serves sidecars, and the CLI keeps a filesystem implementation for local use. The Nominatim SQLite cache and hedonic file hashing move to Postgres tables, which removes audit findings 3.1-2 and 3.1-3.

### Route map

| Prefix | Owner | Auth | Purpose |
| --- | --- | --- | --- |
| `/api/auth/*` | FastAPI | public | Google ID-token sign-in, email magic link, email/password (`register`, `register/verify`, `register/resend`, `login`, `password/forgot`, `password/reset`; `password/change` needs a session), sign-out, session list (spec: PASSWORD-AUTH-SPEC.md) |
| `/api/me` | FastAPI | session | Profile, plan, credit balance, feature flags; `GET /api/me/export` (access request, 5 per hour); `DELETE /api/me` (account erasure, confirmed by typing the address) |
| `/api/audits` | FastAPI | session + entitlement | `POST` create (202), `GET` list, `GET /{id}`, `GET /{id}/events` (SSE), `POST /{id}/cancel` |
| `/api/saved` | FastAPI | session | Save or unsave listings, notes; only listings the caller has audited can be saved (anything else is 404), at most 500 |
| `/api/market/*` | FastAPI | session; free tier sees top 20 | 727-city yield radar, city sidecars by grain |
| `/api/screener/*` | FastAPI | Pro feature flag | Discovery runs, approval queue, batch generate |
| `/api/billing/checkout`, `/api/billing/portal` | FastAPI | session | Create Stripe Checkout or Portal session, return URL. **Pilot (ADR 0005 successor in progress):** `GET /api/billing/packs`, `POST /api/billing/checkout` (pack code + `Idempotency-Key`), `GET /api/billing/purchases[/{id}]`, Paddle packs per `PADDLE-INTEGRATION.md` §3 (RM-217); no portal |
| `/api/billing/webhook` | FastAPI | Stripe signature | Webhook state machine (Section 3) |
| `/api/admin/*` | FastAPI | `user.role = 'admin'` | Flags, overrides, credit adjustments (idempotent by a caller-chosen UUID), job inspection (metadata only, never arguments) |
| `/healthz`, `/readyz` | FastAPI | internal only (Caddy blocks external) | Liveness; readiness checks DB and queue. A separate public \`/api/health\` (no DB) serves the uptime monitor |

### Frontend boundary and data fetching

- The SPA talks only to `/api/*` on its own origin. Caddy serves `index.html` for every non-API path.
- Types are generated, not hand-written: FastAPI's OpenAPI schema → `openapi-typescript` → `openapi-fetch` client, wrapped in TanStack Query. A Pydantic change that the UI does not handle fails `tsc` in CI.
- **Delete `frontend/src/lib/cashflow.ts` and `appreciation.ts`.** The API returns every number; a null renders as an explicit "not computed" state. This enforces the deterministic-math invariant at the boundary (audit P0.3).
- Progress uses `EventSource` on `/api/audits/{id}/events`; if the stream drops, the browser reconnects with `Last-Event-ID` and the server replays from `audit_event`.

### Listing-analysis contract

Request and response, validated by Pydantic v2:

```python
class AuditCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    listing_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
    lang: Literal["pl", "en"] = "pl"
    analyst: bool = False  # Pro-only text LLM audit

    @field_validator("listing_ref")
    @classmethod
    def normalise(cls, v: str) -> str:
        m = OTODOM_REF_RE.search(v)  # https://www.otodom.pl/pl/oferta/...-ID4CpHB or ID4CpHB
        if not m:
            raise ValueError("not an Otodom listing URL or ID")
        return m.group("short_id")

class AuditAccepted(BaseModel):
    audit_id: UUID
    status: AuditStatus           # queued
    events_url: str               # /api/audits/{id}/events
    credits_remaining: int | None # None = within plan allowance
```

Pipeline stages emit progress events; percentages are fixed so the UI bar is deterministic:

| Stage | Event `stage` | `pct` at start | Invariant enforced here |
| --- | --- | --- | --- |
| Fetch `_next/data` | `fetch` | 5 | — |
| Extract specs | `extract` | 15 | **RENT is not a deal**: transaction ≠ SALE → terminal `rejected` / `RENT_NOT_DEAL`; fractional-share guard |
| Market context | `context` | 25 | **Asking ≠ deed**: sidecars loaded as separate typed grains |
| Photos + vision | `vision` | 35 | Renders, plans and staging excluded from CAPEX |
| Floor-plan OCR | `ocr` | 60 | — |
| Rent anchors + hedonic | `anchors` | 70 | **Admin fee is OPEX** |
| 10-year DCF + Max Bid | `synthesize` | 85 | Deterministic Python only; LLM adjustments capped ±15% |
| Persist | `persist` | 95 | Result JSONB + extracted columns |

SSE wire format:

```text
id: 42
event: progress
data: {"audit_id":"…","stage":"vision","pct":35,"message":"12 photos, 3 renders excluded"}

event: done
data: {"audit_id":"…","status":"succeeded","grade":"B","result_url":"/api/audits/…"}
```

### Error contract, including anti-scraping

Errors return RFC 9457 `application/problem+json` with a stable `code`. Terminal audit states decide the credit outcome: a credit is captured only on `succeeded` or `succeeded_degraded`; every other terminal state releases it.

| `code` | Detected by | HTTP at submit / terminal status | Retry policy | Credit |
| --- | --- | --- | --- | --- |
| `INVALID_LISTING_REF` | Pydantic | 422 | none | never reserved |
| `QUOTA_EXHAUSTED` | entitlement dependency | 402 with `upgrade_url` | none | never reserved |
| `AUDIT_IN_PROGRESS` | Procrastinate `queueing_lock` per user + listing | 409 with existing `audit_id` | none | never reserved |
| `RENT_NOT_DEAL` | extract stage | `rejected` | none | released |
| `FRACTIONAL_OWNERSHIP` | extract stage | `rejected` | none | released |
| `LISTING_GONE` | 404 or 410, or redirect to search | `failed_input` | none | released |
| `UPSTREAM_BLOCKED` | 403, 429, captcha or challenge HTML, missing `__NEXT_DATA__` | `failed_upstream` | tenacity: 4 attempts, exponential 2–60 s with jitter, honour `Retry-After`; then trip a 15-minute host circuit breaker | released |
| `UPSTREAM_SCHEMA_DRIFT` | `_next/data` payload fails Pydantic | `failed_upstream` + Better Stack alert | none (needs a code fix) | released |
| `VISION_UNAVAILABLE` | OpenRouter 5xx or timeout after retries | `succeeded_degraded`: CAPEX marked unknown, confidence lowered | 3 attempts | captured |
| `CONTEXT_UNAVAILABLE` | a market input the engine cannot run without is not configured (risk-free rate) or the market-data store failed (RM-187) | `failed_internal` + Better Stack error | none until the input exists | released |
| `INTERNAL` | anything else | `failed_internal` + Better Stack error | Procrastinate retry once | released |
| `BILLING_UNAVAILABLE` | billing is switched off or no approved catalog is loaded (the default) | 503 | none | n/a |
| `IDEMPOTENCY_CONFLICT` | an `Idempotency-Key` was reused for a different pack | 409 | use a new key | n/a |
| `BILLING_PROVIDER_ERROR` | the payment provider refused to start a purchase | 502 | try again with a new key | n/a |
| `VALIDATION_ERROR` | request body, query or path fails Pydantic (`extra="forbid"`) | 422, field errors without echoing input | none | never reserved |
| `NOT_FOUND` | unknown route, or a resource of another tenant (never 403) | 404 | none | never reserved |
| `HTTP_ERROR` | other transport errors (405, 413, …) | as raised | none | never reserved |
| `NOT_READY` | `/readyz` database or queue check fails; Google's signing certificates unreachable | 503 with `checks` | orchestrator retries | n/a |
| `UNAUTHENTICATED` | `current_principal`: no, unknown or expired session cookie | 401 | sign in | never reserved |
| `INVALID_GOOGLE_TOKEN` | `google-auth` rejects signature, audience, issuer, expiry or claims | 401 | none | n/a |
| `EMAIL_CONFIRMATION_REQUIRED` | verified Google token for an address Google cannot vouch for (not `@gmail.com`, no matching `hd`) and no existing identity | 401 (the SPA offers the magic link) | confirm with a magic link | n/a |
| `GOOGLE_EMAIL_UNVERIFIED` | valid Google token whose `email_verified` is false | 401 (the SPA offers the magic link) | none | n/a |
| `MAGIC_LINK_INVALID` | magic-link token unknown, already used or expired | 401 | request a new link | n/a |
| `INVALID_CREDENTIALS` | password login failed for any reason (wrong password, unknown address, no password set) | 401 | none; throttled | n/a |
| `WEAK_PASSWORD` | password fails the policy (`reason`: too_short, too_long, common, contains_email) | 422 | choose another | n/a |
| `ACCOUNT_EXISTS` | a registration link was used but the address already has an account (nothing is attached; use "forgot password") | 409 | sign in or recover | n/a |
| `AUTH_TOKEN_INVALID` | registration or reset token unknown, used, expired or wrong purpose | 401 | request a new link | n/a |
| `RATE_LIMITED` | atomic per-address or per-IP counter exceeded | 429 with `Retry-After` | after the window | n/a |
| `ADMIN_ONLY` | `require_admin` dependency: caller's role is not `admin` | 403 | none | n/a |
| `CREDIT_BELOW_ZERO` | admin credit adjustment would make the balance negative | 409 | none | n/a |
| `SAVED_LIMIT_REACHED` | saving a new listing beyond the per-user cap | 409 | unsave one | n/a |
| `CONFIRMATION_MISMATCH` | `DELETE /api/me` body address differs from the account's | 422 | retype the address | n/a |
| `ORIGIN_NOT_ALLOWED` | unsafe method on `/api/*` without `Origin == PUBLIC_APP_URL` | 403 | none | never reserved |

Scraping hygiene the workers enforce:

- A shared Postgres `host_throttle` row per host caps Otodom at 1 request/second across both worker pools, so batch sweeps cannot starve audits.
- `curl_cffi` with browser TLS impersonation replaces the `requests` bridge (audit 3.2).
- Listing snapshots are shared across tenants for 6 hours by `(otodom_id, content hash)`: two users auditing the same flat cost one fetch.
- The circuit breaker state is exposed on `/api/me` so the UI shows "Otodom is rate-limiting us, try in N minutes" instead of a spinner.

### Auth decision: pure Python, Google-first

One runtime. The Better Auth Node sidecar from the earlier draft is removed. With Google as the primary method, auth reduces to verifying one Google-signed ID token and keeping a session row — about 300 lines of Python. That is less than the glue the sidecar needed: a second container and toolchain, its own migration CLI owning a second schema, and a cookie-format contract between two languages.

| Option | Verdict | Reason |
| --- | --- | --- |
| Better Auth Node sidecar (previous draft) | Rejected | A second runtime, container, migration tool and schema owner for one feature |
| Everything in Node | Rejected | The engine, workers and DCF math are Python and stay Python; Node would add a runtime, not remove one |
| FastAPI-Users | Rejected | Maintenance mode; passwords are now ours (ADR 0013) and we use `pwdlib[argon2]` directly |
| Managed provider (Clerk, Auth0) | Rejected | Another vendor on the login path; the user table leaves your Postgres |
| **FastAPI + Google Identity Services + `google-auth`, own sessions** | **Chosen** | Google authenticates the person; FastAPI verifies Google's signed token and issues its own session |

Sign-in methods:

1. **Google (primary).** The "Zaloguj się przez Google" button and One Tap both come from Google Identity Services (GIS) in the SPA. GIS hands the SPA a signed ID token (`credential`), which the SPA posts to `POST /api/auth/google`. No OAuth redirect and no client secret on the server.
2. **Email magic link (secondary).** For users without Google: `POST /api/auth/email/start` emails a single-use link valid 30 minutes; `POST /api/auth/email/verify` signs in after the user presses "Kontynuuj" on the page the link opens, so mail scanners that prefetch links cannot use up the token. Using the link proves the address, so the 3 free audits unlock.

**Passwords (amended by ADR 0013, 2026-10-14):** the original hard call was no passwords. The owner asked for email and password sign-in, so it is added next to Google and the magic link with `pwdlib[argon2]`, mailbox proof before an account exists, hashed single-use tokens, throttling and non-enumerating responses. The contract is [PASSWORD-AUTH-SPEC.md](PASSWORD-AUTH-SPEC.md); implementation tracked in #203, #204, #205.

How it protects FastAPI:

1. A session is a random 32-byte token in cookie `__Host-rm_session` (`HttpOnly; Secure; SameSite=Lax; Path=/`). Postgres stores only its SHA-256, so a database leak does not leak live sessions.
2. `current_principal` hashes the cookie, looks up `user_session` joined to `app_user` where `expires_at > now()`, extends the expiry at most once a day, and caches hits for 30 seconds in-process.
3. Unsafe methods on `/api/*` must carry `Origin` equal to `PUBLIC_APP_URL`. That covers `POST /api/auth/google`, because the SPA uses GIS's JavaScript callback mode, not the `login_uri` form-post mode that needs Google's `g_csrf_token` double-submit check.
4. Sign-out deletes the session row; "sign out everywhere" deletes all of the user's rows. Both send NOTIFY session\_revoked, which every API process receives on the SSE hub's existing LISTEN connection and uses to drop cached principals, so revocation is near-immediate. If that connection is down, revocation falls back to the 30-second cache TTL — a stated bound, not a hidden one.
5. `/api/auth/email/start` is rate-limited to 5 per hour per address and 20 per hour per IP through one atomic Postgres upsert (INSERT … ON CONFLICT (key, window\_start) DO UPDATE SET n = n + 1 RETURNING n), so concurrent API processes cannot overshoot.
6. Unverified Google emails are rejected outright (the SPA offers the magic link instead), so every Google identity is verified. Account linking and creation additionally require that Google is **authoritative** for the address (ADR 0010, owner decision D-13): the address ends in `@gmail.com`, or the token carries an `hd` claim equal to the address's domain. A verified Google sign-in for any other address joins or creates nothing and is answered `EMAIL_CONFIRMATION_REQUIRED`; the user confirms the address with the magic link first. An unverified one never links, which blocks account takeover.
7. Cookies work with `EventSource`, so SSE needs no token plumbing.

```python
# services/rm_api/auth/google.py
import cachecontrol, requests
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

_certs = GoogleRequest(session=cachecontrol.CacheControl(requests.Session()))  # caches Google's keys


class GoogleCredential(BaseModel):
    credential: str = Field(max_length=4096)


@router.post("/google", response_model=MeOut)
async def google_sign_in(body: GoogleCredential, request: Request, response: Response, db: DB) -> MeOut:
    try:
        # Checks signature, issuer, audience (our client id) and expiry; blocking I/O -> thread.
        claims = await asyncio.to_thread(
            id_token.verify_oauth2_token, body.credential, _certs, settings.google_client_id)
    except ValueError:
        raise Problem.unauthorized("INVALID_GOOGLE_TOKEN")
    if not claims.get("email_verified"):
        # Hard call: no accounts from unverified Google emails; they cannot claim an address.
        raise Problem.unauthorized("GOOGLE_EMAIL_UNVERIFIED")   # SPA offers the magic link
    user = await upsert_google_user(
        db, sub=claims["sub"], email=claims["email"].lower(),
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"), picture=claims.get("picture"))
    token = await create_session(db, user.id, request)
    await ensure_credit_account(db, user.id, verified=user.email_verified_at is not None)
    await db.commit()
    set_session_cookie(response, token)
    return MeOut.from_user(user)


async def upsert_google_user(db, *, sub, email, email_verified, name, picture) -> User:
    ident = await db.scalar(select(AuthIdentity).where(
        AuthIdentity.provider == "google", AuthIdentity.subject == sub))
    if ident is not None:                                  # returning Google user (keyed by sub, never email)
        return await db.get(User, ident.user_id)
    user = await db.scalar(select(User).where(User.email == email))   # caller guarantees verified
    if user is None:
        user = User(email=email, name=name, avatar_url=picture,
                    email_verified_at=func.now() if email_verified else None)
        db.add(user)
        await db.flush()
    elif user.email_verified_at is None:
        user.email_verified_at = func.now()
    db.add(AuthIdentity(user_id=user.id, provider="google", subject=sub))
    return user


async def create_session(db, user_id: str, request: Request) -> str:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(
        token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(days=settings.session_ttl_days),
        user_agent=request.headers.get("user-agent", "")[:300], ip=request.client.host))
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(settings.session_cookie_name, token, max_age=settings.session_ttl_days * 86400,
                        httponly=True, secure=settings.app_env != "development", samesite="lax", path="/")
```

Magic link, same module:

```python
@router.post("/email/start", status_code=204)
async def email_start(body: EmailStart, request: Request, db: DB) -> None:
    email = body.email.lower()
    await enforce_rate_limit(db, f"ml:email:{email}", limit=5, window_s=3600)
    await enforce_rate_limit(db, f"ml:ip:{request.client.host}", limit=20, window_s=3600)
    token = secrets.token_urlsafe(32)
    db.add(LoginToken(token_hash=sha256_hex(token), email=email,
                      expires_at=datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes)))
    await db.commit()
    # Fragment, not query string: never sent to servers, so proxies and scanners do not log it.
    await send_magic_link.defer_async(email=email, url=f"{settings.public_app_url}/login/email#t={token}")
    # Always 204: the response never reveals whether the address has an account.


@router.post("/email/verify", response_model=MeOut)
async def email_verify(body: EmailVerify, request: Request, response: Response, db: DB) -> MeOut:
    email = (await db.execute(
        update(LoginToken)
        .where(LoginToken.token_hash == sha256_hex(body.token),
               LoginToken.used_at.is_(None), LoginToken.expires_at > func.now())
        .values(used_at=func.now()).returning(LoginToken.email)      # atomic single use
    )).scalar_one_or_none()
    if email is None:
        raise Problem.unauthorized("MAGIC_LINK_INVALID")
    user = await upsert_email_user(db, email=email)   # user + ('email', address) identity, email_verified_at set
    token = await create_session(db, user.id, request)
    await ensure_credit_account(db, user.id, verified=True)
    await db.commit()
    set_session_cookie(response, token)
    return MeOut.from_user(user)
```

SPA side (Google's script, no npm auth library):

```typescript
// frontend/src/auth/google.ts — loads https://accounts.google.com/gsi/client
google.accounts.id.initialize({
  client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
  callback: async ({ credential }) => {
    const r = await fetch("/api/auth/google", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential }),
    });
    if (r.ok) location.assign("/app");
  },
});
// /login: the button, first and full width
google.accounts.id.renderButton(el, { theme: "outline", size: "large", text: "signin_with", locale: "pl", width: 360 });
// landing page and paywall only: One Tap
google.accounts.id.prompt();
```

Screen rules: `/login` and `/signup` are one screen — the Google button first, a "lub" divider, then a collapsed "Wyślij link na e-mail" field. One Tap appears on the landing page and paywall, never on `/login`, so the user never sees two Google prompts. A first Google sign-in lands on `/app` with the 3 free audits visible.

Google Cloud setup:

1. OAuth consent screen: External, app name RentMonitor, support email, scopes `openid`, `email`, `profile` only.
2. OAuth client, type Web application. Authorized JavaScript origins: `https://app.rentmonitor.pl` and `http://localhost`. No redirect URIs and no client secret are used.
3. Move the app from Testing to In production before launch; in Testing only listed test users can sign in.
4. The Caddy CSP in 4.3 already allows `accounts.google.com` for scripts, styles, frames and connections.

## 3. Data model and entitlement schema

One schema, `app`, owned by Alembic. Users, login identities, sessions and magic-link tokens sit next to the business tables, so deleting a user cascades in one transaction and there is one migration tool.

Design rules the schema encodes:

- **Two consumption sources, consumed in order.** A paid period's allowance (`usage_period`, expires at period end) is spent before discrete credits (`credit_ledger`, never expire). Free users have only credits: 3 on verified sign-up.
- **Reserve → capture or release.** A credit is held when the audit is queued and settled when it ends, so a crashed or blocked audit never costs the user.
- **Every grant has an idempotency key** (`signup:{user_id}`, `invoice:{in_…}`, `admin:{uuid}`) with a unique constraint — a replayed webhook or double click cannot double-grant.
- **Asking ≠ deed is a database constraint**, not a convention: `market_sidecar.price_basis` is checked against `kind`.
- **Tenant = user** for launch. Every tenant-owned row carries `user_id`, and all queries go through repositories that require a `Principal`. Workspaces are an additive migration later.

### SQLAlchemy 2.0 models

```python
# packages/rm_core/db/models.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Identity,
    Index, Integer, MetaData, Numeric, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
APP = {"schema": "app"}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {datetime: DateTime(timezone=True), dict: JSONB}


def pg_enum(e: type[StrEnum], name: str) -> Enum:
    return Enum(e, name=name, schema="app", values_callable=lambda x: [m.value for m in x])


# ---------- Identity and sessions (owned by this app) ----------
class User(Base):
    __tablename__ = "app_user"; __table_args__ = APP     # 'user' is reserved in Postgres
    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(Text, unique=True)   # stored lower-cased
    email_verified_at: Mapped[datetime | None]
    name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default="user")   # user | admin
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


USER_FK = ForeignKey("app.app_user.id", ondelete="CASCADE")


class AuthIdentity(Base):
    """One row per login method: ('google', sub) or ('email', address)."""
    __tablename__ = "auth_identity"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, USER_FK, index=True)
    provider: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(Text)            # Google 'sub' — never key on email
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("provider", "subject"), APP)


class UserSession(Base):
    __tablename__ = "user_session"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)   # sha256 of the cookie value
    user_id: Mapped[str] = mapped_column(Text, USER_FK, index=True)
    expires_at: Mapped[datetime]
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(45))
    __table_args__ = APP


class LoginToken(Base):
    """Email magic link: single use, 30 minutes."""
    __tablename__ = "login_token"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(Text, index=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    __table_args__ = APP


# ---------- Plans, Stripe, subscriptions ----------
class SubStatus(StrEnum):
    incomplete = "incomplete"; incomplete_expired = "incomplete_expired"
    trialing = "trialing"; active = "active"; past_due = "past_due"
    canceled = "canceled"; unpaid = "unpaid"; paused = "paused"


class Plan(Base):
    __tablename__ = "plan"; __table_args__ = APP
    code: Mapped[str] = mapped_column(String(32), primary_key=True)        # free | pro
    stripe_price_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    monthly_audit_allowance: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[dict] = mapped_column(default=dict)                  # {"screener": true, ...}
    active: Mapped[bool] = mapped_column(default=True)


class StripeCustomer(Base):
    __tablename__ = "stripe_customer"; __table_args__ = APP
    user_id: Mapped[str] = mapped_column(Text, USER_FK, primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Subscription(Base):
    __tablename__ = "subscription"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)          # sub_...
    user_id: Mapped[str] = mapped_column(Text, USER_FK, index=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("app.plan.code"))
    status: Mapped[SubStatus] = mapped_column(pg_enum(SubStatus, "sub_status"))
    price_id: Mapped[str] = mapped_column(String(64))
    current_period_start: Mapped[datetime]   # from items.data[0] (API >= 2025-03-31.basil)
    current_period_end: Mapped[datetime]
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    grace_until: Mapped[datetime | None]
    stripe_seen_at: Mapped[datetime]         # newest event.created applied
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    __table_args__ = (
        Index("uq_subscription_one_live_per_user", "user_id", unique=True,
              postgresql_where=text("status IN ('trialing','active','past_due')")),
        APP,
    )


class StripeEvent(Base):
    """Idempotency log: inserted in the same transaction as the side effects."""
    __tablename__ = "stripe_event"; __table_args__ = APP
    id: Mapped[str] = mapped_column(String(64), primary_key=True)          # evt_...
    type: Mapped[str] = mapped_column(String(80), index=True)
    api_version: Mapped[str | None] = mapped_column(String(40))
    stripe_created: Mapped[datetime]
    outcome: Mapped[str] = mapped_column(String(16))                       # processed | ignored
    payload: Mapped[dict]
    received_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------- Quota: plan allowance per period + discrete credit ledger ----------
class UsagePeriod(Base):
    __tablename__ = "usage_period"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, USER_FK)
    kind: Mapped[str] = mapped_column(String(12), default="subscription")  # subscription | pass
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("app.subscription.id"))  # None for a pass
    source_invoice_id: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    allowance: Mapped[int]
    used: Mapped[int] = mapped_column(default=0)
    __table_args__ = (
        CheckConstraint("used >= 0 AND used <= allowance", name="used_within_allowance"),
        Index("ix_usage_period_user_window", "user_id", "period_end"),
        APP,
    )


class CreditReason(StrEnum):
    signup_grant = "signup_grant"; admin_adjust = "admin_adjust"; topup = "topup"
    reserve = "reserve"; release = "release"


class CreditAccount(Base):
    """Balance cache; row-locked (FOR UPDATE) for every mutation."""
    __tablename__ = "credit_account"
    user_id: Mapped[str] = mapped_column(Text, USER_FK, primary_key=True)
    balance: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint("balance >= 0", name="non_negative"), APP)


class CreditLedger(Base):
    """Append-only. SUM(delta) per user must equal credit_account.balance (nightly check)."""
    __tablename__ = "credit_ledger"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, USER_FK, index=True)
    delta: Mapped[int]
    reason: Mapped[CreditReason] = mapped_column(pg_enum(CreditReason, "credit_reason"))
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True)
    audit_id: Mapped[UUID | None] = mapped_column(ForeignKey("app.audit.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (CheckConstraint("delta <> 0", name="non_zero"), APP)


# ---------- Listings, audits, progress, saved ----------
class AuditStatus(StrEnum):
    queued = "queued"; running = "running"; succeeded = "succeeded"
    succeeded_degraded = "succeeded_degraded"; rejected = "rejected"
    failed_input = "failed_input"; failed_upstream = "failed_upstream"
    failed_internal = "failed_internal"; cancelled = "cancelled"


class ChargeSource(StrEnum):
    plan = "plan"; credit = "credit"; admin_free = "admin_free"


class ChargeState(StrEnum):
    reserved = "reserved"; captured = "captured"; released = "released"


class Listing(Base):
    """Public listing identity, shared across tenants."""
    __tablename__ = "listing"; __table_args__ = APP
    otodom_id: Mapped[str] = mapped_column(String(16), primary_key=True)    # ID4CpHB
    url: Mapped[str] = mapped_column(Text)
    transaction: Mapped[str | None] = mapped_column(String(8))              # SALE | RENT
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshot"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    otodom_id: Mapped[str] = mapped_column(ForeignKey("app.listing.otodom_id"))
    content_sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict]                       # raw _next/data pageProps.ad
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (UniqueConstraint("otodom_id", "content_sha256"), APP)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(Text, USER_FK)
    otodom_id: Mapped[str] = mapped_column(ForeignKey("app.listing.otodom_id"))
    snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("app.listing_snapshot.id"))
    status: Mapped[AuditStatus] = mapped_column(pg_enum(AuditStatus, "audit_status"))
    error_code: Mapped[str | None] = mapped_column(String(40))
    charge_source: Mapped[ChargeSource] = mapped_column(pg_enum(ChargeSource, "charge_source"))
    charge_state: Mapped[ChargeState] = mapped_column(pg_enum(ChargeState, "charge_state"))
    usage_period_id: Mapped[int | None] = mapped_column(ForeignKey("app.usage_period.id"))
    lang: Mapped[str] = mapped_column(String(2), default="pl")
    analyst: Mapped[bool] = mapped_column(default=False)
    engine_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[int]
    result: Mapped[dict | None]                 # canonical DealAnalysis JSON (was reports/final/{id}.json)
    # extracted for filtering and sorting — copied from result, never computed here
    grade: Mapped[str | None] = mapped_column(String(2))
    asking_price_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_bid_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    irr_10y: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    capex_pln: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", text("created_at DESC")),
        Index("uq_audit_one_active_per_listing", "user_id", "otodom_id", unique=True,
              postgresql_where=text("status IN ('queued','running')")),
        CheckConstraint("(charge_source = 'plan') = (usage_period_id IS NOT NULL)", name="plan_has_period"),
        APP,
    )


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)  # SSE id
    audit_id: Mapped[UUID] = mapped_column(ForeignKey("app.audit.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12))        # progress | done | error
    stage: Mapped[str | None] = mapped_column(String(16))
    pct: Mapped[int | None]
    payload: Mapped[dict] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = (Index("ix_audit_event_audit_id", "audit_id", "id"), APP)


class SavedListing(Base):
    __tablename__ = "saved_listing"; __table_args__ = APP
    user_id: Mapped[str] = mapped_column(Text, USER_FK, primary_key=True)
    otodom_id: Mapped[str] = mapped_column(ForeignKey("app.listing.otodom_id"), primary_key=True)
    latest_audit_id: Mapped[UUID | None] = mapped_column(ForeignKey("app.audit.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------- Market sidecars (agent-context migrated) ----------
class SidecarKind(StrEnum):
    otodom_rental = "otodom_rental"; otodom_sale = "otodom_sale"
    bdl_deed = "bdl_deed"; cenogram_deed = "cenogram_deed"
    moniter_asking = "moniter_asking"; yield_ranking = "yield_ranking"


class MarketSidecar(Base):
    __tablename__ = "market_sidecar"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    kind: Mapped[SidecarKind] = mapped_column(pg_enum(SidecarKind, "sidecar_kind"))
    price_basis: Mapped[str] = mapped_column(String(8))   # asking | deed | rent
    city_slug: Mapped[str] = mapped_column(String(80))    # 'pl' for national rankings
    teryt: Mapped[str | None] = mapped_column(String(12))
    period: Mapped[date]                                  # first day of month or quarter
    size_bucket: Mapped[str | None] = mapped_column(String(8))  # 0-30 | 30-50 | 50-70 | 70+
    source_stem: Mapped[str] = mapped_column(Text)        # otodom-rental-leszno-2026-09
    sha256: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict]                                 # canonical sidecar JSON
    generated_at: Mapped[datetime]
    __table_args__ = (
        UniqueConstraint("kind", "city_slug", "period", "size_bucket", name="uq_sidecar_grain",
                         postgresql_nulls_not_distinct=True),
        CheckConstraint(
            "(kind IN ('bdl_deed','cenogram_deed') AND price_basis = 'deed') OR "
            "(kind IN ('moniter_asking','otodom_sale','yield_ranking') AND price_basis = 'asking') OR "
            "(kind = 'otodom_rental' AND price_basis = 'rent')",
            name="asking_is_not_deed",
        ),
        Index("ix_sidecar_city_kind_period", "city_slug", "kind", text("period DESC")),
        APP,
    )


# ---------- AI spend control (added by RM-24) ----------
class AiBudget(Base):        # one row per UTC month: cap_usd, reserved_usd, spent_usd, warned_at
    __tablename__ = "ai_budget"
class AiReservation(Base):   # one hold per model call: amount_usd, state reserved|settled|released|swept
    __tablename__ = "ai_reservation"
class AiUsage(Base):         # per-call log: model, tokens, cost_usd, cost_estimated, audit_id (no FK)
    __tablename__ = "ai_usage"


# ---------- OSM lookup cache (added by RM-86) ----------
class GeoCache(Base):
    """Cached Nominatim/Overpass answers keyed by sha256 of the normalised request; expires_at drives retention."""
    __tablename__ = "geo_cache"; __table_args__ = APP
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))                 # geocode | poi
    payload: Mapped[dict]
    fetched_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(index=True)


# ---------- Erasure accountability (added by RM-30) ----------
class ErasureLog(Base):
    """sha256(user_id) of erased accounts, so a restore from an older backup can re-erase them."""
    __tablename__ = "erasure_log"; __table_args__ = APP
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_hash: Mapped[str] = mapped_column(String(64), unique=True)
    erased_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)


# ---------- Scraping hygiene (added by RM-22) ----------
class HostThrottle(Base):
    """Next free request slot per outbound host and its circuit-breaker window."""
    __tablename__ = "host_throttle"; __table_args__ = APP
    host: Mapped[str] = mapped_column(String(64), primary_key=True)        # 'otodom.pl'
    next_at: Mapped[datetime] = mapped_column(server_default=func.now())
    breaker_open_until: Mapped[datetime | None]
    breaker_reason: Mapped[str | None] = mapped_column(String(40))


# ---------- Feature flags ----------
class FeatureFlag(Base):
    __tablename__ = "feature_flag"; __table_args__ = APP
    key: Mapped[str] = mapped_column(String(64), primary_key=True)   # screener, redesign, analyst
    description: Mapped[str] = mapped_column(Text)
    enabled_default: Mapped[bool] = mapped_column(default=False)
    min_plan: Mapped[str | None] = mapped_column(ForeignKey("app.plan.code"))
    rollout_pct: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class FeatureOverride(Base):
    __tablename__ = "feature_override"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    flag_key: Mapped[str] = mapped_column(ForeignKey("app.feature_flag.key", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(Text, USER_FK)
    enabled: Mapped[bool]
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None]
    created_by: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("flag_key", "user_id"), APP)
```

Flag resolution order, first match wins: unexpired `feature_override` → `min_plan` not met (off) → `rollout_pct` bucket from `sha256(user_id + key) % 100` → `enabled_default`.

Alembic `env.py` keeps everything in `app` and creates the schema first:

```python
context.configure(..., target_metadata=Base.metadata, include_schemas=True,
                  version_table_schema="app")
# first migration: op.execute("CREATE SCHEMA IF NOT EXISTS app")
# Procrastinate's own tables are applied by `procrastinate schema --apply`, not Alembic.
```

### Stripe webhook lifecycle

The handler never trusts event order, and never processes two events for the same subscription at the same time (per-subscription lock, Section 4.5 c). For every subscription-related event it re-retrieves the Subscription from Stripe and writes that current state, so a late `customer.subscription.updated` cannot overwrite a newer `deleted`. Allowance is granted only on `invoice.paid`, keyed by invoice id.

&#91;embedded content: subscription entitlement states · 5 states, 8 transitions\]

Only Active, Cancelling and in-grace Past due grant Pro; every other state falls back to the discrete credit balance.

Pin the account and webhook endpoint to one API version and the matching `stripe` Python SDK. On every version since `2025-03-31.basil`, `current_period_start/end` live on subscription items, not the Subscription, and an invoice's subscription is at `invoice.parent.subscription_details.subscription`.

| Event | Guard | Writes | Entitlement after |
| --- | --- | --- | --- |
| `checkout.session.completed` | `mode == "subscription"`, `client_reference_id` is a user id | Upsert `stripe_customer`; retrieve and upsert `subscription` | Unchanged until the invoice is paid |
| `invoice.paid` | New allowance only when `billing_reason` is `subscription_create` or `subscription_cycle`; every paid invoice, including `subscription_update` prorations, gets a VAT invoice | Upsert subscription; insert `usage_period` with `source_invoice_id` (on conflict do nothing); clear `grace_until` | Pro, allowance reset for the new period |
| `invoice.payment_failed` | invoice has a subscription parent | Upsert subscription; `grace_until = coalesce(grace_until, now() + 7 days)`; email the user | Pro until `grace_until` |
| `customer.subscription.updated` | — | Upsert status, price → plan, `cancel_at_period_end`, periods | Follows status; cancel-at-period-end keeps Pro until the period ends |
| `customer.subscription.deleted` | — | Status `canceled`; truncate the open `usage_period` to now | Free; remaining discrete credits still usable |
| anything else | — | `stripe_event.outcome = 'ignored'` | Unchanged |

Entitlement predicate, used by both the API and the workers:

```python
def has_pro(sub: Subscription | None, now: datetime) -> bool:
    if sub is None:
        return False
    if sub.status in (SubStatus.active, SubStatus.trialing):
        # Fail closed if the renewal never arrives: 48 h covers Stripe's renewal attempt and webhook
        # lag; a nightly reconcile_subscriptions task re-reads every live subscription from Stripe.
        return now < sub.current_period_end + timedelta(hours=48)
    return sub.status == SubStatus.past_due and sub.grace_until is not None and now < sub.grace_until
```

In the Stripe Dashboard, enable Smart Retries and set "if all retries fail" to cancel the subscription; that produces the `deleted` event that closes the loop.

### BLIK at launch

BLIK is a launch requirement, so there are two BLIK paths, with card as the universal fallback. Every customer can pay with BLIK on day one, even if their bank does not support recurring BLIK.

| Path | Who | Stripe mechanism | Renewal | Pro access comes from |
| --- | --- | --- | --- | --- |
| Card subscription | Anyone | Checkout, `mode=subscription` | Automatic | `usage_period` from `invoice.paid` |
| BLIK subscription | Customers of banks with BLIK recurring (list below) | Checkout, `mode=subscription`; customer enters a BLIK code and approves a recurring mandate (BLIK Model O) in the bank app | Automatic, off-session, no new code | `usage_period` from `invoice.paid` |
| BLIK pass "Pro 30 dni" | Any other bank, or anyone who does not want a mandate | Checkout, `mode=payment`, one-off 100 zł, `invoice_creation` on | Manual: reminder 3 days before expiry with a new pay link | `usage_period` from `checkout.session.completed` with `payment_status=paid` |

Confirmed in Stripe's docs (11 Oct 2026):

- BLIK recurring works with Subscriptions, Invoices and Checkout in subscription mode. It is PLN-only, and each off-session charge is capped at 2,000 zł — far above 100 zł.
- Both `blik_payments` and `blik_recurring_payments` must be `active` on your account. Enable them in Dashboard → Payment methods → BLIK → recurring payments. Stripe's April 2026 changelog required support to enable it; if the toggle is missing, open a support request now — this is the long pole for launch.
- Recurring BLIK works only for customers of Alior Bank, Credit Agricole, ING Bank Śląski, Millennium, mBank, Nest Bank, PKO Bank Polski, Santander Bank Polska and SGB cooperative banks. Other banks fail with `recurring_not_supported_by_bank`. That is why the 30-day pass exists.
- Hosted Checkout collects the code and the mandate, but **you** must show the billing and mandate disclosures before redirecting (see the paywall copy below).
- The mandate is indefinite unless you set `expires_at`; leave it indefinite.
- The Customer Portal lets subscribers switch between card and BLIK.
- Fees: BLIK 1.6% + 1.00 zł, plus 0.7% for Stripe Billing on subscriptions.

Paywall disclosure, shown above the "Zapłać" button when BLIK is likely (Polish locale):

> Subskrypcja RentMonitor Pro: 100 zł miesięcznie, pierwsza płatność dziś, kolejne automatycznie co miesiąc w tym samym dniu, bez ponownego kodu BLIK. Autoryzujesz płatności cykliczne BLIK w aplikacji banku; możesz je anulować w dowolnym momencie w ustawieniach konta. Obsługiwane banki: Alior, Credit Agricole, ING, Millennium, mBank, Nest Bank, PKO BP, Santander, banki SGB. Inny bank? Kup karnet Pro na 30 dni BLIK-iem.

Schema and code changes for the pass:

- `usage_period.subscription_id` becomes nullable, and a `kind` column (`subscription` | `pass`) is added.
- `load_entitlements` sets `is_pro` when `has_pro(subscription)` **or** a `pass` period covers now.
- A second Stripe Price, `STRIPE_PRICE_PRO_PASS_30D` (100 PLN, one-time), backs the pass.
- Buying a pass while one is active extends it: the new period starts at the end of the latest open period.

The code changes are applied in Section 4.5 (c) and the models above.

### VAT invoices and KSeF

Stripe collects the money; a Polish invoicing service issues the legal VAT invoice and submits it to KSeF. Stripe's invoice PDF is never presented as the faktura.

Confirmed ([ifirma](https://www.ifirma.pl/blog/ksef-w-e-commerce-faktury-b2b-oraz-b2c-w-sprzedazy-online-i-inne-obowiazki-zwiazane-z-krajowym-systemem-e-faktur-od-2026/), 11 Oct 2026):

- KSeF became mandatory on 1 Feb 2026 for taxpayers above 200 mln zł sales and on 1 Apr 2026 for everyone else.
- Tax authorities can impose penalties from **1 Jan 2027**. The external audit said penalties are suspended "through the end of 2027"; this source does not support that, so plan for 2027-01-01.
- A seller whose invoiced sales stay at or below 10,000 zł gross per month has no KSeF obligation until the end of 2026; it starts from the invoice that crosses the limit.
- For consumers, a KSeF e-invoice is optional, and an invoice is issued only on the consumer's request.

Not confirmed: whether Stripe can produce KSeF XML (I found nothing suggesting it can — *inference*); KSeF and cash-register (*kasa fiskalna*) treatment of your B2C sales; your own VAT status. Confirm all three with your accountant.

**Hard call: KSeF-compliant from the first B2B sale,** even if you start under the 10,000 zł limit. Retrofitting invoicing after launch means reissuing documents; doing it now is one background task.

Flow:

1. Checkout sessions set `tax_id_collection: {"enabled": true}`. A buyer who enters a NIP is a business; one who does not is a consumer.
2. On `invoice.paid` (subscription) and on a paid pass, the event handler inserts a `vat_invoice` row (status `pending`) in the same transaction as the payment's effects. That row is the durable work record; a `billing` task drains pending rows right after commit and every minute.
3. Business buyer: the task creates the invoice in **Fakturownia** through its API (buyer NIP, name and address from the Stripe customer; 100 zł gross at 23% VAT unless your accountant says otherwise). Fakturownia's KSeF integration is free on every plan and can send invoices to KSeF automatically, per [its KSeF page](https://fakturownia.pl/integracja-z-ksef). It does not say whether API-created invoices are sent automatically — test that on a trial account before building on it.
4. The task polls until Fakturownia reports a KSeF number, stores it, and emails the invoice. Alerts: not created at Fakturownia within 15 minutes, not accepted by KSeF within 2 hours, or any KSeF rejection → immediate Better Stack alert. The legal issuing deadline is your accountant's call; these thresholds sit well inside any plausible one.
5. Consumer buyer: a payment confirmation only, plus a "Poproś o fakturę" button on `/billing` that runs the same task on demand.
6. In the Stripe Dashboard, turn off Stripe's own invoice and receipt emails so customers receive one document set (*inference* that this avoids confusion; check which emails your account sends).

Why Fakturownia: free KSeF integration, a public REST API, and Polish-language support. inFakt or wFirma work the same way — use whichever your accountant already reads.

```python
class VatInvoice(Base):
    __tablename__ = "vat_invoice"
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, USER_FK, index=True)
    stripe_invoice_id: Mapped[str] = mapped_column(String(64), unique=True)   # idempotency
    buyer_nip: Mapped[str | None] = mapped_column(String(13))                 # None = consumer
    provider: Mapped[str] = mapped_column(String(16), default="fakturownia")
    provider_invoice_id: Mapped[str | None] = mapped_column(String(64))
    number: Mapped[str | None] = mapped_column(String(64))                    # e.g. FV 12/10/2026
    ksef_number: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")         # pending | created | submitted | ksef_accepted | ksef_rejected | failed
    attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    __table_args__ = APP
```

## 4. Turnkey implementation blueprint for AI coding agents

Hand this section to the agent as its specification. It is ordered so each step leaves a runnable, tested system; the agent must not start step N+1 with step N's tests red.

### 4.0 Agent operating rules

1. The analytical engines in `apps/` are written from scratch (ADR 0001); the proof of concept is read-only reference and nothing is copied from it. Engine math lives only in `apps/deal_analyzer`, uses `Decimal`, and takes `ContextRepository` and `ProgressSink` as native seams.
2. Never compute a financial number outside `apps/deal_analyzer`. The API copies values from `DealAnalysis` into typed columns; the UI renders them.
3. The four invariants each get a named regression test (listed in 4.6). A PR that deletes or skips one is rejected.
4. All money is `Decimal` in Python and `NUMERIC` in Postgres. No floats in persisted financial fields.
5. Every external call (Otodom, OpenRouter, GUS BDL, Moniter, Stripe, Nominatim) goes through an injectable client so tests run offline.

### 4.1 Repository layout

```text
rentmonitor/
├── pyproject.toml                # uv workspace: apps/*, packages/*, services/api, services/worker
├── uv.lock
├── Makefile                      # dev, test, migrate, seed, deploy, backup-drill
├── .env.example
├── apps/                         # engines, written from scratch (ADR 0001)
│   ├── deal-analyzer/
│   ├── otodom-city-report/
│   ├── price-intel/
│   ├── otodom-investment-screener/
│   └── agent-context/            # becomes an export target, no longer read at runtime
├── packages/
│   ├── rm_core/                  # settings, db models, repositories, ledger, entitlements, flags (pyproject.toml beside the modules)
│   └── rm_contracts/             # Pydantic API schemas + problem codes, shared by api and worker
├── services/
│   ├── rm_api/                   # main.py, deps.py, problems.py, sse.py, auth/, routers/, billing/
│   └── rm_worker/                # app.py, progress.py, tasks/audit.py, tasks/market.py, tasks/maintenance.py
├── frontend/                     # existing Vite SPA; server/plugin.ts and server/redesign.ts deleted
│   └── src/api/{schema.d.ts (generated), client.ts}
├── migrations/                   # Alembic, schema "app" only
├── scripts/{import_agent_context.py, import_legacy_reports.py, seed.py, gen_openapi.py}
├── tests/                        # cross-service integration tests + fixtures/
└── deploy/
    ├── compose.yml               # production
    ├── compose.dev.yml           # (RM-69: local development uses compose.yml alone; a production overlay arrives with RM-15)
    ├── docker/python.Dockerfile  # one image, three commands (api, worker-audit, worker-batch)
    ├── caddy/{Caddyfile, Dockerfile}   # multi-stage: builds frontend, copies dist
    ├── postgres/postgresql.conf
    └── backup/{backup.sh, restore-drill.sh, Dockerfile}
```

### 4.2 Environment configuration

```bash
# .env.example — copy to .env; never commit .env

# --- Public URLs ---
PUBLIC_APP_URL=https://app.rentmonitor.pl          # single origin for SPA, API and auth
APP_ENV=production                                 # development | test | production

# --- PostgreSQL ---
POSTGRES_DB=rentmonitor
POSTGRES_USER=rentmonitor
POSTGRES_PASSWORD=change-me-32-random-bytes
DATABASE_URL=postgresql+psycopg://rentmonitor:${POSTGRES_PASSWORD}@postgres:5432/rentmonitor
PROCRASTINATE_DSN=postgresql://rentmonitor:${POSTGRES_PASSWORD}@postgres:5432/rentmonitor

# --- Redis (intentionally absent) ---
# Procrastinate keeps jobs in Postgres; no REDIS_URL is read anywhere.

# --- Auth (Google Identity Services + email magic link, all in FastAPI) ---
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com   # audience checked on every ID token
VITE_GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}           # same id, baked into the SPA build
SESSION_COOKIE_NAME=__Host-rm_session               # dev over http: rm_session
SESSION_TTL_DAYS=30
MAGIC_LINK_TTL_MINUTES=30                          # corporate mail can delay delivery

# --- Email (Resend) ---
RESEND_API_KEY=re_xxx
MAIL_FROM="RentMonitor <no-reply@rentmonitor.pl>"

# --- Stripe ---
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx                     # from Dashboard endpoint, or `stripe listen` locally
STRIPE_API_VERSION=2026-09-30.endive                # pin; must match the webhook endpoint version
STRIPE_PRICE_PRO_MONTHLY=price_xxx                  # 100 PLN / month, recurring, card + BLIK
STRIPE_PRICE_PRO_PASS_30D=price_xxx                 # 100 PLN one-time, 30-day pass (BLIK fallback)
PRO_MONTHLY_AUDIT_ALLOWANCE=40                      # placeholder until per-audit COGS is measured
FREE_SIGNUP_CREDITS=3
PAST_DUE_GRACE_DAYS=7

# --- AI / external data ---
OPEN_ROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MONTHLY_BUDGET_USD=50                    # hard stop: workers refuse vision when exceeded
OPENROUTER_CALL_ESTIMATE_USD=0.02                   # reserved per call until settled with the real cost (placeholder, L-003)
IMAGE_HOST_ALLOWLIST=olxcdn.com,otodom.pl           # photo hosts we may fetch from (https only); see L-006
BDL_API_KEY=
OTODOM_HTTP_BACKEND=curl_cffi
OTODOM_MAX_RPS=1
NOMINATIM_USER_AGENT="RentMonitor/1.0 (ops@rentmonitor.pl)"

# --- Workers ---
WORKER_AUDIT_CONCURRENCY=1                          # raise to 2 only after the memory load test
WORKER_BATCH_CONCURRENCY=1
AUDIT_JOB_TIMEOUT_S=900

# --- Observability ---
SENTRY_DSN=https://$APPLICATION_TOKEN@$INGESTING_HOST/$APPLICATION_ID   # Better Stack Errors DSN for the Sentry SDK (ADR 0009)
SENTRY_TRACES_SAMPLE_RATE=0.05
BETTERSTACK_HEARTBEAT_BACKUP_URL=https://incidents.betterstack.com/api/v1/heartbeat/XXX
LOG_LEVEL=INFO
LOG_JSON=true
VITE_UMAMI_WEBSITE_ID=00000000-0000-0000-0000-000000000000
VITE_UMAMI_SCRIPT_URL=https://cloud.umami.is/script.js

# --- Backups (Cloudflare R2, S3-compatible) ---
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=rentmonitor-backups
BACKUP_AGE_RECIPIENT=age1xxx                        # public key; private key lives offline
BACKUP_RETENTION_DAILY=14
BACKUP_RETENTION_WEEKLY=8

# --- WAL-G continuous archiving (postgres and backup containers) ---
WALG_S3_PREFIX=s3://rentmonitor-backups/wal
AWS_ENDPOINT=https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
AWS_REGION=auto
AWS_S3_FORCE_PATH_STYLE=true
AWS_ACCESS_KEY_ID=${R2_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${R2_SECRET_ACCESS_KEY}
WALG_COMPRESSION_METHOD=zstd
WALG_LIBSODIUM_KEY=change-me-32-bytes-hex          # copy also kept offline; without it backups are unreadable
PGHOST=postgres

# --- Invoicing (Fakturownia) ---
FAKTUROWNIA_DOMAIN=yourcompany                      # yourcompany.fakturownia.pl
FAKTUROWNIA_API_TOKEN=xxx
```

Logging: the request asked for Loguru; the existing packages use structlog. Keep **structlog** with its JSON renderer everywhere — two logging libraries in one process means two formats in one log stream. Bind `request_id`, `user_id`, `audit_id` and `job_id` as context variables.

### 4.3 Compose and Caddy

```yaml
# deploy/compose.yml
x-py: &py
  image: ghcr.io/you/rentmonitor-py:${IMAGE_TAG:-latest}
  env_file: ../.env
  restart: unless-stopped
  depends_on: { postgres: { condition: service_healthy } }
  logging: { driver: json-file, options: { max-size: "20m", max-file: "5" } }

services:
  postgres:
    build: ./postgres            # postgres:17 (Debian) + wal-g binary; Dockerfile in Section 6
    env_file: ../.env
    command: ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
    volumes: ["pgdata:/var/lib/postgresql/data", "./postgres/postgresql.conf:/etc/postgresql/postgresql.conf:ro"]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"], interval: 5s, retries: 10 }
    mem_limit: 3g
    memswap_limit: 3g
    mem_reservation: 2g
    cpus: 2.0
    oom_score_adj: -900
    shm_size: 256m
    restart: unless-stopped

  api:
    <<: *py
    command: ["uvicorn", "rm_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "3", "--proxy-headers", "--forwarded-allow-ips", "*"]
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"], interval: 15s }
    mem_limit: 1536m
    memswap_limit: 1536m
    mem_reservation: 768m
    cpus: 2.0

  worker-audit:
    <<: *py
    command: ["procrastinate", "--app=rm_worker.app.app", "worker", "--queues=audit", "--concurrency=${WORKER_AUDIT_CONCURRENCY:-1}"]
    mem_limit: 3g
    memswap_limit: 3g
    mem_reservation: 1536m
    cpus: 3.0
    cpuset: "2-5"
    oom_score_adj: 500
    stop_grace_period: 60s

  worker-batch:
    <<: *py
    command: ["procrastinate", "--app=rm_worker.app.app", "worker", "--queues=city_refresh,ranking,screener", "--concurrency=1"]
    mem_limit: 2g
    memswap_limit: 2g
    mem_reservation: 512m
    cpus: 1.5
    cpuset: "4-5"
    oom_score_adj: 600
    stop_grace_period: 120s

  caddy:
    build: { context: .., dockerfile: deploy/caddy/Dockerfile }
    ports: ["80:80", "443:443", "443:443/udp"]
    volumes: ["caddy_data:/data", "caddy_config:/config"]
    environment: { PUBLIC_HOST: "app.rentmonitor.pl" }
    depends_on: [api]
    mem_limit: 128m
    memswap_limit: 128m
    cpus: 0.5
    oom_score_adj: -500
    restart: unless-stopped

  backup:
    build: ./backup               # also contains wal-g; no Docker socket mounted
    env_file: ../.env
    volumes: ["pgdata:/var/lib/postgresql/data:ro"]   # wal-g backup-push reads PGDATA directly
    depends_on: { postgres: { condition: service_healthy } }
    mem_limit: 256m
    cpus: 0.5
    oom_score_adj: 800
    restart: unless-stopped   # runs supercronic: 02:30 Europe/Warsaw daily

volumes: { pgdata: {}, caddy_data: {}, caddy_config: {} }
```

```text
# deploy/caddy/Caddyfile
{$PUBLIC_HOST} {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        Content-Security-Policy "default-src 'self'; script-src 'self' https://cloud.umami.is https://accounts.google.com; style-src 'self' https://accounts.google.com/gsi/style; connect-src 'self' https://cloud.umami.is <Better Stack ingesting host from SENTRY_DSN> https://accounts.google.com; img-src 'self' data: https:; frame-src https://accounts.google.com https://checkout.stripe.com https://billing.stripe.com"
    }
    @internal path /healthz /readyz
    respond @internal 404

    @sse path_regexp sse ^/api/audits/[0-9a-f-]+/events$
    handle @sse {
        reverse_proxy api:8000 {
            flush_interval -1          # stream SSE immediately
        }
    }
    handle /api/* {
        reverse_proxy api:8000
    }
    handle {
        root * /srv/www
        try_files {path} /index.html
        file_server
    }
}
```

### 4.4 Bootstrap sequence

Local development (Docker Desktop or Linux):

```bash
# 0. Toolchain
curl -LsSf https://astral.sh/uv/install.sh | sh
# Node 22 LTS, only to build the frontend

# 1. Dependencies
uv sync --all-packages --group dev
npm ci --prefix frontend
cp .env.example .env    # fill test keys; APP_ENV=development

# 2. Data plane
docker compose -f deploy/compose.yml -f deploy/compose.dev.yml up -d postgres

# 3. Schemas (one tool for the app, one for the queue)
uv run alembic upgrade head
uv run procrastinate --app=rm_worker.app.app schema --apply

# 4. Seed plans, flags, and migrate existing filesystem data
uv run python scripts/seed.py                       # plans free/pro, feature flags, admin user role
uv run python scripts/import_agent_context.py apps/agent-context/reports   # sidecars -> market_sidecar
uv run python scripts/import_legacy_reports.py apps/deal_analyzer/reports/final --owner admin@rentmonitor.pl

# 5. Generate the typed frontend client
uv run python scripts/gen_openapi.py > frontend/openapi.json
npx --prefix frontend openapi-typescript openapi.json -o src/api/schema.d.ts

# 6. Everything else
docker compose -f deploy/compose.yml -f deploy/compose.dev.yml up -d --build
stripe listen --forward-to http://localhost/api/billing/webhook   # prints whsec_ for .env
```

Production (fresh VPS, Debian 13 or Ubuntu 24.04):

```bash
# host hardening + swap
adduser deploy && usermod -aG sudo deploy
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && systemctl reload ssh
ufw default deny incoming && ufw allow 22,80,443/tcp && ufw allow 443/udp && ufw enable
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swap.conf && sysctl --system
curl -fsSL https://get.docker.com | sh && usermod -aG docker deploy

# deploy (as deploy)
git clone git@github.com:you/rentmonitor.git && cd rentmonitor && cp .env.example .env && $EDITOR .env
docker compose -f deploy/compose.yml up -d postgres
docker compose -f deploy/compose.yml run --rm api alembic upgrade head
docker compose -f deploy/compose.yml run --rm api procrastinate --app=rm_worker.app.app schema --apply
docker compose -f deploy/compose.yml run --rm api python scripts/seed.py
docker compose -f deploy/compose.yml up -d
curl -fsS https://app.rentmonitor.pl/api/me -o /dev/null -w '%{http_code}\n'   # expect 401
```

Release after the first: build and push the image in CI, then `IMAGE_TAG=<sha> docker compose up -d`. Migrations run as a one-off `run --rm api alembic upgrade head` before `up`; every migration must be backward-compatible with the previous image (expand, deploy, contract).

### 4.5 Core implementation

The snippets below are the load-bearing code paths. They assume `stripe` ≥ 12 (`StripeClient.v1`, `*_async` methods), `procrastinate` 3.x, `sqlalchemy` 2.0 with `psycopg` 3, and `sse-starlette`. Pin these in `uv.lock` and treat any API-shape difference as a compile error to fix, not a reason to change the design.

#### a) Authentication and entitlement dependencies

`current_principal` opens its own short session instead of depending on the request-scoped one, so a long SSE stream never pins a pooled connection.

```python
# services/rm_api/deps.py
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID, uuid4

from cachetools import TTLCache
from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rm_core.db.models import ChargeSource, User, UserSession
from rm_core.entitlements import load_entitlements
from rm_core.ledger import ensure_credit_account, reserve
from rm_core.settings import settings
from rm_api.problems import Problem


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    email: str
    email_verified: bool
    role: str | None


_cache: TTLCache[str, Principal] = TTLCache(maxsize=10_000, ttl=30)


async def current_principal(request: Request) -> Principal:
    raw = request.cookies.get(settings.session_cookie_name)
    if not raw:
        raise Problem.unauthorized()
    token_hash = hashlib.sha256(raw.encode()).hexdigest()   # DB never sees the raw token
    if (hit := _cache.get(token_hash)) is not None:
        return hit
    async with request.app.state.sessionmaker() as db:
        row = (await db.execute(
            select(User.id, User.email, User.email_verified_at.is_not(None), User.role)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash, UserSession.expires_at > func.now())
        )).one_or_none()
    if row is None:
        raise Problem.unauthorized()
    principal = Principal(*row)
    _cache[token_hash] = principal
    return principal


CurrentUser = Annotated[Principal, Depends(current_principal)]


async def require_admin(p: CurrentUser) -> Principal:
    if p.role != "admin":
        raise Problem.forbidden("ADMIN_ONLY")
    return p


@dataclass(frozen=True, slots=True)
class Reservation:
    audit_id: UUID            # pre-allocated; the route must create the Audit with this id
    feature: str
    source: ChargeSource
    usage_period_id: int | None
    cost: int


def require_quota_or_entitlement(feature: str) -> Callable[..., Awaitable[Reservation]]:
    """Locks the user's quota rows and decrements them inside the request transaction.

    Nothing is committed here: the route commits the reservation together with the
    Audit row, or the request rolls back and the reservation never happened.
    """
    async def dependency(principal: CurrentUser, db: DB) -> Reservation:
        if not principal.email_verified:                 # verified by Google or by magic link
            raise Problem.forbidden("EMAIL_NOT_VERIFIED")
        await ensure_credit_account(db, principal.user_id, verified=True)  # idempotent signup grant
        ent = await load_entitlements(db, principal.user_id)
        if not ent.feature_enabled(feature):
            raise Problem.payment_required("FEATURE_NOT_IN_PLAN", feature=feature)
        res = await reserve(db, principal.user_id, feature, ent, audit_id=uuid4())
        if res is None:
            raise Problem.payment_required("QUOTA_EXHAUSTED", upgrade_url="/billing")
        return res
    return dependency
```

```python
# packages/rm_core/ledger.py
FEATURE_COST = {"deal_audit": 1, "deal_audit_analyst": 2, "redesign": 1}


async def ensure_credit_account(db: AsyncSession, user_id: str, *, verified: bool) -> None:
    await db.execute(pg_insert(CreditAccount).values(user_id=user_id, balance=0)
                     .on_conflict_do_nothing(index_elements=["user_id"]))
    if not verified:
        return
    granted = (await db.execute(
        pg_insert(CreditLedger).values(
            user_id=user_id, delta=settings.free_signup_credits,
            reason=CreditReason.signup_grant, idempotency_key=f"signup:{user_id}")
        .on_conflict_do_nothing(index_elements=["idempotency_key"]).returning(CreditLedger.id)
    )).scalar_one_or_none()
    if granted is not None:
        await db.execute(update(CreditAccount).where(CreditAccount.user_id == user_id)
                         .values(balance=CreditAccount.balance + settings.free_signup_credits))


async def reserve(db, user_id, feature, ent, *, audit_id) -> Reservation | None:
    cost = FEATURE_COST[feature]
    if ent.is_pro:                                   # 1) spend the expiring allowance first
        period = (await db.execute(
            select(UsagePeriod)
            .where(UsagePeriod.user_id == user_id,
                   UsagePeriod.period_start <= func.now(), UsagePeriod.period_end > func.now())
            .order_by(UsagePeriod.period_end.desc()).limit(1).with_for_update()
        )).scalar_one_or_none()
        if period is not None and period.used + cost <= period.allowance:
            period.used += cost
            return Reservation(audit_id, feature, ChargeSource.plan, period.id, cost)
    acct = (await db.execute(                         # 2) then non-expiring credits
        select(CreditAccount).where(CreditAccount.user_id == user_id).with_for_update()
    )).scalar_one()
    if acct.balance < cost:
        return None
    acct.balance -= cost
    return Reservation(audit_id, feature, ChargeSource.credit, None, cost)


async def record_reservation(db: AsyncSession, res: Reservation, user_id: str) -> None:
    """Call after the Audit row is flushed (FK)."""
    if res.source is ChargeSource.credit:
        db.add(CreditLedger(user_id=user_id, delta=-res.cost, reason=CreditReason.reserve,
                            idempotency_key=f"reserve:{res.audit_id}", audit_id=res.audit_id))


async def settle(db: AsyncSession, audit: Audit, *, capture: bool) -> None:
    """Idempotent: only a 'reserved' audit moves. Runs in the worker's final transaction."""
    if audit.charge_state is not ChargeState.reserved:
        return
    if capture:
        audit.charge_state = ChargeState.captured
        return
    cost = FEATURE_COST["deal_audit_analyst" if audit.analyst else "deal_audit"]
    if audit.charge_source is ChargeSource.plan:
        await db.execute(update(UsagePeriod).where(UsagePeriod.id == audit.usage_period_id)
                         .values(used=UsagePeriod.used - cost))
    elif audit.charge_source is ChargeSource.credit:
        await db.execute(select(CreditAccount).where(CreditAccount.user_id == audit.user_id).with_for_update())
        await db.execute(update(CreditAccount).where(CreditAccount.user_id == audit.user_id)
                         .values(balance=CreditAccount.balance + cost))
        db.add(CreditLedger(user_id=audit.user_id, delta=cost, reason=CreditReason.release,
                            idempotency_key=f"release:{audit.id}", audit_id=audit.id))
    audit.charge_state = ChargeState.released
```

#### b) Audit submission, background job and SSE progress stream

```python
# services/rm_api/routers/audits.py
@router.post("", status_code=202, response_model=AuditAccepted)
async def create_audit(
    body: AuditCreate,
    principal: CurrentUser,
    db: DB,
    res: Annotated[Reservation, Depends(require_quota_or_entitlement("deal_audit"))],
) -> AuditAccepted:
    await upsert_listing_stub(db, body.listing_ref)
    audit = Audit(
        id=res.audit_id, user_id=principal.user_id, otodom_id=body.listing_ref,
        status=AuditStatus.queued, charge_source=res.source, charge_state=ChargeState.reserved,
        usage_period_id=res.usage_period_id, lang=body.lang, analyst=body.analyst,
        engine_version=ENGINE_VERSION, schema_version=DEAL_ANALYSIS_SCHEMA_VERSION,
    )
    db.add(audit)
    try:
        await db.flush()                      # hits uq_audit_one_active_per_listing
    except IntegrityError:
        await db.rollback()                   # also undoes the reservation
        existing = await active_audit_id(db, principal.user_id, body.listing_ref)
        raise Problem.conflict("AUDIT_IN_PROGRESS", audit_id=str(existing))
    await record_reservation(db, res, principal.user_id)
    db.add(AuditEvent(audit_id=audit.id, kind="progress", stage="queued", pct=0))
    await db.commit()                         # reservation + audit are durable together

    # Enqueue after commit. If this call fails, reconcile_queued_audits re-defers within 60 s.
    with suppress(AlreadyEnqueued):
        await run_audit.configure(queueing_lock=f"audit:{audit.id}").defer_async(audit_id=str(audit.id))
    return AuditAccepted(audit_id=audit.id, status=audit.status,
                         events_url=f"/api/audits/{audit.id}/events", credits_remaining=None)
```

```python
# services/rm_worker/tasks/audit.py
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=settings.procrastinate_dsn, min_size=1, max_size=6),
    import_paths=["rm_worker.tasks.audit", "rm_worker.tasks.market", "rm_worker.tasks.maintenance"],
)

TERMINAL_CAPTURE = {AuditStatus.succeeded, AuditStatus.succeeded_degraded}


@app.task(name="run_audit", queue="audit", pass_context=True,
          retry=procrastinate.RetryStrategy(max_attempts=2, wait=30, retry_exceptions={TransientInfraError}))
async def run_audit(context: procrastinate.JobContext, audit_id: str) -> None:
    log = structlog.get_logger().bind(audit_id=audit_id, job_id=context.job.id)
    async with sessionmaker() as db, db.begin():
        audit = await db.get(Audit, UUID(audit_id), with_for_update=True)
        if audit is None or audit.status is not AuditStatus.queued:
            return                                         # idempotent: already handled
        audit.status, audit.started_at = AuditStatus.running, func.now()
        # copy what the engine needs: ORM objects are not used across transactions
        ref, lang, analyst = audit.otodom_id, audit.lang, audit.analyst

    sink = ProgressSink(sessionmaker, audit_id, loop=asyncio.get_running_loop())
    status, error_code, result = AuditStatus.failed_internal, "INTERNAL", None
    try:
        async with asyncio.timeout(settings.audit_job_timeout_s):
            # Child process, not a thread: a thread cannot be killed, so a timeout would only
            # stop waiting while the hung engine kept its memory and sockets.
            result = await run_engine_in_subprocess(
                ref, lang=lang, analyst=analyst, sink=sink,
            )
        status = AuditStatus.succeeded_degraded if result.degraded else AuditStatus.succeeded
        error_code = None
    except ListingIsRent:
        status, error_code = AuditStatus.rejected, "RENT_NOT_DEAL"
    except FractionalOwnership:
        status, error_code = AuditStatus.rejected, "FRACTIONAL_OWNERSHIP"
    except ListingGone:
        status, error_code = AuditStatus.failed_input, "LISTING_GONE"
    except UpstreamBlocked:
        status, error_code = AuditStatus.failed_upstream, "UPSTREAM_BLOCKED"
    except UpstreamSchemaDrift:
        status, error_code = AuditStatus.failed_upstream, "UPSTREAM_SCHEMA_DRIFT"
        sentry_sdk.capture_exception()
    except TimeoutError:
        status, error_code = AuditStatus.failed_internal, "TIMEOUT"
    except TransientInfraError:
        await reset_to_queued(audit_id)                    # Procrastinate retries
        raise
    except Exception:
        log.exception("audit.crashed")
        sentry_sdk.capture_exception()

    async with sessionmaker() as db, db.begin():           # one final transaction
        audit = await db.get(Audit, UUID(audit_id), with_for_update=True)
        audit.status, audit.error_code, audit.finished_at = status, error_code, func.now()
        if result is not None:
            audit.result = result.model_dump(mode="json")
            audit.snapshot_id = result.provenance.snapshot_id
            # copied, never computed
            audit.grade = result.verdict.grade
            audit.asking_price_pln = result.listing.price_pln
            audit.max_bid_pln = result.valuation.max_bid_pln
            audit.irr_10y = result.returns.irr_10y
            audit.capex_pln = result.capex.total_pln
        await settle(db, audit, capture=status in TERMINAL_CAPTURE)
        await sink.emit_in(db, kind="done" if error_code is None else "error", stage="done", pct=100,
                           payload={"status": status, "error_code": error_code, "grade": audit.grade})
    log.info("audit.finished", status=status, error_code=error_code)


@app.periodic(cron="* * * * *")
@app.task(queue="maintenance", queueing_lock="reconcile_queued_audits")
async def reconcile_queued_audits(timestamp: int) -> None:
    """Re-defer audits whose enqueue was lost, and fail audits stuck in 'running' > 2x timeout."""
    ...
```

The engine runs in a killable child process. The external audit flagged thread-pool exhaustion; with at most 3 audits per worker that cannot happen (the default pool holds `min(32, cpu_count + 4)` threads). The real defect was different: `asyncio.timeout` around `to_thread` stops waiting but cannot stop the thread, so a hung fetch or image decode keeps running after the audit is marked failed. A child process fixes that, returns all its memory after every audit, and turns an OOM kill into a clean `failed_internal` with the credit released. It costs a process start per audit (seconds, *estimate*).

```python
# services/rm_worker/engine_proc.py
import multiprocessing as mp, queue, time

_ctx = mp.get_context("spawn")          # fresh interpreter: no inherited DB pools or event loop


def _child(ref: str, lang: str, analyst: bool, q: mp.Queue) -> None:
    from deal_analyzer import analyze_listing
    from rm_core.context_repo import PostgresContextRepository   # its own sync connection
    try:
        result = analyze_listing(
            ref, context=PostgresContextRepository(settings.database_url_sync),
            progress=lambda stage, pct, msg="": q.put(("progress", stage, pct, msg)),
            lang=lang, analyst=analyst, vision_budget=OpenRouterBudget.from_settings())
        q.put(("result", result.model_dump_json()))
    except BaseException as e:            # domain errors cross the boundary by class name
        q.put(("error", type(e).__name__, str(e)))


async def run_engine_in_subprocess(ref, *, lang, analyst, sink) -> DealAnalysis:
    q = _ctx.Queue()
    p = _ctx.Process(target=_child, args=(ref, lang, analyst, q), daemon=True)
    p.start()
    deadline = time.monotonic() + settings.audit_job_timeout_s
    try:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError
            try:
                msg = await asyncio.to_thread(q.get, True, 1.0)     # 1 s poll, one short thread
            except queue.Empty:
                if not p.is_alive():
                    raise EngineCrashed(p.exitcode)                  # e.g. -9 after an OOM kill
                continue
            match msg:
                case ("progress", stage, pct, text):
                    await sink.emit(stage, pct, text)
                case ("result", payload):
                    return DealAnalysis.model_validate_json(payload)
                case ("error", name, text):
                    raise ENGINE_ERRORS.get(name, EngineError)(text)  # ListingIsRent, UpstreamBlocked, ...
    finally:
        if p.is_alive():
            p.kill()                       # SIGKILL frees memory and sockets at once
        p.join(5)
```

Inside the engine, every outbound call still gets explicit timeouts (Otodom via `curl_cffi`: connect 5 s, read 30 s; OpenRouter: 120 s), as the audit recommends, so most failures surface as typed errors long before the job deadline. `EngineCrashed` maps to `failed_internal` in the error table.

```python
# services/rm_worker/progress.py
class ProgressSink:
    def __init__(self, sessionmaker, audit_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self._sm, self._audit_id, self._loop = sessionmaker, audit_id, loop

    def threadsafe_emit(self, stage: str, pct: int, message: str = "") -> None:
        asyncio.run_coroutine_threadsafe(self.emit(stage, pct, message), self._loop).result(timeout=10)

    async def emit(self, stage: str, pct: int, message: str = "") -> None:
        async with self._sm() as db, db.begin():
            await self.emit_in(db, kind="progress", stage=stage, pct=pct, payload={"message": message})

    async def emit_in(self, db, *, kind, stage, pct, payload) -> None:
        ev = AuditEvent(audit_id=UUID(self._audit_id), kind=kind, stage=stage, pct=pct, payload=payload)
        db.add(ev)
        await db.flush()
        # NOTIFY is delivered on commit; the payload is only a wake-up, the table is the truth.
        await db.execute(select(func.pg_notify("audit_progress", f"{self._audit_id}:{ev.id}")))
```

```python
# services/rm_api/sse.py
class ProgressHub:
    """One LISTEN connection per API process, fanned out to in-memory queues."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._subs: dict[str, set[asyncio.Event]] = defaultdict(set)   # Event coalesces wake-ups

    async def run(self) -> None:                       # started as a task in lifespan
        backoff = 1
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(self._dsn, autocommit=True) as conn:
                    await conn.execute("LISTEN audit_progress")
                    await conn.execute("LISTEN session_revoked")   # cross-process principal-cache eviction
                    backoff = 1
                    async for note in conn.notifies():
                        if note.channel == "session_revoked":
                            evict_principals(note.payload)          # payload = user_id
                            continue
                        audit_id = note.payload.split(":", 1)[0]
                        for ev in self._subs.get(audit_id, ()):
                            ev.set()                                # idempotent: cannot overflow
            except Exception:                                       # never let the listener die
                log.exception("progress_hub.listener_failed")
                self.healthy = False                                # exposed on /readyz
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    @asynccontextmanager
    async def subscribe(self, audit_id: str) -> AsyncIterator[asyncio.Event]:
        ev = asyncio.Event()
        self._subs[audit_id].add(ev)
        try:
            yield ev
        finally:
            self._subs[audit_id].discard(ev)
            if not self._subs[audit_id]:
                del self._subs[audit_id]


@router.get("/{audit_id}/events")
async def audit_events(
    audit_id: UUID, request: Request, principal: CurrentUser,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID")] = None,
) -> EventSourceResponse:
    sm, hub = request.app.state.sessionmaker, request.app.state.hub
    async with sm() as db:
        if not await audit_owned_by(db, audit_id, principal.user_id):
            raise Problem.not_found()                     # 404, never 403: do not leak existence

    async def stream() -> AsyncIterator[dict]:
        cursor = last_event_id or 0
        async with hub.subscribe(str(audit_id)) as wake:
            while not await request.is_disconnected():
                wake.clear()                              # clear BEFORE reading: no lost wake-ups
                async with sm() as db:                    # short read, connection returned at once
                    events = await events_after(db, audit_id, cursor)
                for ev in events:
                    cursor = ev.id
                    yield {"id": str(ev.id), "event": ev.kind,
                           "data": json.dumps({"audit_id": str(audit_id), "stage": ev.stage,
                                               "pct": ev.pct, **ev.payload})}
                    if ev.kind in ("done", "error"):
                        return
                with suppress(TimeoutError):
                    await asyncio.wait_for(wake.wait(), timeout=15)   # also a 15 s safety poll

    return EventSourceResponse(stream(), ping=15)
```

Closing the tab no longer orphans work (audit finding 2.4): the job belongs to the queue, the credit is reserved, and the user can reopen the report and resume the stream from `Last-Event-ID`. Cancellation is explicit via `POST /api/audits/{id}/cancel`, which sets `cancelled` and releases the credit if the job has not started.

#### c) Idempotent Stripe webhook

```python
# services/rm_api/billing/webhook.py
GRANT_REASONS = {"subscription_create", "subscription_cycle"}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    payload = await request.body()                     # raw bytes: never re-serialise before verifying
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise Problem.bad_request("INVALID_STRIPE_SIGNATURE")

    sc: stripe.StripeClient = request.app.state.stripe
    async with request.app.state.sessionmaker() as db, db.begin():
        # Idempotency gate. A concurrent duplicate blocks on the PK until we commit, then no-ops.
        claimed = (await db.execute(
            pg_insert(StripeEvent).values(
                id=event["id"], type=event["type"], api_version=event.get("api_version"),
                stripe_created=datetime.fromtimestamp(event["created"], UTC),
                outcome="received", payload=json.loads(payload))
            .on_conflict_do_nothing(index_elements=["id"]).returning(StripeEvent.id)
        )).scalar_one_or_none()
        if claimed is None:
            return {"status": "duplicate"}

    # Acknowledge fast (Stripe's guidance); process asynchronously and serially per subscription/user.
    with suppress(AlreadyEnqueued):
        await process_stripe_event.configure(
            lock=serialization_key(event),            # Procrastinate runs same-lock jobs one at a time
            queueing_lock=f"evt:{event['id']}",
        ).defer_async(event_id=event["id"])           # lost defer -> reconciler re-defers 'received' rows
    return {"status": "received"}


def serialization_key(event) -> str:
    obj = event["data"]["object"]
    if obj.get("object") == "subscription":
        return f"sub:{obj['id']}"
    if obj.get("object") == "invoice" and (sid := invoice_subscription_id(obj)):
        return f"sub:{sid}"
    if obj.get("object") == "checkout.session":
        return f"sub:{obj['subscription']}" if obj.get("subscription") else f"user:{obj['client_reference_id']}"
    return f"evt:{event['id']}"


@app.task(queue="billing", retry=procrastinate.RetryStrategy(max_attempts=8, wait=30))
async def process_stripe_event(event_id: str) -> None:
    async with sessionmaker() as db, db.begin():
        row = await db.get(StripeEvent, event_id, with_for_update=True)
        if row is None or row.outcome != "received":
            return                                     # idempotent
        event = stripe.Event.construct_from(row.payload, settings.stripe_secret_key)
        # Second guard besides Procrastinate's lock: same key is strictly serial, across any queue.
        # The Stripe object is retrieved AFTER this lock, so a slower handler cannot write stale state.
        await db.execute(select(func.pg_advisory_xact_lock(
            func.hashtextextended(serialization_key(event), 0))))
        handler = HANDLERS.get(event["type"])
        if handler is not None:
            await handler(db, stripe_client, event)
        row.outcome = "processed" if handler is not None else "ignored"


async def sync_subscription(db: AsyncSession, sc: stripe.StripeClient, sub_id: str, seen: datetime) -> Subscription:
    """Order-independent: always write Stripe's *current* state."""
    s = await sc.v1.subscriptions.retrieve_async(sub_id)
    item = s["items"]["data"][0]                       # single-price plans
    user_id = await user_for_customer(db, s["customer"]) or s["metadata"]["user_id"]
    values = {
        "user_id": user_id,
        "plan_code": await plan_for_price(db, item["price"]["id"]),
        "status": SubStatus(s["status"]),
        "price_id": item["price"]["id"],
        "current_period_start": ts(item["current_period_start"]),   # item-level since 2025-03-31.basil
        "current_period_end": ts(item["current_period_end"]),
        "cancel_at_period_end": s["cancel_at_period_end"],
        "stripe_seen_at": seen,
    }
    await db.execute(pg_insert(Subscription).values(id=s["id"], **values)
                     .on_conflict_do_update(index_elements=["id"], set_=values))
    return await db.get(Subscription, s["id"], populate_existing=True)


def invoice_subscription_id(inv) -> str | None:
    parent = inv.get("parent") or {}
    if parent.get("type") != "subscription_details":
        return None
    return parent["subscription_details"]["subscription"]


async def on_checkout_completed(db, sc, event) -> None:
    """Handles checkout.session.completed and checkout.session.async_payment_succeeded."""
    cs = event["data"]["object"]
    if cs["mode"] == "payment" and (cs.get("metadata") or {}).get("product") == "pro_pass_30d":
        if cs["payment_status"] == "paid":           # BLIK one-off is normally paid at completion
            await link_customer(db, user_id=cs["client_reference_id"], customer_id=cs["customer"])
            await grant_pass(db, cs)
        return
    if cs["mode"] != "subscription" or not cs.get("subscription"):
        return
    await link_customer(db, user_id=cs["client_reference_id"], customer_id=cs["customer"])
    await sync_subscription(db, sc, cs["subscription"], ts(event["created"]))


async def on_invoice_paid(db, sc, event) -> None:
    inv = event["data"]["object"]
    sub_id = invoice_subscription_id(inv)
    if sub_id is None:
        return
    sub = await sync_subscription(db, sc, sub_id, ts(event["created"]))
    sub.grace_until = None
    if inv["amount_paid"] > 0:
        await enqueue_vat_invoice(db, user_id=sub.user_id, stripe_invoice_id=inv["id"])  # every paid invoice
    if inv["billing_reason"] not in GRANT_REASONS:
        return
    plan = await db.get(Plan, sub.plan_code)
    await db.execute(pg_insert(UsagePeriod).values(
        user_id=sub.user_id, subscription_id=sub.id, source_invoice_id=inv["id"],
        # the invoice's own billing period, not whatever the subscription has advanced to since
        period_start=ts(inv["lines"]["data"][0]["period"]["start"]),
        period_end=ts(inv["lines"]["data"][0]["period"]["end"]),
        allowance=plan.monthly_audit_allowance,
    ).on_conflict_do_nothing(index_elements=["source_invoice_id"]))


async def on_invoice_payment_failed(db, sc, event) -> None:
    inv = event["data"]["object"]
    if (sub_id := invoice_subscription_id(inv)) is None:
        return
    sub = await sync_subscription(db, sc, sub_id, ts(event["created"]))
    if sub.grace_until is None:
        sub.grace_until = datetime.now(UTC) + timedelta(days=settings.past_due_grace_days)
        await send_dunning_email.defer_async(user_id=sub.user_id, invoice_id=inv["id"])


async def on_subscription_changed(db, sc, event) -> None:
    obj = event["data"]["object"]
    sub = await sync_subscription(db, sc, obj["id"], ts(event["created"]))
    if sub.status in (SubStatus.canceled, SubStatus.unpaid, SubStatus.incomplete_expired):
        await db.execute(update(UsagePeriod)
                         .where(UsagePeriod.subscription_id == sub.id, UsagePeriod.period_end > func.now())
                         .values(period_end=func.now()))


async def grant_pass(db: AsyncSession, cs) -> None:
    """30 days of Pro from a one-off BLIK/card payment. Stacks after any open period."""
    user_id = cs["client_reference_id"]
    # Serialize extensions per user: two different paid passes must stack to 60 days, not overlap.
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"pass:{user_id}", 0))))
    plan = await db.get(Plan, "pro")
    latest_end = await db.scalar(
        select(func.max(UsagePeriod.period_end))
        .where(UsagePeriod.user_id == user_id, UsagePeriod.period_end > func.now()))
    start = max(datetime.now(UTC), latest_end or datetime.now(UTC))
    await db.execute(pg_insert(UsagePeriod).values(
        user_id=user_id, kind="pass", subscription_id=None,
        source_invoice_id=cs.get("invoice") or cs["id"],   # invoice exists when invoice_creation is on
        period_start=start, period_end=start + timedelta(days=30),
        allowance=plan.monthly_audit_allowance,
    ).on_conflict_do_nothing(index_elements=["source_invoice_id"]))
    await enqueue_vat_invoice(db, user_id=user_id, stripe_invoice_id=cs["invoice"])  # same invoice lifecycle


async def enqueue_vat_invoice(db: AsyncSession, *, user_id: str, stripe_invoice_id: str) -> None:
    """Outbox row = the durable work record, written in the payment's own transaction.
    A 'billing' task drains pending rows (deferred after commit + every minute)."""
    await db.execute(pg_insert(VatInvoice).values(
        user_id=user_id, stripe_invoice_id=stripe_invoice_id, status="pending",
    ).on_conflict_do_nothing(index_elements=["stripe_invoice_id"]))


HANDLERS = {
    "checkout.session.completed": on_checkout_completed,
    "checkout.session.async_payment_succeeded": on_checkout_completed,
    "invoice.paid": on_invoice_paid,
    "invoice.payment_failed": on_invoice_payment_failed,
    "customer.subscription.updated": on_subscription_changed,
    "customer.subscription.deleted": on_subscription_changed,
}
```

Checkout creates the Stripe customer before redirecting, so `stripe_customer` always maps a customer to a user:

```python
@router.post("/checkout")
async def create_checkout(principal: CurrentUser, db: DB, request: Request) -> dict[str, str]:
    if (await load_entitlements(db, principal.user_id)).is_pro:
        raise Problem.conflict("ALREADY_SUBSCRIBED", portal_url="/api/billing/portal")
    sc = request.app.state.stripe
    customer_id = await ensure_stripe_customer(db, sc, principal)   # creates + commits on first use
    cs = await sc.v1.checkout.sessions.create_async(params={
        "mode": "subscription",
        "customer": customer_id,
        "client_reference_id": principal.user_id,
        "line_items": [{"price": settings.stripe_price_pro_monthly, "quantity": 1}],
        "subscription_data": {"metadata": {"user_id": principal.user_id}},
        "success_url": f"{settings.public_app_url}/billing?checkout=success",
        "cancel_url": f"{settings.public_app_url}/billing?checkout=cancelled",
        "locale": "pl",
        # BLIK here creates a recurring Model O mandate; requires blik_recurring_payments = active.
        # Confirmed in Stripe's API reference: Checkout create takes allowed_payment_method_types,
        # a filter on the dynamically eligible set (payment_method_types is not a create parameter).
        "allowed_payment_method_types": ["card", "blik"],
        "tax_id_collection": {"enabled": True},                  # NIP -> B2B -> KSeF invoice
        "customer_update": {"name": "auto", "address": "auto"},  # save NIP data on the existing customer
    })
    return {"url": cs["url"]}


@router.post("/checkout/pass")
async def create_pass_checkout(principal: CurrentUser, db: DB, request: Request) -> dict[str, str]:
    """One-off 30-day Pro pass for banks without recurring BLIK."""
    sc = request.app.state.stripe
    customer_id = await ensure_stripe_customer(db, sc, principal)
    cs = await sc.v1.checkout.sessions.create_async(params={
        "mode": "payment",
        "customer": customer_id,
        "client_reference_id": principal.user_id,
        "line_items": [{"price": settings.stripe_price_pro_pass_30d, "quantity": 1}],
        "allowed_payment_method_types": ["blik", "card"],         # one-off: no mandate is created
        "tax_id_collection": {"enabled": True},
        "customer_update": {"name": "auto", "address": "auto"},
        "invoice_creation": {"enabled": True},
        "metadata": {"user_id": principal.user_id, "product": "pro_pass_30d"},
        "success_url": f"{settings.public_app_url}/billing?pass=success",
        "cancel_url": f"{settings.public_app_url}/billing?pass=cancelled",
        "locale": "pl",
    })
    return {"url": cs["url"]}
```

`user_for_customer` returning nothing (for example, a `stripe trigger` fixture with a customer you never created) records the event as `ignored` instead of raising, so Stripe does not retry it for days.

Concurrent duplicate deliveries do not need extra handling. The webhook transaction runs at Postgres's default READ COMMITTED isolation. A second `INSERT … ON CONFLICT DO NOTHING` with the same event id waits on the first transaction's uncommitted row. If the first commits, the second returns no row and answers `duplicate`; if the first rolls back, the second processes the event. Serialization errors only occur at REPEATABLE READ or SERIALIZABLE, so the external audit's concern does not apply as long as nobody raises the isolation level for this endpoint. `test_webhook_concurrent_duplicate` pins this: two identical signed posts sent in parallel produce one `stripe_event` row and one 200 `duplicate`.

### 4.6 Local testing and verification protocol

Every test runs offline. External systems are replaced at their client boundary: Otodom and OpenRouter by fixture-backed fakes, Stripe by a stub `StripeClient` plus locally signed webhook payloads, Postgres by a real Postgres 17 in Testcontainers (never SQLite — the schema relies on partial indexes, `NULLS NOT DISTINCT` and `LISTEN/NOTIFY`).

**Test harness**

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def pg_url():
    with PostgresContainer("postgres:17-alpine") as pg:
        url = pg.get_connection_url(driver="psycopg")
        alembic_upgrade(url, "head")
        procrastinate_apply_schema(url)
        yield url


@pytest.fixture
async def client(pg_url, fake_otodom, fake_openrouter, fake_stripe):
    app = create_app(settings.model_copy(update={"database_url": pg_url}),
                     otodom=fake_otodom, openrouter=fake_openrouter, stripe=fake_stripe)
    async with LifespanManager(app), AsyncClient(transport=ASGITransport(app), base_url="http://test") as c:
        yield c
    await truncate_app_tables(pg_url)


@pytest.fixture
async def login(pg_url):
    async def _login(client, *, verified=True, role=None) -> str:
        user_id, token = await insert_user_and_session(pg_url, verified=verified, role=role)
        client.cookies.set(settings.session_cookie_name, token)
        return user_id
    return _login


def stripe_sign(payload: bytes, secret: str, t: int | None = None) -> str:
    t = t or int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"
```

Run the worker in-process for integration tests with `await app.run_worker_async(queues=["audit"], wait=False)`, which drains queued jobs and returns.

**Required tests (CI blocks merge if any is missing or skipped)**

| Test | Asserts |
| --- | --- |
| `test_invariant_rent_is_not_a_deal` | A RENT fixture ends `rejected` / `RENT_NOT_DEAL`, no vision call is made, the credit is released |
| `test_invariant_asking_is_not_deed` | Inserting a `moniter_asking` row with `price_basis='deed'` raises `IntegrityError`; `ContextRepository` returns asking and deed as distinct types |
| `test_invariant_admin_fee_is_opex` | A fixture with `characteristics.rent = 600` shows 600 PLN/month in OPEX and 0 in income |
| `test_invariant_deterministic_math` | Same snapshot + same vision stub → byte-identical `returns` block across two runs; LLM adjustment outside ±15% is clamped |
| `test_no_frontend_finance` | CI step fails if `frontend/src/lib/cashflow.ts` or `appreciation.ts` exist |
| `test_quota_race` | 10 concurrent `POST /api/audits` with 3 credits → exactly 3 × 202 and 7 × 402; balance 0; `SUM(delta)` equals balance |
| `test_duplicate_active_audit` | Second submit of the same listing while queued → 409 with the first `audit_id` |
| `test_failed_audit_releases` | `UPSTREAM_BLOCKED` fake → credit back, ledger has `reserve` + `release` |
| `test_webhook_signature` | Bad signature → 400, nothing written |
| `test_webhook_replay` | Same `invoice.paid` posted twice → one `usage_period` |
| `test_webhook_out_of_order` | `deleted` then a late `updated` → final status `canceled` (stub returns current state) |
| `test_grace_period` | `payment_failed` → Pro until `grace_until`, Free one second after |
| `test_tenant_isolation` | User B gets 404 on user A's audit, its SSE stream and its saved listing |
| `test_sse_resume` | Reconnect with `Last-Event-ID: n` receives only events after `n` and ends on `done` |
| `test_google_token_validation` | Wrong audience, expired or tampered Google ID token → 401; a valid one creates exactly one user, one identity and one session |
| test\_google\_signup\_gets\_credits | First Google sign-in with email\_verified = true → 3 free audits, no email step; magic-link sign-in → 3 free audits once the link is used |
| test\_google\_links\_existing\_email | Magic-link user, then Google sign-in with the same verified email → one user, two identities; an unverified Google email never links; a used or expired magic link → 401 |
| test\_blik\_offered\_in\_checkout | Subscription and pass Checkout sessions created in Stripe test mode both offer blik (e2e marker) |
| test\_pass\_grants\_30\_days | Paid pass → Pro for 30 days; replayed event → one period; a second pass stacks to 60 days |
| test\_pass\_unpaid\_ignored | Completed session with payment\_status = unpaid grants nothing until async\_payment\_succeeded |
| test\_webhook\_concurrent\_duplicate | Two identical signed posts in parallel → one stripe\_event row, one processed and one duplicate response, no serialization error |
| test\_engine\_timeout\_kills\_child | A fake engine that sleeps past the deadline → child process gone, audit failed\_internal / TIMEOUT, credit released |
| test\_vat\_invoice\_idempotent | Replayed invoice.paid → one vat\_invoice row and one Fakturownia call (stubbed); a buyer without NIP gets no invoice until requested |
| test\_subscription\_events\_adverse\_order | updated and deleted for one subscription run concurrently with the stub forcing the stale handler to commit last → final status canceled |
| test\_pass\_parallel\_stacks | Two different paid pass sessions for one user processed in parallel → 60 sequential days and two vat\_invoice rows |
| test\_worker\_death\_releases\_credit | Worker killed mid-audit → reconciler marks failed\_internal and the credit returns |
| test\_sse\_burst\_listener\_survives | 10,000 NOTIFYs for one audit → listener alive, stream still ends on done |
| test\_google\_unverified\_rejected | email\_verified = false → 401 GOOGLE\_EMAIL\_UNVERIFIED, no user created, existing same-email user untouched |
| test\_has\_pro\_fails\_closed | Local status active but period end + 48 h passed → Free |

```bash
uv run pytest -m "not e2e" -q                         # unit + integration, offline
uv run pytest -m invariant -q                         # the four invariants alone
npx --prefix frontend tsc --noEmit                    # catches API contract drift
```

**Manual auth check** (in development the mailer logs the magic link instead of sending it; check Google sign-in in the browser with your own account against `http://localhost`):

```bash
docker compose -f deploy/compose.yml -f deploy/compose.dev.yml up -d
curl -s -c jar -H 'Origin: http://localhost' -H 'Content-Type: application/json' \
  -d '{"email":"test@example.pl"}' http://localhost/api/auth/email/start
TOKEN=$(docker compose logs api | grep -o 'login/email#t=[A-Za-z0-9_-]*' | tail -1 | cut -d= -f2)
curl -s -b jar -c jar -H 'Origin: http://localhost' -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\"}" http://localhost/api/auth/email/verify
curl -s -b jar http://localhost/api/me | jq '.credits'          # expect 3
curl -s -b jar -c jar -H 'Origin: http://localhost' -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\"}" http://localhost/api/auth/email/verify -w '%{http_code}\n'   # expect 401: single use
curl -s -b jar -H 'Origin: http://evil.example' -X POST http://localhost/api/audits -d '{}' -w '%{http_code}\n'   # expect 403
```

**Stripe locally with the Stripe CLI**

```bash
stripe login
stripe listen --forward-to http://localhost/api/billing/webhook \
  --events checkout.session.completed,checkout.session.async_payment_succeeded,invoice.paid,invoice.payment_failed,customer.subscription.updated,customer.subscription.deleted
# 1. Real subscribe flow: click Upgrade in the SPA, pay with test card 4242 4242 4242 4242
# 2. Renewal and dunning without waiting a month: use a test clock
stripe test_helpers test_clocks create --frozen-time $(date +%s)
#    create the customer on that clock (scripts/stripe_clock_customer.py), subscribe, then:
stripe test_helpers test_clocks advance clk_xxx --frozen-time $(date -d '+32 days' +%s)
# 3. Failed renewal: attach test card 4000 0000 0000 0341 (attaches, then declines) before advancing
# 4. Replay to prove idempotency
stripe events resend evt_xxx
```

Check after each step: `SELECT status, grace_until FROM app.subscription;` and `SELECT * FROM app.usage_period ORDER BY id DESC LIMIT 3;`.

### 4.7 Backup, disaster recovery and health monitoring

Targets: **RPO 5 minutes, RTO 1 hour, from launch — targets, unverified until the first timed point-in-time restore.** Paying users mean a 24-hour loss of credits and saved listings is not acceptable, so continuous WAL archiving ships on day one; it costs nothing extra and about an hour of setup. The nightly logical dump below stays as a second, version-independent copy.

I rejected the external audit's suggestion of dumping only `credit_ledger` and `usage_period` every 4 hours. Restoring those over a nightly full dump gives an inconsistent database: ledger rows point at audits the nightly dump does not contain, and balances no longer match the ledger. WAL archiving restores the whole database to one consistent moment. Stripe stays the source of truth for subscriptions, so `usage_period` can also be rebuilt from Stripe events (retained 30 days, *inference* — check your account).

WAL-G in the Postgres container (custom image: `postgres:17` + the `wal-g` binary):

```text
# deploy/postgres/postgresql.conf (additions)
archive_mode = on
archive_command = 'wal-g wal-push %p'
archive_timeout = 300            # close a WAL segment at least every 5 min when there is activity
```

```bash
# env for the postgres container (R2 is S3-compatible)
WALG_S3_PREFIX=s3://rentmonitor-backups/wal
AWS_ENDPOINT=https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com
AWS_REGION=auto
AWS_S3_FORCE_PATH_STYLE=true
AWS_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY
WALG_COMPRESSION_METHOD=zstd
WALG_LIBSODIUM_KEY=<32-byte key kept in your password manager>

# nightly base backup + retention (cron in the backup container, which mounts pgdata read-only)
wal-g backup-push /var/lib/postgresql/data
wal-g delete retain FULL 14 --confirm   # 14 days, ADR 0011 (was 7)

# point-in-time restore on a fresh box
wal-g backup-fetch /var/lib/postgresql/data LATEST
touch /var/lib/postgresql/data/recovery.signal
# postgresql.conf: restore_command = 'wal-g wal-fetch %f %p'
#                  recovery_target_time = '2026-11-03 14:05:00+01'   (optional)
```

I have not tested WAL-G against R2 myself; the settings follow WAL-G's S3-compatible mode. Make the first restore drill a WAL-G point-in-time restore. Storage depends on write volume; alert when the bucket passes 7 GB of the 10 GB free tier.

The nightly logical dump (unchanged):

```sh
#!/usr/bin/env sh
# deploy/backup/backup.sh — run by supercronic at 02:30 Europe/Warsaw
set -eu
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/tmp/rentmonitor-$STAMP.dump.age
PREFIX=daily; [ "$(date -u +%u)" = "7" ] && PREFIX=weekly

# Better Stack heartbeat (ADR 0009): no start signal; report a failure on any non-zero exit
trap 'rc=$?; [ "$rc" -eq 0 ] || curl -fsS -m 10 "$BETTERSTACK_HEARTBEAT_BACKUP_URL/fail" >/dev/null || true' EXIT

PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --format=custom --compress=zstd:6 --no-owner \
  | age -r "$BACKUP_AGE_RECIPIENT" > "$OUT"

export RCLONE_CONFIG_R2_TYPE=s3 RCLONE_CONFIG_R2_PROVIDER=Cloudflare \
       RCLONE_CONFIG_R2_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
       RCLONE_CONFIG_R2_ENDPOINT="https://$R2_ACCOUNT_ID.r2.cloudflarestorage.com"
rclone copyto "$OUT" "r2:$R2_BUCKET/$PREFIX/$(basename "$OUT")" --s3-no-check-bucket
rclone check --one-way "$OUT" "r2:$R2_BUCKET/$PREFIX/" --include "$(basename "$OUT")"
rm -f "$OUT"

curl -fsS -m 10 "$BETTERSTACK_HEARTBEAT_BACKUP_URL" >/dev/null
```

Retention is enforced by R2 lifecycle rules, not by the script: expire `daily/` after 14 days and `weekly/` after 56 days. Twenty-two dumps fit the 10 GB free tier while each dump stays under ≈ 450 MB; alert at 300 MB. Add `BETTERSTACK_HEARTBEAT_BACKUP_URL` to `.env` from the Better Stack heartbeat (Uptime → Heartbeats, period 24 h, grace 1 h); a missed or failed heartbeat emails you.

**Monthly restore drill** (run on your laptop, where the age private key lives):

```bash
# deploy/backup/restore-drill.sh
LATEST=$(rclone lsf r2:rentmonitor-backups/daily/ | sort | tail -1)
rclone copyto "r2:rentmonitor-backups/daily/$LATEST" ./latest.dump.age
age -d -i ~/.config/rentmonitor/backup.key latest.dump.age > latest.dump
docker run -d --name drill -e POSTGRES_PASSWORD=drill -p 55432:5432 postgres:17-alpine && sleep 5
pg_restore -h localhost -p 55432 -U postgres -d postgres --create --no-owner latest.dump
psql -h localhost -p 55432 -U postgres -d rentmonitor -v ON_ERROR_STOP=1 <<'SQL'
SELECT version_num FROM app.alembic_version;                                   -- must equal repo head
SELECT count(*) AS users FROM app.app_user;
SELECT count(*) AS audits FROM app.audit;
SELECT a.user_id FROM app.credit_account a                                      -- must return 0 rows
 LEFT JOIN (SELECT user_id, SUM(delta) s FROM app.credit_ledger GROUP BY 1) l USING (user_id)
 WHERE a.balance <> COALESCE(l.s, 0);
SQL
docker rm -f drill && rm -f latest.dump latest.dump.age
```

Record the drill's wall-clock time; if it exceeds 30 minutes, the 1-hour RTO is at risk.

**Full recovery runbook** (VPS lost):

1. Order a new VPS, run the host-hardening block from 4.4, clone the repo, restore `.env` from your password manager.
2. `docker compose up -d postgres`, then `pg_restore` the latest dump into it (as in the drill, against the compose network).
3. `docker compose up -d`; confirm `/api/health` and one test audit.
4. Point the Cloudflare DNS record at the new IP (proxied records switch at once).
5. Stripe retries undelivered webhooks with backoff for several days, so subscription changes during the outage arrive on their own; spot-check the `stripe_event` table against the Dashboard's event log.
6. Before risky upgrades, also take an OVH VPS snapshot (paid option) — a faster rollback than a dump restore, but on the same provider, so not a backup. OVH's included daily backup (7-day retention, replicated within the same datacenter) is not off-site either.

**Health checks and resource monitoring**

| Signal | Mechanism | Threshold → action |
| --- | --- | --- |
| Site up | Better Stack uptime monitor on `https://app.rentmonitor.pl/api/health` (public, no DB) | 2 failures → email |
| Nightly backup | Better Stack heartbeat via the URL above (`/fail` on error) | Missed or failed → email |
| Container health | Docker `healthcheck` on postgres and api; `restart: unless-stopped` | Auto-restart; repeated restarts show in `docker events` |
| Readiness | `/readyz` (internal): `SELECT 1`, Procrastinate reachable | Used by the deploy script before cutting over |
| Queue | `maintenance` periodic task every 5 min: oldest `todo` job age, `audit` rows stuck in `running` | Oldest > 10 min or stuck > 2 × timeout → Better Stack warning (Sentry SDK) |
| Host | Same task: disk use from `shutil.disk_usage`, Postgres DB size, `numbackends` | Disk > 80%, connections > 50 → Better Stack warning (Sentry SDK) |
| Money | Nightly: ledger vs balance check; OpenRouter month-to-date spend vs `OPENROUTER_MONTHLY_BUDGET_USD` | Any mismatch → Better Stack error (Sentry SDK); spend > 80% → warning, 100% → vision disabled, audits run degraded |
| OOM | `docker inspect --format '{{.State.OOMKilled}}'` in the same task via the Docker socket proxy, or check `dmesg` weekly | Any OOM kill → Better Stack warning (Sentry SDK) with the container name |

### 4.8 Implementation order for the agent

1. **Engine foundation**: new `apps/deal_analyzer` with `ContextRepository` and `ProgressSink` as native interfaces, in-memory and filesystem implementations, and the four invariant tests written first.
2. **Data plane**: `rm-core` models, Alembic baseline, Procrastinate schema, importers for `agent-context` and `reports/final`. Invariant tests for asking ≠ deed.
3. **Auth** (Python only): Google ID-token sign-in and One Tap first, then email magic link; sessions, `current_principal`, Origin check, signup grant. Tenant-isolation, Google-token and magic-link tests.
4. **Audits**: submit route, worker task, SSE hub, reconciler. Quota race, release and SSE resume tests. Delete `frontend/server/*.ts`.
5. **Billing**: Checkout (card + BLIK recurring), the 30-day BLIK pass, Portal, webhook, entitlements, grace. All webhook and pass tests plus a test-clock run. Request BLIK recurring activation from Stripe on day one of this step. Add the Fakturownia invoice task and confirm on a trial account that API-created invoices reach KSeF.
6. **Frontend**: generated client, TanStack Query hooks, progress view on SSE, paywall on 402, removal of TS finance code.
7. **Ops**: compose, Caddy, backups, monitors, WAL-G archiving to R2, restore drill (a point-in-time restore) executed once and timed.
8. **Market and screener**: city refresh and ranking as `worker-batch` periodic tasks; screener approval queue behind the `screener` flag.

## 5. Risk register and open decisions

The largest risk is not infrastructure: it is the right and ability to scrape Otodom commercially.

| Risk | Likelihood / impact | Evidence status | Mitigation |
| --- | --- | --- | --- |
| Otodom terms of service and EU database rights prohibit commercial reuse | Unknown / product-ending | Not assessed here; not legal advice | Polish legal review before launch; position audits as user-initiated analysis of a single listing; keep raw snapshots private, never republished |
| Datacenter IP blocked by Otodom | Medium / audits fail | Inference; OVH ranges not tested | Test from the VPS in week 1; `UPSTREAM_BLOCKED` path releases credits; reserve the ≈ $10 headroom for a proxy |
| `_next/data` schema drift | High over a year / audits fail | Audit 3.2 documents the fragility | `UPSTREAM_SCHEMA_DRIFT` alert; recorded fixtures; contract test run nightly against one live listing |
| OpenRouter cost per audit exceeds plan economics | Unknown / margin | Not measured | Log tokens and USD per audit from day one; monthly budget kill-switch; set `PRO_MONTHLY_AUDIT_ALLOWANCE` from measured p90 cost |
| Single VPS failure | Low / hours of downtime | Accepted at this budget | Nightly encrypted R2 backups, monthly timed drill, 1-hour RTO runbook |
| Black Friday promo does not apply to an existing VPS | Unknown / miss the promo price | Not confirmed; OVH's 2025 promo page states no VPS conditions | Order a new promo VPS and migrate with the 4.7 runbook; otherwise commit the existing VPS at −15% |
| Stripe API shape drift | Medium / webhook errors | Confirmed for `basil` field moves | Pin `STRIPE_API_VERSION` on account, endpoint and SDK together |
| Stripe has not activated BLIK recurring on the account | Medium / BLIK subscriptions blocked at launch | Confirmed: both capabilities must be active; April 2026 changelog required support enablement | Request it this week; until active, card subscriptions and the one-off BLIK pass still cover BLIK users |
| Customer's bank is not on Stripe's BLIK recurring list (e.g. Pekao SA, BNP Paribas) | High / lost subscriptions | Confirmed: Stripe lists 9 supported banks | 30-day BLIK pass with expiry reminders; bank list shown in the paywall |
| KSeF e-invoicing for B2B customers | Certain for B2B / penalties from 1 Jan 2027 | Dates confirmed (ifirma); Stripe producing KSeF XML not found (inference) | Fakturownia issues and submits every B2B invoice from launch (Section 3); accountant confirms VAT and B2C treatment |
| Google OAuth app left in Testing mode | Low / only test users can sign in | Known Google Cloud behaviour | Publish to In production before launch (Section 2 checklist) |
| Google Identity Services changes One Tap behaviour (FedCM, prompt suppression) | Medium / One Tap shows less often | Inference from Google's ongoing FedCM migration | The explicit Google button and the magic link never depend on One Tap |

Open decisions that are yours, not technical:

- [ ] **VAT presentation of 100 PLN.** Individual investors are consumers (price shown gross, 23% VAT inside); companies expect net + VAT. Pick one before creating the Stripe Price. Stripe Tax adds 0.5% per transaction if you want it automated.
- [ ] **Pro allowance.** 40 audits/month is a placeholder; set it after two weeks of measured COGS.
- [ ] **Free tier scope.** Proposed: 3 audits, yield radar top 20, no screener, no redesign.
- [ ] **Payment fees.** At 100 PLN, a card costs 1.5% + 1.00 zł plus 0.7% Billing ≈ 3.20 zł; BLIK 1.6% + 1.00 zł plus 0.7% ≈ 3.30 zł. BLIK is required at launch; the one-off pass costs 1.6% + 1.00 zł ≈ 2.60 zł (whether Stripe adds an invoicing fee for the post-payment invoice is not verified).

## 6. Production hardening and release gates

The second external audit was right on almost every count, and its fixes are applied throughout Sections 1–4. This section records what changed, adds the pieces that had no home yet, and sets the seven gates that block a paid launch. Nothing here adds infrastructure beyond one small worker container.

| Finding | Verdict | Change made |
| --- | --- | --- |
| KSeF path not wired (no NIP collection, pass not invoiced, provider retries could duplicate, "issued" ≠ accepted) | Accepted | `tax_id_collection` on both Checkouts; subscriptions and passes share one `vat_invoice` outbox row; Fakturownia `oid` = Stripe invoice id with `oid_unique`; full status machine; alerts at 15 min / 2 h |
| Subscription events can commit stale state | Accepted | Webhook only persists + enqueues; per-subscription Procrastinate lock and advisory lock; Stripe object retrieved after the lock |
| `has_pro` fails open | Accepted | Active/trialing valid only until period end + 48 h; nightly `reconcile_subscriptions` |
| Concurrent passes overlap | Accepted | Per-user advisory lock around read-compute-insert |
| Grant policy vs code; late invoice period | Accepted | Table aligned with code; period taken from the invoice line |
| Host OOM "never"; CPU "reservation" | Accepted | Wording corrected; audit concurrency 1; per-child memory cap; image limits; cgroup metrics |
| Connection budget undercounted | Accepted | Every pool listed below; `max_connections=100` |
| BLIK Checkout parameter | Accepted, now confirmed | Stripe's API reference lists `allowed_payment_method_types` for Checkout create; snippets changed |
| WAL-G not wired | Accepted | Custom Postgres image, WAL-G env, backup container reads PGDATA read-only, archiver monitoring, RPO marked unverified |
| Unverified Google email collides with existing user | Accepted | Unverified Google emails rejected; magic link instead |
| Principal cache delays revocation | Accepted | `NOTIFY session_revoked` evicts across processes; TTL fallback stated |
| Non-atomic rate limit; SSE `QueueFull` kills listener | Accepted | Atomic upsert; `asyncio.Event` wake-ups, listener cannot die |
| Throttle fairness, total deadline, AI budget overshoot | Accepted | Below |
| No dispute/refund handling | Accepted | Below |

### Worker layout and memory admission

Billing and maintenance jobs move to their own small worker. With audit concurrency at 1 and the batch worker busy for hours on city refreshes, a Stripe event or invoice task must never queue behind either.

```yaml
  worker-ops:
    <<: *py
    command: ["procrastinate", "--app=rm_worker.app.app", "worker", "--queues=billing,maintenance", "--concurrency=2"]
    mem_limit: 256m
    memswap_limit: 256m
    cpus: 0.5
    cpuset: "2-5"
  worker-batch:   # queues now: city_refresh, ranking, screener
```

```dockerfile
# deploy/postgres/Dockerfile — Debian base: the wal-g release binaries are glibc builds
FROM postgres:17
ARG WALG_VERSION=<pin>
ADD https://github.com/wal-g/wal-g/releases/download/${WALG_VERSION}/wal-g-pg-ubuntu-22.04-amd64.tar.gz /tmp/walg.tgz
RUN tar -xzf /tmp/walg.tgz -C /usr/local/bin && mv /usr/local/bin/wal-g-pg-* /usr/local/bin/wal-g && rm /tmp/walg.tgz
```

The child-process boundary is a cancellation mechanism, not memory isolation: all audit children share the worker's 3 GB cgroup. Each child therefore caps itself before loading the engine:

```python
# first lines of _child(), before importing deal_analyzer
import resource
from PIL import Image
limit = settings.audit_child_max_bytes            # 2 GiB at concurrency 1; ~1.2 GiB at 2
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))   # MemoryError in the child, not a cgroup OOM
Image.MAX_IMAGE_PIXELS = 40_000_000               # refuse decompression bombs
```

Engine limits per audit: at most 25 photos, downscaled to a 1,600 px long edge before vision, at most 2 floor plans to OCR, and at most 4 OpenRouter calls in flight across the whole box. `RLIMIT_AS` counts virtual memory, and some native libraries reserve large virtual ranges; if it trips falsely in the load test, switch to `RLIMIT_DATA`. Each worker reports its own cgroup's `memory.peak` and the `oom_kill` count from `memory.events` every 5 minutes. A reconcile task fails any audit left `running` after its worker died and releases its credit.

### Connection budget, every pool counted

| Process | Pool | Peak connections |
| --- | --- | --- |
| API × 3 | SQLAlchemy 5 + 3 overflow | 24 |
| API × 3 | Procrastinate connector, defer only, `max_size=2` | 6 |
| API × 3 | LISTEN connection (progress + session revocation) | 3 |
| worker-audit | Procrastinate 4 + SQLAlchemy 3 | 7 |
| worker-batch | Procrastinate 4 + SQLAlchemy 3 | 7 |
| worker-ops | Procrastinate 3 + SQLAlchemy 2 | 5 |
| Engine children (audit + batch) | 1 sync connection each | 3 |
| Backup and WAL-G base backup | — | 2 |
| Migrations, psql, monitoring | reserved | 10 |
| **Peak** |  | **67 of `max_connections=100`** |

### Deadlines, fairness and the AI budget

- **One deadline per audit.** The engine receives a `Deadline` (900 s from start). Every retry first checks that enough time remains to be useful; a `Retry-After` longer than what remains fails the audit at once as `UPSTREAM_BLOCKED`.
- **Throttle without holding locks.** A request slot is reserved in a short transaction — `UPDATE host_throttle SET next_at = GREATEST(next_at, now()) + interval '1 second' WHERE host = 'otodom' RETURNING next_at` — and the wait happens after commit.
- **Interactive first.** Batch jobs reserve a slot only when no `audit` job is waiting or running, so a city refresh can never delay a paying user's audit by more than one request.
- **Atomic AI budget.** Before each OpenRouter call: `UPDATE ai_budget SET reserved = reserved + :est WHERE month = :m AND spent + reserved + :est <= cap RETURNING month`. No row → vision disabled, audit degraded. After the call, the estimate is swapped for the actual cost. A nightly sweep clears reservations left by crashed children.

### Disputes, refunds and invoice idempotency

- `charge.dispute.created` → Better Stack alert and email, recorded in a `payment_issue` table. Stripe's BLIK docs give 12 calendar days to submit evidence, so this alert pages, not just logs.
- `charge.refunded` on a pass → the pass's `usage_period` ends now. Any refund → a corrective invoice (*faktura korygująca*) through Fakturownia to KSeF; your accountant confirms the exact treatment.
- Fakturownia retries cannot duplicate. Its API documents an `oid` field and `oid_unique: "yes"`, which refuses a second invoice with the same `oid`. The task sends the Stripe invoice id as `oid`. On a duplicate-oid refusal (an earlier attempt succeeded but its response was lost), the task looks the invoice up instead of creating one. Fakturownia's README says invoices can be searched by `oid` but does not document the filter parameter — confirm it on the trial account.

```python
@app.task(queue="billing", retry=procrastinate.RetryStrategy(max_attempts=10, wait=60))
async def issue_vat_invoice(vat_invoice_id: int) -> None:
    async with sessionmaker() as db, db.begin():
        row = await db.get(VatInvoice, vat_invoice_id, with_for_update=True)
        if row.status in ("ksef_accepted", "ksef_rejected"):
            return
        if row.provider_invoice_id is None:
            payload = await build_invoice_payload(db, row)            # NIP, buyer, 23% VAT, PLN
            res = await fakturownia.create(payload | {"oid": row.stripe_invoice_id, "oid_unique": "yes"})
            if res.duplicate_oid:
                res = await fakturownia.find_by_oid(row.stripe_invoice_id)
            row.provider_invoice_id, row.number, row.status = res.id, res.number, "created"
        state = await fakturownia.ksef_state(row.provider_invoice_id)   # submitted | accepted | rejected
        row.status = {"submitted": "submitted", "accepted": "ksef_accepted",
                      "rejected": "ksef_rejected"}.get(state.kind, row.status)
        row.ksef_number, row.last_error, row.attempts = state.ksef_number, state.error, row.attempts + 1
    if row.status in ("created", "submitted"):
        raise StillPending                                            # Procrastinate retries in 60 s
```

### Release gates

A paid launch needs all seven to pass, with the evidence kept.

| # | Gate | Evidence |
| --- | --- | --- |
| 1 | KSeF end to end | On a Fakturownia trial: initial subscription, renewal via Stripe test clock, BLIK pass, card pass, buyer without NIP, later invoice request, provider timeout after creation, KSeF rejection, provider downtime. Each payment ends in exactly one accepted invoice or one alerted error |
| 2 | Billing concurrency | Two different events for one subscription committed in the adverse order leave it canceled; two parallel passes give 60 days |
| 3 | BLIK recurring | One live 100 zł subscription on an eligible bank creates a mandate and is refunded; an unsupported bank lands on the pass offer |
| 4 | Memory | 20 representative audits (largest photo sets, floor plans) while the batch queue runs; worker cgroup `memory.peak` recorded; concurrency 2 only if peak stays under 60% of the limit |
| 5 | Connections | Peak-load test with API, webhooks and audits; `pg_stat_activity` stays under 70 |
| 6 | Restore | WAL-G point-in-time restore to a chosen timestamp on a fresh VPS, timed, under 1 hour |
| 7 | Auth | Unverified Google token rejected; same-email collision handled; sign-out-everywhere evicts cached sessions in all API processes within 1 second |

## Sources

All opened 11 Oct 2026.

- [netcup VPS 1000 G12 product page](https://www.netcup.com/en/server/vps/vps-1000-g12-iv-12m) — €8.45 incl. VAT, 12-month term, specs
- [StackValueLab: Hetzner CX and CAX unavailable](https://stackvaluelab.com/hetzner-cx-cax-unavailable/) — availability and prices checked 2 Sep 2026
- [WZ-IT: Hetzner price increase June 2026](https://wz-it.com/en/blog/hetzner-price-increase-june-2026-cpx-ccx-alternatives/)
- [Neon pricing](https://neon.com/pricing)
- [Modal pricing](https://modal.com/pricing)
- [Vercel fair use guidelines](https://vercel.com/docs/limits/fair-use-guidelines) — Hobby is non-commercial
- [Cloudflare Containers pricing](https://developers.cloudflare.com/containers/pricing/)
- [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- [Better Stack pricing](https://betterstack.com/pricing) (chosen, ADR 0009); [Sentry SDK ingestion](https://betterstack.com/docs/errors/collecting-errors/sentry-sdk/)
- [Sentry pricing](https://sentry.io/pricing/) (original choice)
- [Umami pricing](https://umami.is/pricing)
- [Resend pricing](https://resend.com/pricing)
- [Stripe pricing, Poland](https://stripe.com/en-pl/pricing)
- [Stripe changelog: BLIK recurring off-session payments](https://docs.stripe.com/changelog/endive/2026-09-30/blik-recurring-off-session-payments)
- [Stripe changelog: subscription item billing periods (basil)](https://docs.stripe.com/changelog/basil/2025-03-31/deprecate-subscription-current-period-start-and-end)
- [Stripe changelog: invoice parent field (basil)](https://docs.stripe.com/changelog/basil/2025-03-31/adds-new-parent-field-to-invoicing-objects)
- [FastAPI Users repository](https://github.com/fastapi-users/fastapi-users) — maintenance-mode notice
- [arq repository](https://github.com/python-arq/arq) — maintenance-only notice
- [Procrastinate on PyPI](https://pypi.org/project/procrastinate/) — 3.10.0, 23 Sep 2026

Added for the hosting update (opened 11 Oct 2026):

- [OVHcloud VPS (PL)](https://www.ovhcloud.com/pl/vps/) — VPS-3 from 44.37 zł net, daily backup included
- [OVHcloud VPS Poland](https://www.ovhcloud.com/en/vps/vps-poland/) — Poland location availability
- [OVHcloud: managing commitments](https://docs.ovhcloud.com/en/guides/account-and-service-management/managing-billing-payments-and-services/manage-commitments) — commit later, starts at next renewal
- [OVHcloud Black Friday 2025](https://www.ovhcloud.com/pl/black-friday/) — no VPS conditions stated
- [NBP table A, 9 Oct 2026](https://api.nbp.pl/api/exchangerates/tables/A/?format=json) — USD 3.9022, EUR 4.3775
- Your screenshots: OVH VPS-3 configurator (52.20 zł net, no commitment) and netcup RS G12.5 price cards

Added for Google sign-in and BLIK (opened 11 Oct 2026):

- [Stripe: BLIK recurring payments](https://docs.stripe.com/payments/blik/recurring-payments) — capabilities, 2,000 zł cap, supported banks, Checkout subscriptions, disclosures
- [Stripe: BLIK payments](https://docs.stripe.com/payments/blik) — Checkout, Subscriptions, Invoicing support; disputes and refunds
- [Stripe changelog: BLIK in Stripe Billing](https://docs.stripe.com/changelog/dahlia/2026-04-22/stripe-billing-blik-recurring-payments) — Model O mandates, account-level enablement

Added for Python-only auth and the hosting split (opened 11 Oct 2026):

- [Google: verify the Google ID token on your server side](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token) — `verify_oauth2_token`, audience, `g_csrf_token`, key users by `sub`
- [Authlib on PyPI](https://pypi.org/project/Authlib/) — 1.8.0; considered and not needed, because GIS returns an ID token and no OAuth redirect runs on the server
- Your screenshot: OVH VPS-1 2027 at 19.20 zł net monthly; VPS-1/2/3 12-month prices 16.32 / 30.77 / 44.37 zł
