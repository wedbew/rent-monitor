# Pre-deployment checklist

Nothing here is ticked until there is **evidence** (PR, test name, run URL, dated note). Agents tick items in the PR that
delivers the evidence; humans own the items marked **(owner)**. A paid launch needs every section green. Release gates are
blueprint §6; risks are blueprint §5; limits are `docs/LIMITATIONS.md`.

## 0. Repository visibility and publishing (owner)
- [ ] The repo is **public only during development**. Before real keys, customer data or a live domain exist, switch it to
      **private** (`gh repo edit <repo> --visibility private --accept-visibility-change-consequences`) or confirm that staying public is intended.
- [ ] If it stays public: gitleaks on full history is clean; the maintainer's commit email is acceptable; `docs/BLUEPRINT.md` cost, risk and legal sections are reviewed for what you are willing to publish.
- [ ] Rulesets (`.github/rulesets/`) are still enforced after any visibility change (private repos need GitHub Pro or higher; otherwise protection silently disappears).
- [ ] Any secret ever pasted into an issue, PR, log or chat has been rotated.

## 1. Code and tests (CI on `main` green)
- [x] `migrations` job enabled and required (RM-68, 2026-10-11).
- [x] `invariants` job enabled and required (RM-89, 2026-10-12).
- [ ] ~~**`invariants` job enabled**~~ (done above) (repo variables `ENABLE_INVARIANTS_JOB`, `ENABLE_MIGRATIONS_JOB` = `true`) and **required again** on `staging` (`.github/rulesets/staging.json` and the live ruleset).
- [ ] All blueprint §4.6 named tests exist and pass, none skipped (`uv run pytest -m invariant`); `e2e` Stripe tests pass in test mode.
- [ ] Coverage floor met; pyright strict clean for `packages/` and `services/`; ruff, semgrep, gitleaks, zizmor, actionlint clean.
- [ ] `tests/migrations` (pytest-alembic) and `squawk` pass; migrations are expand→contract; rollback/restore path documented.
- [ ] Contract test against one live listing passes (schema-drift detector); the `UPSTREAM_SCHEMA_DRIFT` alert is verified.
- [ ] The SPA computes no finance: the tested ESLint money guard (`frontend/eslint.money.mjs`) passes in the `frontend` job. (Replaces the old check that two `frontend/src/lib/*` files do not exist, which could not fail in the flat layout.)
- [ ] No reachable placeholder screen: every row of `docs/STATUS.md` *Frontend: screens a user can reach that are not built* is built or its entry point removed (in particular `/terms` and `/privacy`, which sign-up says the person accepts).
- [ ] `frontend`, `frontend-e2e` and `frontend-journey` are required checks on `main` and `staging` (B-019).

## 2. Release gates (blueprint §6): evidence required
- [ ] 1 KSeF end to end on a Fakturownia trial (subscription, test-clock renewal, BLIK pass, card pass, no-NIP buyer, timeout, rejection, downtime).
- [ ] 2 Billing concurrency (adverse event order → canceled; parallel passes → 60 days).
- [ ] 3 BLIK recurring: one live 100 zł subscription on an eligible bank creates a mandate and is refunded; an unsupported bank lands on the pass offer.
- [ ] 4 Memory: 20 representative audits with batch running; `memory.peak` recorded; concurrency 2 only if peak < 60 % of the limit.
- [ ] 5 Connections: peak-load test, `pg_stat_activity` stays under 70.
- [ ] 6 Restore: WAL-G point-in-time restore on a fresh VPS, timed, under 1 hour.
- [x] 7 Auth: unverified Google token rejected; same-email collision handled; sign-out-everywhere evicts sessions within 1 s. Evidence (offline, fake Google; CI): `tests/integration/test_auth.py::test_google_unverified_email_is_rejected_and_creates_nothing`, `::test_an_unverified_google_email_never_links_to_an_existing_user`, `::test_sign_out_everywhere_evicts_cached_sessions_in_all_processes` (asserts under 1 s), 2026-10-14, #38. Real Google sign-in is still unexercised (B-004).

## 3. Security
- [ ] Production secrets only in the host `.env` / password manager; none in git, CI logs or images. Stripe live keys separate from test keys.
- [ ] Cookie flags, Origin check, CSP (Caddy) and HSTS verified on the deployed domain; `/healthz` and `/readyz` unreachable from outside.
- [ ] Stripe webhook signature verified on the raw body; endpoint API version pinned and equal to `STRIPE_API_VERSION`.
- [ ] Rate limits live (magic link per address and IP); SSRF-safe handling of user-supplied listing refs verified.
- [ ] Least-privilege DB roles; Postgres not publicly exposed; UFW allows only 22/80/443; SSH password login disabled.
- [ ] Dependency audit clean (Dependabot, lockfile reviewed); GitHub Actions pinned by SHA; no `pull_request_target`.
- [ ] Tenant isolation: user B gets 404 on every user-A resource (`test_tenant_isolation` plus a manual pass).

## 4. Legal, GDPR and tax (owner)
- [ ] **Polish legal review of Otodom scraping and image analysis done** (L-001); decision recorded; kill-switch flags for `LEGAL[...]` features tested off and on.
- [ ] `grep` inventory of `LEGAL[` / `GDPR[` tags reviewed with counsel; nothing uncertain is missing from `docs/LIMITATIONS.md`.
- [ ] Privacy policy, terms, cookie/analytics notice (Umami), processor list (Google, Stripe, Resend, Fakturownia, OpenRouter, Better Stack, OVH, Cloudflare), DPAs signed; Better Stack data region checked (ADR 0009).
- [ ] Retention jobs live and tested (sessions, login tokens, snapshots, `audit_event`, backups 14 d / 56 d); account deletion and data export work; backup-restore re-deletion procedure written.
- [ ] VAT price presentation (net/gross) decided; accountant confirmed B2C/B2B treatment and KSeF timing (penalties from 2027-01-01).
- [ ] Google OAuth consent screen moved from Testing to **In production**.

## 5. Billing and product
- [ ] Stripe: BLIK and BLIK recurring capabilities **active**; Smart Retries on, cancel after all retries fail; Stripe's own receipts/invoices disabled.
- [ ] Live-mode prices created (monthly, 30-day pass); `PRO_MONTHLY_AUDIT_ALLOWANCE` set from measured COGS (L-003), not the placeholder 40.
- [ ] CAPEX catalog uses sourced prices, not placeholders (L-007, B-015); `prices_are_placeholders` is false in every result.
- [ ] OpenRouter monthly budget cap and kill-switch tested; tokens and USD logged per audit.
- [ ] Free-tier scope decided and implemented (3 audits, radar top 20).
- [ ] Datacenter-IP test from the production VPS: Otodom reachable, or proxy plan active (L-002). Evidence so far: one request from the VPS-1 returned 200 on 2026-10-13; repeat from the final VPS and under audit load before ticking.

## 6. Infrastructure and operations
- [ ] VPS ordered in **Poland**, Ubuntu 24.04 LTS, hardened per blueprint §4.4, 2 GB swap, `vm.swappiness=10`.
- [ ] Compose limits match the resource matrix; `memswap_limit` and `oom_score_adj` set; healthchecks green; restart policies verified by killing containers.
- [ ] Images built in CI, tagged by SHA, scanned; deploy is `IMAGE_TAG=<sha> docker compose up -d` after a one-off migration.
- [ ] Backups: nightly `pg_dump` and WAL-G to R2 running and encrypted, R2 lifecycle (14 d / 56 d) set, `age` private key offline, restore drill done and timed.
- [ ] Monitoring (Better Stack, ADR 0009): errors via the Sentry SDK, uptime monitor on `/api/health`, backup heartbeat; queue, disk, connection, OOM and ledger-vs-balance alerts each verified by triggering once.
- [ ] DNS and TLS on Cloudflare/Caddy; domain plus SPF/DKIM/DMARC for the Resend sending domain verified.
- [ ] Runbook: deploy, rollback, restore, rotate secrets, disable a legal-tagged feature, handle a Stripe dispute (12-day evidence window).
- [ ] Every `active` item in `docs/LIMITATIONS.md` is mitigated, accepted by the owner, or blocking.

## 7. Launch day
- [ ] `main` promoted from `staging` by PR with one human approval; tagged release; `CHANGELOG.md` section dated.
- [ ] Production smoke test: Google sign-up, magic link, one audit end to end, one live purchase refunded, webhook replay, SSE reconnect.
- [ ] Rollback plan agreed (previous `IMAGE_TAG`, OVH snapshot before migration).
- [ ] `CONTEXT.md`, `README.md` Status and this checklist updated to the launched state.
