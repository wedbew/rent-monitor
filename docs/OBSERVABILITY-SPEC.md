# Observability specification: Better Stack (closes #136)

Status: specification (no code in this PR). Decision of record: ADR 0009 (Better Stack, errors through the Sentry SDK).
*Confirmed* = read in the code or run in this repository on 2026-10-12; *inferred* = not yet exercised against the live
service. The owner's local notes (`docs/BETTERSTACK-INTEGRATION.md`, gitignored) hold the account details; no token, DSN,
source id or ingest host is copied into a committed file except the host already in `.env.example` (owner decision).

## 1. Errors and traces (Sentry SDK -> Better Stack Errors)

Confirmed today (`rm_core.observability`): off while `SENTRY_DSN` is empty; `environment` = `APP_ENV`, `release` = `RELEASE`;
`send_default_pii=False`; trace sampling `SENTRY_TRACES_SAMPLE_RATE` (0.05); `before_send` removes request cookies, bodies,
query strings, auth headers and user details except the id. The API initialises it; **the worker does not yet.**

| Requirement | Status |
|---|---|
| API and worker both call `init_sentry` at start; the worker tags each event with `job_id`, `queue` and `task` | worker missing (#25) |
| **No stack-frame variables** (`include_local_variables=False`); drop frame `vars`, breadcrumb data and `extra` | done in #149 (L-013 resolved; was confirmed: SDK default is True and the old `scrub_event` left them) |
| Redact emails and `#t=` / `token=` / `credential=` values inside exception messages and breadcrumb messages | done in #149 |
| Convention: never put personal data in an exception message; log ids, not values | in force (legal-tags rule) |
| Events carry the user id only (a pseudonymous UUID, never email) and `request_id` | confirmed |
| Fail closed: any scrubber exception drops the event rather than sending it | done in #149 |

## 2. Logs (structlog JSON -> Better Stack Telemetry)

- The app writes one JSON object per line to stdout (confirmed): `request_id`, `user_id`, `audit_id`, `job_id`,
  `legal_tags`; keys such as email, name, ip, user_agent, authorization, cookie, token, secret, session and id_token are
  redacted by name (confirmed, `rm_core.logging.SENSITIVE_KEYS`). Redaction is by key only: **never put a link, an address
  or a token inside another field's value** (the dev-only `magic_link_dev` line is the one deliberate exception and is
  gated to `APP_ENV=development`).
- **Forwarding is done outside the app**: a log shipper container (Vector or Better Stack's collector) reads container stdout
  and sends it to the Telemetry source. The application does not import `BETTERSTACK_SOURCE_TOKEN` or
  `BETTERSTACK_INGESTING_URL`; only the shipper reads them. Consequences: a Better Stack outage can never block or slow
  a request; if the shipper falls behind it drops lines, not requests; the app code stays free of a vendor client. This
  replaces the "in-process exporter" the `.env.example` comments mention (*decision for review*).
- Source region is US (owner screenshots); the EU-residency and DPA questions are open (B-012, PRE-DEPLOYMENT section 4).
- Retention on the free tier is a few days (ADR 0009 table), which is acceptable because logs hold ids only.

## 3. Uptime

| Probe | Route | Reachable from outside | Checks | Use |
|---|---|---|---|---|
| Public liveness | `/api/health` | yes | process answers; **touches no database** | Better Stack uptime monitor (ADR 0009) |
| Liveness | `/healthz` | no (Caddy blocks) | process answers | container healthcheck |
| Readiness | `/readyz` | no (Caddy blocks) | database and Procrastinate schema, 2 s timeout each | orchestrator, and the readiness heartbeat below |

The owner's B-001 note proposes monitoring `/healthz` and `/readyz`; they are internal by design, so an external monitor
cannot reach them. The external monitor therefore watches `/api/health` (is the host up), and database trouble is caught by a
**readiness heartbeat**: a cron on the host runs `curl -fsS http://localhost:8000/readyz` every 5 minutes and pings a Better
Stack heartbeat only on success, so a database or queue failure makes the heartbeat go silent and alert. Alert channel
on the free tier: email (and Slack if the owner connects it).

## 4. Heartbeats (free tier: 10)

| Heartbeat | Period | Pinged by | Env name |
|---|---|---|---|
| Nightly backup | 24 h + grace | the backup script, success and `/fail` (ADR 0009) | `BETTERSTACK_HEARTBEAT_BACKUP_URL` (exists) |
| Readiness | 5 min + grace | host cron (section 3) | `BETTERSTACK_HEARTBEAT_READY_URL` (new) |
| Ledger check | 24 h | worker task `ledger_mismatches`, success only when zero mismatches | `BETTERSTACK_HEARTBEAT_LEDGER_URL` (new) |
| Retention sweep | 24 h | the `retention` worker task | `BETTERSTACK_HEARTBEAT_RETENTION_URL` (new) |

New names are added to `.env.example` in the PR that implements the pings (#25, #15). An unset URL means no ping and no error.

## 5. Alert catalogue

| Event | Severity | Channel |
|---|---|---|
| Public health probe fails 2 checks in a row | page | uptime monitor |
| Readiness, backup, ledger or retention heartbeat missing | page | heartbeat |
| Ledger/balance mismatch (any row) | page | Sentry error + ledger heartbeat |
| Stripe webhook signature or processing failure, invoice outbox stuck | page | Sentry error |
| Host circuit breaker open on Otodom for more than 30 minutes | warn | Sentry warning |
| Procrastinate queue lag over 10 minutes, failed jobs after retries | warn | Sentry error |
| Connection budget above 70 of 100, disk above 80 % | warn | host check -> heartbeat |
| AI budget at 80 % (exists) | warn | Sentry warning |
| Validation errors, 401/403/404/429 from clients | log only | structlog |

## 6. GDPR and legal

`GDPR[processor]`: Better Stack receives scrubbed events, traces and (via the shipper) log lines containing ids only.
Open: data region, DPA signature, retention of the 90-day error history, and the erasure path (the event user id is a
pseudonymous UUID; on an erasure request events age out within the retention period, deleting them earlier through the
vendor is *inferred* possible and unverified). Add Better Stack to the processor list in the privacy policy (B-012). No
`LEGAL[...]` tag applies.

## 7. Test plan

- Scrubber unit tests (exist since #149): request, user, **frame vars, breadcrumbs, extra, exception and breadcrumb
  messages**, with emails, `#t=` tokens, Google credentials and cookies; a scrubber exception drops the event.
- `init_sentry` is a no-op without a DSN and sets `include_local_variables=False` with one (extends the existing tests).
- Worker start test: Sentry initialised once, job tags bound.
- Heartbeat helper: pings success/fail with a fake transport, no-op when the URL is empty, never raises.
- CI never calls Better Stack; the shipper is exercised only in the Docker smoke by checking it starts.

## 8. Environment names and owner checklist

Names (already in `.env.example`): `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `BETTERSTACK_HEARTBEAT_BACKUP_URL`,
`BETTERSTACK_SOURCE_TOKEN`, `BETTERSTACK_INGESTING_URL`. Planned: the three heartbeat URLs in section 4.

1. Errors: create the application, copy the Sentry-SDK DSN into `SENTRY_DSN` (B-001).
2. Uptime: one monitor on `https://<domain>/api/health` once the domain points at the VPS.
3. Heartbeats: create the four above and note the URLs in the private `.env`.
4. Confirm region and sign the DPA (B-012).
