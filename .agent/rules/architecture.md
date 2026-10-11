# Rule: keep the spec and the code in agreement

Spec of record: `docs/BLUEPRINT.md` (RentMonitor SaaS — Architecture & Implementation Blueprint). `agents.md` §0 says
that when the blueprint and the code or rules disagree, you stop and ask in the issue. This rule says what to do
when your change touches a system boundary.

## When this applies — and what to update in the same PR

| Change | Update / check |
|---|---|
| New, removed or re-authenticated route under `/api/*` | Blueprint §2 *Route map*; OpenAPI is regenerated (`scripts/gen_openapi.py`) so `frontend` types do not drift |
| New or changed error `code` | Add it to `rm_contracts.problems` **first**, then to the blueprint §2 *Error contract* table (HTTP status, retry, credit outcome) |
| Table, column, constraint or index change | Alembic migration (expand → deploy → contract), blueprint §3 models; keep `asking_is_not_deed` and ledger CHECKs intact |
| Auth / session / Origin / cookie behaviour | Blueprint §2 *Auth decision*; tenant-isolation and Google/magic-link tests |
| Stripe event handling, Checkout, pass, entitlement, VAT outbox | Blueprint §3 *Stripe webhook lifecycle*, *BLIK*, *VAT invoices*; the named billing tests in §4.6 |
| New env var or setting | `.env.example` (names only), blueprint §4.2, README *How to run* |
| New or resized container, memory/CPU limit, queue or worker pool, DB pool | Blueprint §1 resource matrix and §6 *Connection budget* (peak must stay under 70 of `max_connections=100`) |
| New external service or client (Otodom, OpenRouter, GUS BDL, Moniter, Stripe, Nominatim, Fakturownia, Resend, …) | Injectable client with explicit timeouts + offline fake (`agents.md` §3); blueprint cost table and risk register §5 |
| New top-level directory or package, or a `services/*` ↔ `packages/*` dependency | Blueprint §4.1 layout; `packages/*` must never import `services/*` |
| New named test that guards an invariant or release gate | Blueprint §4.6 table / §6 *Release gates* |

## Engines are greenfield

`apps/*` contain **new** code (ADR 0001, `poc-reference.md`). Do not "wrap" or copy POC modules; design from the blueprint's contracts.

## Procedure

1. Implement against the blueprint as written. If the right design differs from it, **stop and ask** in the issue —
   do not pick silently (`agents.md` §0, §9).
2. If the maintainer approves a deviation, record it in the PR body under "Blueprint deviation" and add an ADR
   `docs/adr/NNNN-<slug>.md` (context, decision, consequences) for anything non-obvious. Prefer an ADR over long prose.
3. Edit `docs/BLUEPRINT.md` only when the ticket says so or the maintainer approved the deviation; then keep the
   edit minimal and in the section named in the table above. Do not rewrite sections you did not change.
4. Replace stale claims with their new status; keep the blueprint's *confirmed / inferred / estimate* labels honest.

## Do not

- Change architecture silently in code only.
- Put task checklists in the blueprint — the implementation order is §4.8; work items live in issues.
- Put the limitation register in the blueprint — use `docs/LIMITATIONS.md` (see `limitations.md`).
- Duplicate blueprint content in README or `agents.md`; link to the section instead.
