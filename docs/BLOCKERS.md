# Blockers: things only the owner can unblock

Agents add a row the moment they hit one and stop that work (`.agent/rules/blockers.md`). Rows are never deleted.
Strategy (owner decision, 2026-10-11): **work locally until the whole app works, in Docker; deploy later.** Items that only
matter for production or a domain are *Deferred*, not blocking.

## Open (needs the owner)

| ID | What | Owner action | Waits on it |
|---|---|---|---|
| B-007 | **Engine specification** | See "What B-007 is" below. Approve or edit the draft `docs/ENGINE-SPEC.md` (agent writes it next) | #17 and the whole valuation engine, so audits cannot produce a real result |
| B-009 | semgrep `no-float-money` flags every `x: float = ...` annotation (#55) | Approve a rule fix | any float setting or probability |
| B-012 | Legal review and retention periods (#41) | Counsel confirms Otodom scraping/image use and the proposed retention defaults (sessions 7 d, login tokens 1 d, snapshots 30 d, audit events 30 d) | paid launch only; not needed to build |
| B-004 | Google OAuth client id, Resend key | Create a Google OAuth Web client and a Resend key; put `GOOGLE_CLIENT_ID`, `RESEND_API_KEY` in `.env`. Needed only for live sign-in tests: until then auth is built and tested with fakes, and the magic link is logged in dev | live testing of #12 |

### What B-007 is
The valuation engine (`apps/deal-analyzer`) turns one Otodom listing into the 10-year cash-flow result the product sells: yield,
IRR, tax, CAPEX, **Max Bid** (the highest price at which the deal still meets your return target) and a grade. Every number
must be computed by our Python code with fixed rules, so the *rules themselves* have to be decided by a person: which
purchase costs and taxes apply, how rent and costs are estimated, whether the buyer uses a mortgage, what "Max Bid" targets,
and where the grade cut-offs sit. The old proof of concept contains one set of answers, but the project rule (ADR 0001) is to
write the product from scratch and not copy formulas out of the POC, because some of them were wrong or untested.

You do not have to write formulas. The agent writes `docs/ENGINE-SPEC.md` with a recommended default for each of the 13
questions (listed in `docs/ROADMAP.md` §8, D-01), marks the tax items "accountant to confirm", and you approve or change it.
Until then the engine stays blocked (#17) while everything else proceeds.

## Deferred (not blocking local work)

| ID | What | Why deferred | Revisit when |
|---|---|---|---|
| B-001 | Sentry project and DSN (org `mb-web-dev`) | Code is ready and Sentry stays off while `SENTRY_DSN` is empty; owner connects it later. Agents keep issues tracked here | before launch; steps: create project `rentmonitor-api`, set `SENTRY_DSN`, cron + uptime monitors |
| B-002 | Umami analytics | Frontend only, and no domain yet | Phase 2 frontend |
| B-003 | Stripe sandbox keys, webhook, BLIK activation (#39) | Implemented after the API endpoints work, together with Google auth | billing step (#14); request BLIK activation early, it has lead time |
| B-005 | Domain and DNS | Not needed locally | deployment preparation |
| B-006 | VPS purchase and Otodom datacenter-IP test (#42) | Buy after the app works locally | deployment preparation |

## Resolved

| ID | What | Resolution | Date |
|---|---|---|---|
| B-005a | R2 bucket and keys | Owner states the R2 values are in `.env` (not verified by agents, which cannot read it) | 2026-10-11 |
| B-008 | `migrations` CI job and required check | Enabled: `ENABLE_MIGRATIONS_JOB=true`, `migrations` required on `staging`, squawk clean (RM-68). `invariants` stays off: it needs the engine's three missing named tests, see #17 | 2026-10-11 |
| B-010 | Agents could not read `.env.example` | Deny rule narrowed to real env files; agents read and edit `.env.example` (`rules/env-example.md`) | 2026-10-11 |
| B-011 | `.claude/settings.json` safety entries | Added deny `gh pr merge*--admin*`, ask on `gh repo edit*visibility*` and `gh repo delete*`. Agents merge into `staging` themselves; the human approval is on `staging` → `main` only, at launch, enforced by the ruleset | 2026-10-11 |
| B-013 | Testcontainers reaper could not mount the Docker socket (macOS) | `tests/conftest.py` sets `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`; suite passes with the reaper on | 2026-10-11 |
