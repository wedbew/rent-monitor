# Blockers: things only the owner can unblock

Agents add a row the moment they hit one and stop that work (`.agent/rules/blockers.md`). Rows are never deleted.
Strategy (owner decision, 2026-10-11): **work locally until the whole app works, in Docker; deploy later.** Items that only
matter for production or a domain are *Deferred*, not blocking.

## Awaiting your approval (PRs the agent will not merge)

_None. #108 (ledger, entitlements, flags) and #109 (AI budget) were approved and merged on 2026-10-12; auth (#12) and audits (#13) are unblocked._

## Open (needs the owner)

| ID | What | Owner action | Waits on it |
|---|---|---|---|

## Deferred (not blocking local work)

| ID | What | Why deferred | Revisit when |
|---|---|---|---|
| B-001 | Better Stack Errors DSN, log export and monitors (ADR 0009) | **2026-10-12:** owner screenshots confirm a RentMonitor Python Telemetry source in the US region. Source ingestion token and URL saved in private `.env` with owner authorization; no telemetry sends made. API Sentry initializer exists; Errors application/DSN and delivery remain unverified, and worker initialization/log forwarding remain implementation work. Local handoff: `docs/BETTERSTACK-INTEGRATION.md` (gitignored); specification: `docs/OBSERVABILITY-SPEC.md` (note: `/healthz` and `/readyz` are internal; the external monitor uses `/api/health`; an open privacy gap is registered as L-013) | before launch: Errors application → Ingest → exact DSN in private `SENTRY_DSN`; verify error/log delivery and region/DPA; monitor reachable health URL (current routes `/healthz`, `/readyz`); backup heartbeat URL separately |
| B-002 | Umami analytics | **Owner created the Umami Cloud website (2026-10-12).** Script endpoint verified; events arriving is unverified (needs a page on an allowed domain). Frontend only, and no domain yet. The script posts to `gateway.umami.is`, which the blueprint CSP does not allow (L-010, needs a maintainer decision). Local notes: `docs/UMAMI-INTEGRATION.md` (gitignored); specification: `docs/ANALYTICS-SPEC.md` | Phase 2 frontend; CSP decision before the Caddy config |
| B-003 | Stripe: sandbox access, webhook secret, price ids, BLIK activation (#39) | **Verified 2026-10-12:** CLI 1.53.1 is authenticated, but the default account has **live access only**; test product listing and switching to sandbox were refused. Owner grants sandbox access via `stripe login --project-name rent-monitor`, then selects the sandbox. Project-profile authorization was started but is not yet confirmed. No billing resources created. Confirm D-03 VAT treatment before final prices; then prepare products/prices, Portal, BLIK, retries and local webhook signing secret. Details are in the owner's local handoff notes (`docs/STRIPE-INTEGRATION.md`, gitignored, not in the repo); the written specification is tracked in #127. Agents never use `--live`. Application billing still follows the API prerequisites | requested Stripe setup; billing step (#14); BLIK activation has lead time |
| B-004 | Google OAuth origins and Resend sending domain | **Google OAuth credentials are configured per owner**: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are in `.env` (2026-10-12; not inspected); secret JSON is gitignored. Source inspection confirms auth models/settings but no Google sign-in router, verifier or session authentication. Confirm existing Web client/origins and consent state; callback-based GIS needs no redirect URI or secret. **Resend account created per owner; supplied key saved privately and local `MAIL_FROM` set to the onboarding test sender (2026-10-12).** Key validity/delivery not tested; typed mail settings/client and verified customer-facing domain remain pending. Local instructions: `docs/RESEND-INTEGRATION.md` and `docs/GOOGLE-AUTH-INTEGRATION.md` (gitignored); Google specification tracked in #130, Resend specification: `docs/RESEND-SPEC.md` | end-to-end sign-in test of #12; customer-facing Resend needs verified domain/DNS (B-005) |
| B-005 | DNS (domain registered, see B-005b) | Not needed locally; records still registrar defaults, nothing points to the VPS | deployment preparation (RM-15) |
| B-012 | Legal review (#41): counsel confirms Otodom scraping and image use, privacy docs, processor list | Features are tagged and each has a default-on kill switch, so building is not blocked; scope list = the tag inventory in `.agent/rules/legal-tags.md` | before paid launch (PRE-DEPLOYMENT §4); start the accountant (VAT, KSeF penalties from 2027-01-01) early |
| B-006 | Otodom datacenter-IP test (#42) and VPS sizing decision (VPS bought, see B-006a) | Bought VPS-1 (4 GB) differs from the blueprint's VPS-3 (12 GB, Poland); VPS-2/3 Linux out of stock. Owner plans: VPS-1 as test/beta box, buy VPS-3 when stock returns (owner's local notes) | deployment preparation; IP test can run now |

## Resolved

| ID | What | Resolution | Date |
|---|---|---|---|
| B-005c | R2 connectivity | corrected S3 credentials saved privately; `scripts/check_r2_upload.py` uploaded 55 bytes to `rent-monitor` at `connection-tests/20261012T173240Z-f9eb4c3fe2594328bdeb6f2f194f0322.txt` and read back identical content. Test object retained. SHA-256: `2038114c0ffb30fe0da1ff2434f06a7f8605bbac59973461225660d76314a704`. Previous failure was an invalid access-key length. Specification: `docs/R2-SPEC.md` (open choices: EU jurisdiction, bucket layout, WAL-G retention) | 2026-10-12 |
| B-006a | VPS purchase | Owner bought an OVH VPS-1 (no commitment); details in the owner's local notes (not in the repo) | 2026-10-12 |
| B-005b | Domain registration | Owner registered the production domain at OVH; details in the owner's local notes (not in the repo) | 2026-10-12 |
| B-005a | R2 bucket and keys | Owner states the R2 values are in `.env` (not verified by agents, which cannot read it) | 2026-10-11 |
| B-007 | Engine specification | Owner approved `docs/ENGINE-SPEC.md` with amendments (rows 2, 3, 5, 6, 7, 9, 10, 13); tax items stay flagged for the accountant but are versioned constants and do not block code. #17 can be split into N-01..N-11 | 2026-10-11 |
| B-008 | `migrations` CI job and required check | Enabled: `ENABLE_MIGRATIONS_JOB=true`, `migrations` required on `staging`, squawk clean (RM-68). `invariants` stays off: it needs the engine's three missing named tests, see #17 | 2026-10-11 |
| B-014 | **Exit value anchor** (engine, not blocking code) | ENGINE-SPEC row 8 says exit value = *purchase price* grown by appreciation. With that, a lower bid also lowers the assumed sale value, so Max Bid falls about 2 PLN per 1 PLN of CAPEX; a buyer who gets a bargain still sells at market value. The engine implements the spec as written and supports an optional `market_value_pln` anchor (tested). Decide: keep the spec, or anchor on the market-value estimate (recommended: market value, using the asking price or the price model once N-04 exists). Reply in #43 | the Max Bid numbers users will see |
| B-015 | **CAPEX price list** | Provide renovation prices in PLN/m² per condition (good / refresh / renovation / shell) and per city tier (metro / major / other), or approve a data source to import. Until then `deal_analyzer.capex` uses labelled placeholders (L-007) | meaningful CAPEX, Max Bid and grades; paid launch |
| B-009 | semgrep `no-float-money` flagged every `x: float = ...` annotation (#55) | Owner approved the rule fix; every pattern now binds the name, rule tests run in CI (RM-55) | 2026-10-12 |
| B-010 | Agents could not read `.env.example` | Deny rule narrowed to real env files; agents read and edit `.env.example` (`rules/env-example.md`) | 2026-10-11 |
| B-011 | `.claude/settings.json` safety entries | Added deny `gh pr merge*--admin*`, ask on `gh repo edit*visibility*` and `gh repo delete*`. Agents merge into `staging` themselves; the human approval is on `staging` → `main` only, at launch, enforced by the ruleset | 2026-10-11 |
| B-012a | Retention defaults | Owner decided: sessions 30 d, login tokens valid 30 min and deleted 1 d after expiry, snapshots kept 30 d with seller data stripped at parse, audit events 30 d, log IP/UA 30 d, backups 14 d / 56 d; invoices per tax law (accountant). Details on #30; jobs built in RM-30; counsel may change the values (B-012) | 2026-10-12 |
| B-013 | Testcontainers reaper could not mount the Docker socket (macOS) | `tests/conftest.py` sets `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`; suite passes with the reaper on | 2026-10-11 |
