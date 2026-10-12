# Rule: the POC is reference material; this product is written from scratch to production quality

Decision of record: `docs/adr/0001-greenfield-rewrite.md` (maintainer decision, 2026-10-11). It overrides every older
sentence that says "wrap, don't rewrite", "copy the apps", "port", "migrate the POC" or "keep the POC's tests green"
(blueprint §4.0/§4.1/§4.8 step 1, TOOLCHAIN §8, earlier drafts of `CONTEXT.md`). Where this rule and those texts disagree, this rule wins.

## What the POC is

`~/Projects/otodom-rent-report` (pinned reading commit in `CONTEXT.md` header) is a proof of concept. It exists so you can
learn **what the product must do and where it breaks**. It is read-only input. It is not a code source.

## Hard rules

1. **Never copy, move, vendor, `git archive`, symlink, submodule or import POC files** — source, tests, fixtures, config,
   corpus data, docs. Not "just this module", not "temporarily". Do not add the POC as a dependency or workspace member.
2. **Read it to extract requirements**, then write the behaviour yourself from the blueprint and the requirement. A POC
   fixture may be *recreated* as a small, hand-built, anonymised fixture in `tests/fixtures/` — never copied wholesale,
   never containing real seller names, phones or full listing payloads.
3. **Every POC defect you notice is fixed in the new design, not reproduced.** Record it in `CONTEXT.md` §5 (lessons) and,
   if it is a standing constraint, `docs/LIMITATIONS.md`. Do not write "same as POC" as a justification.
4. **Behavioural parity is judged by requirements and the blueprint's named tests (§4.6), not by diffing against the POC.**
   Where the POC and the blueprint disagree, the blueprint wins; where both are silent, ask.
5. Paths named in the blueprint (`apps/deal_analyzer`, `apps/price-intel`, …) stay as the **locations** of the new,
   from-scratch packages; their contents are new code with their own `pyproject.toml`, tests and types.
6. Never read the POC's `.env`, never copy its `AGENTS.md` / `.cursor` rules, never depend on its absolute path in code, tests or CI.

## Production-ready bar (applies to all new code, not only the engine)

Assume real, hostile, concurrent traffic from day one. A feature is not done until:

- **Inputs:** every external input (HTTP body, listing payload, webhook, env, Google token, scraped HTML/JSON) is parsed
  into a typed, bounded model that rejects unknown/oversized/malformed data with a stable problem code. No `dict[str, Any]` crossing a boundary.
- **Money:** `Decimal`/`NUMERIC` end to end including the engine; rounding rule stated; property tests for ledger and quota. No `float`.
- **Time & I/O:** explicit timeouts and a total deadline on every outbound call; bounded retries with jitter; circuit breaker for scrapers; no blocking I/O on the event loop; no unbounded memory (streams, size caps, pagination).
- **Concurrency:** every state change is idempotent and race-safe (unique keys, `SELECT … FOR UPDATE`, advisory locks); each has a concurrency test, not only a happy path.
- **Failure:** all failure modes map to a terminal state and a defined credit outcome (blueprint §2); crashes, OOM, deploy restarts and duplicate deliveries leave consistent data; graceful shutdown.
- **Security:** authn/authz on every route, tenant-scoped repositories (404 not 403), CSRF/Origin checks, signature checks before parsing, no secrets or personal data in logs, least-privilege DB roles, dependency pinning, SSRF-safe URL handling for user-supplied refs.
- **Operability:** structured logs with ids, metrics/health/readiness, error tracking on unexpected errors (Better Stack via the Sentry SDK, ADR 0009), config only via typed settings, migrations expand→contract and reversible in practice, runbook entry for anything an operator must do.
- **Quality gates:** typed (pyright strict for `packages/` and `services/`), tests offline and deterministic, coverage floor, named invariant tests, semgrep/ruff/gitleaks green.
- **Legal/GDPR:** tagged per `rules/legal-tags.md` while you write it, not afterwards.

If a requirement cannot meet this bar yet, do not ship a weaker version silently: implement the safe subset, register the gap in
`docs/LIMITATIONS.md`, and say so in the PR.

## Working procedure

1. Pick the ticket; read the blueprint section it names.
2. If you need to know how the POC behaves, read the relevant POC file (read-only) and write down the *requirement* and the
   *defect* in your own words (PR body or `CONTEXT.md` §5). Then close the POC file.
3. Design the module from the blueprint's contracts (typed inputs/outputs first), write the tests first (invariants, failure, concurrency), then the code.
4. Update `CONTEXT.md` per `rules/context.md` and the PR per `rules/pull-requests.md`.

## Do not

- Say "ported from the POC", "wrapped POC code", or paste POC code into a PR, comment or issue.
- Keep a POC quirk because a POC test expected it; write the right test.
- Reduce scope to "match the POC" when the blueprint asks for more (auth, ledger, idempotency, SSE, backups are new work).
