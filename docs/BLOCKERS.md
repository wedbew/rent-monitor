# Blockers: things only the owner can unblock

Agents add a row the moment they hit one and stop that work (`.agent/rules/blockers.md`). The owner resolves it, then the row
moves to *Resolved* with a date. Rows are never deleted.

## Open

| ID | Blocked | Owner action | Waits on it | Since |
|---|---|---|---|---|
| B-001 | Sentry in production (no DSN). Org slug: `mb-web-dev` | In Sentry org `mb-web-dev`: (1) create project **rentmonitor-api**, platform Python/FastAPI; (2) copy its DSN into the host/dev `.env` as `SENTRY_DSN` and set `SENTRY_TRACES_SAMPLE_RATE=0.05`; (3) add a **Cron monitor** `nightly-backup` and put its check-in URL in `SENTRY_CRON_CHECKIN_URL`; (4) add an **Uptime monitor** on `https://<domain>/api/health` (needs the domain, B-005); (5) verify with `SENTRY_DSN=... uv run python -c "import sentry_sdk;from rm_core.observability import init_sentry;from rm_core.settings import get_settings;init_sentry(get_settings());sentry_sdk.capture_message('rentmonitor test');sentry_sdk.flush()"` and look for the event. The "run code" the owner mentioned is unidentified: say what it is for. | #18 live check, #15 monitors, gate list | 2026-10-11 |
| B-002 | Umami analytics (no website id/script) | Create Umami Cloud site; give the website id (#40, #41 cookie notice) | SPA, privacy notice | 2026-10-11 |
| B-003 | Stripe: test keys for agents, webhook secret, BLIK recurring activation | Create sandbox keys (Agent-tagged by 2026-10-31), request BLIK recurring (#39, #40) | #14, #26, #27, gates 2-3 | 2026-10-11 |
| B-004 | Google OAuth client id, Resend key and sending domain | Create in Google Cloud / Resend; set `GOOGLE_CLIENT_ID`, `RESEND_API_KEY`, DNS (#40) | #12, #25 | 2026-10-11 |
| B-005 | Cloudflare R2 bucket and keys, domain and DNS | Create bucket, lifecycle 14 d / 56 d, keys; domain (#40) | #15, gate 6 | 2026-10-11 |
| B-006 | VPS and datacenter-IP test | Order OVH VPS-3 Poland; run the Otodom reachability test (#42, L-002) | #15, gates 4-6 | 2026-10-11 |
| B-007 | Engine specification | Answer the engine questions in #43 | #17 and the whole engine lane | 2026-10-11 |
| B-008 | Owner-gated merges: `migrations` CI job and required check | Follow #53 (repo variable + ruleset) | `migrations` enforcement | 2026-10-11 |
| B-009 | semgrep `no-float-money` rule blocks every float annotation | Approve a rule fix (#55) | any float setting | 2026-10-11 |
| B-010 | Agents cannot read `.env.example` (deny rule), so new env names are not added to it | Add the names listed in `CHANGELOG.md` entries to `.env.example`, or allow reading that file | ops docs | 2026-10-11 |
| B-011 | `.claude/settings.json`: deny `gh pr merge*--admin*`, ask on visibility/delete/merge-main | Add the entries (see PR history) | safe autonomy | 2026-10-11 |
| B-012 | Legal review and retention periods | Counsel confirms Otodom scraping/images and the proposed retention defaults (#41) | paid launch, #30 values | 2026-10-11 |
| B-013 | Local Docker: Testcontainers reaper cannot mount the socket; `postgres:17` pull was slow | Run tests with `TESTCONTAINERS_RYUK_DISABLED=true`, or fix Docker Desktop sharing | local test runs | 2026-10-11 |

## Resolved

_None yet._
