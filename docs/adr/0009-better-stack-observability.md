# ADR 0009 — Better Stack instead of Sentry for errors, uptime and cron monitoring

- **Status:** accepted · **Date:** 2026-10-12 · **Decided by:** maintainer · **Ticket:** RM-112
- **Amends:** blueprint §1 cost table, §4.2 env, §4.3 CSP, §4.7 monitoring; B-001

## Context
The blueprint priced Sentry Developer (free): 5k errors, 1 uptime monitor, 1 cron monitor, 30-day lookback. That is one
uptime check and one cron check for the whole product, and a tight error quota. The maintainer chose Better Stack: its
free tier is larger and covers more of what §4.7 needs in one account.

Better Stack free tier, read from betterstack.com/pricing on 2026-10-12 (re-check before launch):

| Capability | Free tier |
|---|---|
| Error tracking | 100,000 exceptions/month, 90-day retention |
| Uptime monitors | 10 |
| Heartbeats (cron) | 10 |
| Status page | 1 (1,000 subscribers) |
| Logs and traces | 3 GB/month each, 3-day retention |
| Alerts | email and Slack; on-call scheduling included |

## Decision
- **Errors:** keep the `sentry-sdk` Python client. Better Stack Errors accepts the Sentry SDK (≥ 2.0) and its traces;
  only the DSN changes (Better Stack → Errors → Application → Data ingestion). `SENTRY_DSN` and
  `SENTRY_TRACES_SAMPLE_RATE` keep their names because they configure that SDK. No code change; PII scrubbing
  (`rm_core.observability.scrub_event`) still runs before anything leaves the process.
- **Uptime:** Better Stack uptime monitor on the public `/api/health`.
- **Cron:** Better Stack heartbeat for the nightly backup. The script pings `BETTERSTACK_HEARTBEAT_BACKUP_URL` on success
  and `…/fail` on failure. Heartbeats have no "in progress" signal, so the start ping is dropped. Replaces
  `SENTRY_CRON_BACKUP_SLUG` and `SENTRY_CRON_CHECKIN_URL`, which no code read.
- **Logs:** optional, later. Shipping structlog JSON to Better Stack Logs is not part of this decision.

## Consequences
- Every "Sentry alert / warning / error" in the blueprint means an event captured through the Sentry SDK and shown in
  Better Stack.
- Better Stack becomes a processor of whatever survives scrubbing: add it to the processor list (`GDPR[processor]`) and
  sign its DPA (PRE-DEPLOYMENT §4). Its EU data-residency options were not confirmed; check before launch.
- Browser errors (Phase 2 SPA) need the CSP `connect-src` to allow the ingesting host from the DSN; set it when the
  frontend lands.
- The free tier may change; the limits above are a dated reading, not a contract.
