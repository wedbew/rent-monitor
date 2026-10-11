# RentMonitor — Toolchain, Governance & Agent Setup Proposal

Oct 11, 2026 · @Marcin B

## Verdict

Adopt a Python-only quality toolchain (uv, prek, ruff, pyright, pytest on real Postgres 17), SHA-pinned GitHub Actions, Gemini as the automated PR reviewer and Claude as the on-demand implementer reachable from mobile. Every pick is tied to a blueprint constraint: one server runtime, offline tests on real Postgres, named invariant tests, and money math that must never drift.

| Area | Pick (versions checked 11 Oct 2026) | Blueprint driver |
| --- | --- | --- |
| Workspace | uv workspace, `uv sync --locked` in hooks and CI | Existing uv monorepo; layout 4.1 adds `packages/*`, `services/*` |
| Tests | pytest 9.1, pytest-asyncio 1.4, testcontainers 4.15, hypothesis 6.169, schemathesis 4.30, pytest-alembic 0.13, time-machine 3.5, polyfactory 3.3 | Section 4.6: real Postgres, never SQLite; 29 named tests |
| Lint and format | ruff 0.17 with `S`, `ASYNC`, `DTZ`, `B`, `TID`, `PT` rule sets | Async code, tz-aware datetimes, import boundaries |
| Types | pyright 1.1.414, strict on new code; ty 0.0.86 advisory only | Pydantic v2 and SQLAlchemy `Mapped[...]`; ty is still beta |
| Migrations | pytest-alembic plus squawk | Expand, deploy, contract rule in 4.4 |
| Secrets | gitleaks 8.30 in the hook and in CI over full history | 40+ secrets in `.env.example` |
| Dependencies | pip-audit on `uv export` (gate); `uv audit` (advisory, preview); Dependabot for `uv` | Paid product, supply chain exposure |
| SAST | ruff `S` rules plus Semgrep CE | Auth, webhook and SSE code |
| Containers and IaC | hadolint; Trivy pinned by SHA at v0.36.0 | Compose, three Dockerfiles, Caddy |
| Workflow security | actionlint plus zizmor; every action pinned to a commit SHA | Trivy's own Actions were hijacked in March 2026 |
| Hook runner | prek 0.5.5, reads `.pre-commit-config.yaml`, installs via uv | No Node in the backend toolchain |
| Commits | commitizen 4.19 with a custom `type(RM-n): subject` pattern; root commit exempt | Ticket-tagged history |
| Releases | release-please v5, one product version on `main` | A deployed SaaS, not published libraries |
| Branches | Rulesets on `main` and `staging` | Staging is a local Compose stack, not a VPS |
| AI reviewer | `run-gemini-cli` v0.1.22, PR review on `pull_request` only | Security audit on every PR |
| AI implementer | Claude GitHub App plus `claude-code-action` v1.0.248 | `@claude` from issues, including on mobile |

**Limitations, stated up front.**

- I have not seen the repository. I worked from the README and the blueprint only, so existing `pyproject.toml` settings, tests and CI are unknown to me. Link the repo before Step 2.
- Versions above were read from PyPI and GitHub tags today. SQLAlchemy is now 2.1.4 while the blueprint says 2.0; that is a decision for you in the last section.
- Rulesets on a private repo need GitHub Pro, Team or Enterprise. Commit-message rules in rulesets are documented under Enterprise Cloud; I did not confirm them on Pro, so the convention is enforced by a required CI check instead.

## 1. Testing and QA

pytest on a real Postgres 17 container is the only acceptable base: the schema depends on partial unique indexes, `NULLS NOT DISTINCT`, advisory locks and `LISTEN/NOTIFY`, none of which a fake database reproduces.

| Package | Role here | Why it earns its place |
| --- | --- | --- |
| pytest 9.1 + pytest-cov + pytest-timeout | Runner, coverage, hang guard | Coverage gate per package; a hung SSE or child-process test fails in 60 s instead of stalling CI |
| pytest-asyncio 1.4 | Async fixtures | Set `asyncio_default_fixture_loop_scope = "session"` so the session engine and the Testcontainers DB share one loop |
| testcontainers\[postgres\] 4.15 | Postgres 17 per session | Blueprint 4.6 harness; image pinned to the production major |
| asgi-lifespan + httpx `ASGITransport` | In-process API client | Runs the real lifespan (ProgressHub, pools) without a network port |
| hypothesis 6.169 | Property tests | Ledger law: for any sequence of reserve, capture, release and grant, `SUM(delta) == balance` and `0 <= used <= allowance` |
| schemathesis 4.30 | Contract fuzzing from OpenAPI | Proves every route returns its declared schema and RFC 9457 problem bodies; catches 500s on odd input |
| pytest-alembic 0.13 | Migration tests | Single head, upgrade-downgrade round trip, models match migrations |
| time-machine 3.5 | Clock control | `has_pro` 48 h fail-closed, 7-day grace, 30-minute magic link, 30-day pass stacking |
| polyfactory 3.3 | Factories | Builds `DealAnalysis`, `AuditCreate` and ORM rows from the Pydantic and SQLAlchemy types themselves |

Markers, registered with `--strict-markers` so a typo cannot skip a test:

- `invariant`: the four business invariants plus fractional ownership. CI runs this set as its own required check, so deleting one turns the PR red.
- `integration`: needs Docker. `e2e`: Stripe test mode, never in PR CI.
- `money`: ledger, quota race, webhook and pass tests; coverage gate 95% on `rm_core.ledger`, `rm_core.entitlements` and `rm_api.billing`.

Not chosen: SQLite or pytest-postgresql (no `NOTIFY` parity), respx as the main mock (Otodom goes through `curl_cffi`, so fakes belong at the injectable client boundary the blueprint already defines), Locust for now (the memory and connection gates in Section 6 are Phase 1 exit work, not PR checks).

## 2. Lint, types and security scanning

One fast layer runs on every commit (ruff, gitleaks, commit message); the slower scanners run in CI where they cannot be skipped with `--no-verify`.

| Check | Tool | Where | Hard rule it enforces |
| --- | --- | --- | --- |
| Lint + format | ruff (`E,F,W,I,B,UP,S,ASYNC,DTZ,PT,TID,RUF,PL`) | hook + CI | `DTZ`: no naive datetimes; `ASYNC`: no blocking calls in async routes; `TID251` bans `float` helpers and `requests` in `services/` |
| Types | pyright strict on `packages/` and `services/`, basic on `apps/` | CI | Contract drift between `rm-contracts`, API and worker fails the build |
| Types (trial) | ty, non-blocking job | CI | Revisit as the gate once ty reaches 1.0 |
| Secrets | gitleaks binary (not the Action) | hook + CI on full history | Stops `.env`, `sk_live_`, `whsec_`, `sk-or-v1-` leaks |
| Dependency CVEs | `uv export` then `pip-audit` | CI + nightly | Blocking on known CVEs |
| Dependency CVEs | `uv audit` | nightly, advisory | Preview command; promote when stable |
| Dependency updates | Dependabot `uv` + `github-actions` + `docker`, grouped weekly | GitHub | Updates arrive as reviewable PRs, never silently |
| SAST | Semgrep CE (`p/python`, `p/jwt`, `p/secrets`, plus local rules) | CI | Local rules: no `float(` on money fields, no `json.loads` before Stripe signature check, no `pull_request_target` |
| Dockerfiles | hadolint | hook + CI | Pinned base images, non-root user |
| Images + config | Trivy (image + `config` scan), action pinned to SHA | CI on `staging`/`main` | HIGH/CRITICAL fixable vulns block release |
| Workflows | actionlint + zizmor | hook + CI | Unpinned actions, template injection, excessive permissions |
| SQL migrations | squawk | CI on `migrations/` | Flags lock-taking DDL that would break expand-contract |

Three calls worth defending:

1. **pyright over mypy.** Faster, strong with Pydantic v2 and `Mapped[]`, and the same engine powers the `pyright-lsp` plugin agents use, so humans, CI and agents see identical errors.
2. **Gitleaks binary, not `gitleaks-action`.** The binary needs no licence key and pins cleanly by version.
3. **Trivy kept, with conditions.** Between 19 and 22 March 2026 attackers force-pushed 75 `trivy-action` tags and published Trivy v0.69.4 with a credential stealer. It remains the best single image-plus-config scanner, but only pinned to a commit SHA, run with read-only permissions and no secrets in the job. CodeQL is free only for public repos (or with GitHub Advanced Security), so it is optional.

## 3. Commit and git governance

Every change starts as a GitHub Issue, lands on `staging` as one squash commit titled `type(RM-<issue>): subject`, and reaches `main` only through a promotion PR. `RM-12` maps to issue `#12`; the `#` form is avoided because git strips lines starting with `#` in the editor and it reads poorly in changelogs.

Commit format (regex used by commitizen, the PR-title check and the agents):

```text
^(feat|fix|perf|refactor|test|docs|build|ci|chore|revert)(\(RM-[0-9]+\))!?: .{1,72}$
examples:  feat(RM-12): add credit ledger reserve/settle
           fix(RM-31)!: reject unverified Google emails
```

**Bootstrap exception.** The repository's root commit (a commit with no parent) is exempt and only it. The commit-msg hook detects "no HEAD yet"; CI skips commits where `git rev-list --parents` shows no parent. This cannot be abused later, unlike an allow-listed message such as `chore: bootstrap`.

**Bot exception.** Two bot-authored forms need no ticket and nothing else does: Dependabot's `build(deps): ...` / `ci(deps): ...` and release-please's `chore(release): x.y.z`. Their PRs are also exempt from the `Closes #n` rule.

Flow:

1. Open an issue from the template (Feature, Bug, Chore). It is added to the Project board with Status, Phase (`P1-backend`, `P2-frontend`) and Blueprint section fields.
2. Branch `rm-12-credit-ledger` from `staging`.
3. Open a PR to `staging`; the title must match the regex and the body must contain `Closes #12`.
4. Required checks pass and Gemini reviews; squash-merge, so the PR title becomes the commit.
5. Promote with a PR `staging` to `main` (merge commit, never squash, so ticket history survives). release-please then opens a release PR on `main`.

Rulesets:

| Rule | `main` | `staging` |
| --- | --- | --- |
| Require PR | yes, from `staging` or `hotfix/*` only | yes |
| Approvals | 1 (you), stale approvals dismissed | 0 while solo; 1 once a second engineer joins |
| Required checks | `lint`, `types`, `test`, `invariants`, `security`, `pr-title` | same |
| Merge method | merge commit | squash only |
| Linear history | no (promotion merges) | yes |
| Force push / deletion | blocked | blocked |
| Bypass | none, admins included | repository admin, for emergencies only |

Tools: **prek** runs the hooks (drop-in for pre-commit, Rust, installs Python hooks through uv, used by CPython, FastAPI and Airflow). **commitizen** validates messages and gives `cz commit` for guided entry. commitlint and Husky are rejected: they add Node to a toolchain the blueprint keeps Python-only outside the SPA build. Changesets is for JS packages.

## 4. CI/CD on GitHub Actions

Seven workflows, each with `permissions: {}` at the top and only what a job needs granted per job; every `uses:` is pinned to a 40-character SHA with the tag in a comment, and Dependabot keeps those pins current.

| Workflow | Trigger | Jobs (required check name) | Notes |
| --- | --- | --- | --- |
| `ci.yml` | PR to `staging`/`main`, push | `lint`, `types`, `test`, `invariants`, `migrations` | `setup-uv` v10.3.0 with cache; `uv sync --locked`; Postgres via Testcontainers on the runner's Docker |
| `security.yml` | PR, push, nightly 03:17 UTC | `security` (gitleaks, pip-audit, Semgrep, zizmor, actionlint, hadolint) | Nightly run catches CVEs published after merge |
| `pr-title.yml` | PR opened/edited | `pr-title` | Regex from Section 3; also rejects PRs with no `Closes #n` |
| `images.yml` | push to `staging`/`main` | build `rentmonitor-py` + Caddy image, Trivy scan, push to GHCR tagged `sha` | Deploy stays manual: `IMAGE_TAG=<sha> docker compose up -d` per blueprint 4.4 |
| `release.yml` | push to `main` | release-please v5 | Needs a GitHub App token so its PR triggers CI (PRs opened with `GITHUB_TOKEN` do not) |
| `gemini-*.yml` | PR, issues, `@gemini-cli` | review, triage, dispatch | Section 5 |
| `claude.yml` | `@claude` comments | implement, answer | Section 5 |

Why release-please over python-semantic-release: ticket IDs occupy the commit scope, and PSR's monorepo parser uses scope prefixes to route commits to packages, so the two conventions collide. A SaaS ships one product version anyway; release-please reads `feat`/`fix`, writes `CHANGELOG.md`, and works through a PR, which respects branch protection. Container tags stay the commit SHA; the semver tag is for humans and Sentry releases.

CI runtime target: under 6 minutes for a PR. Testcontainers starts Postgres once per session; the `invariants` job re-runs only `-m invariant` so its pass or fail is visible on its own.

## 5. AI code review and remote operations

Gemini reviews, Claude implements, and neither can merge. Splitting the roles across two model families means the reviewer is not grading its own work.

| Role | Tool | Trigger | Auth | Permissions |
| --- | --- | --- | --- | --- |
| Automated PR reviewer | `google-github-actions/run-gemini-cli` v0.1.22 (PR Review workflow) | PR opened or synchronized; `@gemini-cli /review` | Workload Identity Federation to Vertex AI (no stored key); `GEMINI_API_KEY` as fallback | `contents: read`, `pull-requests: write`, `id-token: write` |
| Issue triage | same, Issue Triage workflow | issue opened | same | `issues: write` |
| Implementer and Q&A | Claude GitHub App + `anthropics/claude-code-action` v1.0.248 | `@claude` in issue or PR comment, by users with write access | `CLAUDE_CODE_OAUTH_TOKEN` from your subscription, or an API key | `contents: write`, `pull-requests: write`, `issues: write`, `id-token: write`, `actions: read` |
| Mobile and web | Claude Code on the web and the Claude mobile app, through the same GitHub App | you, from your phone | your Claude account | sessions push to branches, never to `main` |

Gemini review prompt, kept in `.github/commands/gemini-review.toml` (in the repo, versioned) and pointed at `.agent/agents.md`: flag any float in money paths, financial math outside `apps/deal-analyzer`, missing `Principal` scoping on tenant queries, webhook handling before signature verification, broadened workflow permissions, and any deleted or skipped `invariant` test. Severity labels map to `blocking`, `should-fix`, `nit`.

Guardrails, because both bots read untrusted text from PRs and issues:

- Never `pull_request_target` and never check out PR head code in a job that holds secrets; that exact pattern let a bot steal Trivy's token in February 2026. zizmor fails the build if it appears.
- `claude-code-action` already refuses bot actors and users without write access; keep `allowed_non_write_users` empty.
- Cap cost and blast radius: `--max-turns 30`, a 30-minute job timeout, and one concurrent run per issue.
- The Gemini review is advisory, not a required check, at first. Promote it to required only after two weeks of measured false positives.

Mobile loop you asked for: create or comment on an issue in GitHub Mobile with `@claude implement this per .agent/agents.md`; Claude opens a branch and PR; Gemini reviews; you merge from the phone. For longer work, start a Claude Code session from the mobile app against the repo. Run `/install-github-app` once from a local Claude Code session to install the app and the secret.

## 6. Agent plugins, MCP servers and skills

Install few, scope each tightly, and keep every production credential out of agent reach: agents get GitHub, docs, a local database and a Stripe sandbox, nothing else.

**MCP servers** (checked into `.mcp.json`, secrets from env):

| Server | Scope granted | Why for this project |
| --- | --- | --- |
| GitHub (official) | this repo; issues, PRs, Actions read | Issue-driven flow: agents read the ticket, link PRs, read failed CI logs |
| Context7 | read-only docs | Blueprint pins fast-moving APIs: Procrastinate 3.x, Stripe SDK on `2026-09-30.endive`, SQLAlchemy async, sse-starlette. Stale training data is the biggest agent error source here |
| Postgres MCP Pro (Crystal DBA) | **restricted mode**, local dev DB only | `explain_query`, hypothetical indexes and health checks while writing the partial indexes and `market_sidecar` queries. Never pointed at the VPS |
| Stripe (`mcp.stripe.com`) | sandbox only, an Agent-tagged restricted key | Docs search and inspecting test objects while building the webhook state machine. From 31 Oct 2026 the server rejects keys without the Agent tag |
| Sentry | later, at ops step 7 | Read production errors when triaging `UPSTREAM_SCHEMA_DRIFT` |

Deferred to Phase 2: Playwright, Chrome DevTools and Figma servers.

**Claude Code plugins** (all from `claude-plugins-official`, verified in its marketplace today):

| Plugin | Use |
| --- | --- |
| `pyright-lsp` | Same type errors in the agent loop as in CI |
| `security-guidance` | Pattern warnings on edits plus a diff review at stop; fits auth and billing work |
| `pr-review-toolkit` | Specialist reviewers for tests, error handling and type design before a PR opens |
| `commit-commands` | Commit and PR creation; agents.md overrides the message format |
| `claude-md-management` | Keeps `CLAUDE.md` and agents.md short and current |
| `github`, `context7`, `stripe` | Plugin-packaged versions of the MCP servers above |
| `semgrep` | Optional: same rules as CI, earlier |

Not recommended: `superpowers` and similar broad workflow packs (they overlap the rules in agents.md and add context on every run), and any plugin whose MCP server needs production credentials.

**Project skills** to write in `.claude/skills/` (each a short `SKILL.md` that also works as a Gemini custom command):

1. `new-migration`: Alembic revision in schema `app`, naming convention, expand-contract checklist, squawk run, pytest-alembic run.
2. `add-endpoint`: router, `rm-contracts` schema, problem codes, `Principal` scoping, OpenAPI regen, schemathesis case.
3. `invariant-guard`: lists the invariant tests, refuses to weaken them, explains how to add one.
4. `stripe-webhook-change`: test-clock recipe, signed payload helper, idempotency and ordering tests to add.
5. `ticket-flow`: from issue to branch, commit format, PR body with `Closes #n`.

## 7. Rules, context and agent files

One canonical rules file, `.agent/agents.md`, and thin pointers for each tool, so Claude, Gemini and any other agent read the same rules and nothing drifts. A draft of every file below is ready as a pre-setup pack (not applied to the repo).

| File | Contents | Read by |
| --- | --- | --- |
| `.agent/agents.md` | Invariants, architecture boundaries, coding standards, security boundaries, testing rules, git flow, implementation order, tools, "confirmed vs inferred" rule (about 120 lines) | All agents, via the pointers |
| `CLAUDE.md` | `@.agent/agents.md` import plus 3 Claude-only notes (use Context7 for pinned APIs, run tests before "done", PRs to `staging`) | Claude Code, `claude-code-action` |
| `AGENTS.md` (root) | One-line pointer (or symlink) to `.agent/agents.md` | Codex, Cursor and others that auto-discover it |
| `.gemini/settings.json` | `context.fileName` set to `.agent/agents.md` | Gemini CLI and the review Action |
| `.mcp.json` | GitHub, Context7, Postgres (restricted), Stripe sandbox; secrets by env var | Claude Code |
| `.claude/skills/*` | The five project skills from Section 6 | Claude Code, Action |
| `docs/blueprint.md` | The blueprint, committed as the spec of record | Everyone |
| `docs/adr/NNNN-*.md` | One ADR per expensive-to-reverse call (Python-only server, Procrastinate over arq, no Redis, Google-first auth, BLIK pass) | Humans and agents |
| `apps/LIMITATIONS.md` | Existing L-01 to L-30 register, extended with blueprint risks | Everyone |

One conflict to fix before agents start: `apps/agent-context/AGENTS.md` is the data corpus index, but AGENTS.md-aware tools load any file with that name as **instructions** when working in that folder. Rename it to `apps/agent-context/INDEX.md` and update the references.

The pack also includes: `.pre-commit-config.yaml` (prek-ready), `scripts/check_commit_msg.py` with 18 passing tests, `pyproject.tooling.toml` (ruff, pyright, pytest markers, coverage, commitizen), workflows `ci`, `security`, `pr-title`, `claude`, `release`, `dependabot.yml`, ruleset JSON for `main` and `staging`, an issue template, and three Semgrep rules (float on money, Stripe body parsed before signature, `pull_request_target`).

Verification done on the pack: YAML, JSON and TOML parse; actionlint clean; zizmor reports 0 findings; both Semgrep rules fire on sample violations; prek validates the hook config, allows the root commit, rejects `chore: no ticket` and accepts `chore(RM-1): ...`. The Gemini workflows are not drafted: install them with Gemini CLI's own setup so they match upstream, then pin to the v0.1.22 commit.

## 8. Phase 1 backend plan and decisions needed

Phase 1 is blueprint steps 1 to 5 plus the batch tasks of step 8, preceded by a pre-setup step; it is done when every named test in blueprint 4.6 passes in CI except the Stripe e2e marker. Each step is one milestone on the Project board, and no step starts with the previous one red.

1. **Step 0, pre-setup (RM-1 to RM-6):** apply the pack, rulesets, Claude and Gemini apps, rename `apps/agent-context/AGENTS.md`, commit the blueprint and ADRs. Exit: CI green on an empty `packages/` skeleton.
2. **Engine seams:** `ContextRepository` and `ProgressSink` in `deal-analyzer`, filesystem implementations, existing tests green, plus the 4 invariant tests.
3. **Data plane:** `rm-core` models, Alembic baseline in schema `app`, Procrastinate schema, importers for `agent-context` and `reports/final`. Exit: pytest-alembic and the asking-is-not-deed constraint test.
4. **Auth:** Google ID-token sign-in, magic link, sessions, Origin check, signup grant, rate limit. Exit: the 6 auth and tenant tests.
5. **Audits:** submit route, worker, child-process engine, SSE hub, reconciler. Exit: quota race, release, SSE resume, burst and timeout tests.
6. **Billing:** Checkout, BLIK pass, Portal, webhook state machine, entitlements, VAT outbox with a stubbed Fakturownia. Exit: all webhook, pass and concurrency tests.
7. **Market batch tasks:** city refresh and ranking on `worker-batch`, screener behind its flag.

Not in Phase 1: release gates 1, 3, 4 and 6 need the VPS, a live Stripe account or a Fakturownia trial; they are launch work, tracked as issues now.

**Decisions I need from you**, with my recommendation:

| # | Decision | Recommendation |
| --- | --- | --- |
| 1 | Repository access for Step 2 | Link this session to your computer, or give me the GitHub repo and a fine-grained token; I cannot apply anything without it |
| 2 | Restructure the existing repo or start `rentmonitor/` fresh | In place: keep `apps/` untouched, add `packages/`, `services/`, `deploy/`, `migrations/` beside it |
| 3 | SQLAlchemy 2.1.4 (current) or 2.0 (blueprint text) | 2.1: new code, nothing to migrate; pin the minor |
| 4 | Stripe SDK major | Pin the SDK major whose default API version is `2026-09-30.endive`; I have not confirmed which major that is (PyPI shows 16.0.0) |
| 5 | GitHub plan | Pro or higher if the repo stays private, otherwise rulesets are unavailable |
| 6 | Gemini auth | Workload Identity Federation to Vertex AI; an API key only if you have no GCP project |
| 7 | Claude auth in Actions | `CLAUDE_CODE_OAUTH_TOKEN` from your subscription while you are solo; switch to an API key if a team shares it |
| 8 | Ticket key | `RM`, mapped to GitHub issue numbers |

Once you confirm (or override) these, I start Step 2 with Step 0's tickets.

## Sources

Pages opened on 11 Oct 2026. Package versions came from the PyPI JSON API; action versions and commit SHAs from `git ls-remote` on each repository.

- [Claude Code GitHub Actions docs](https://code.claude.com/docs/en/github-actions): setup, `@claude` trigger rules, auth secrets, GitHub App permissions
- [run-gemini-cli](https://github.com/google-github-actions/run-gemini-cli): PR review, triage, dispatch workflows; WIF and API-key auth
- [SafeDep: Trivy supply chain compromise](https://safedep.io/trivy-teampcp-supply-chain-compromise/): Feb–Mar 2026 timeline, affected tags, safe versions
- [pydevtools: ty](https://pydevtools.com/handbook/topics/ty/): ty beta status
- [pydevtools: scanning Python dependencies](https://pydevtools.com/handbook/how-to/how-to-scan-python-dependencies-for-vulnerabilities/): `uv audit` preview, pip-audit with `uv export`
- [prek README](https://cdn.jsdelivr.net/gh/j178/prek@master/README.md): pre-commit compatibility, uv integration, adopters
- [python-semantic-release monorepo guide](https://python-semantic-release.readthedocs.io/en/latest/configuration/configuration-guides/monorepos.html): scope-prefix parser
- [Postgres MCP Pro](https://github.com/crystaldba/postgres-mcp): restricted mode, explain and index tools
- [Stripe MCP](https://edge-docs.stripe.com/mcp): Agent-tagged keys required from 31 Oct 2026
- [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets): plan availability
- [claude-plugins-official marketplace](https://github.com/anthropics/claude-plugins-official): plugin names verified from its `marketplace.json`
- Your files: the RentMonitor README and the Architecture and Implementation Blueprint (11 Oct 2026)
