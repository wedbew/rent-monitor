# Rule: register limitations instead of burying them

Known constraints live in `docs/LIMITATIONS.md` (create it with the first entry if it does not exist yet).
The blueprint already names three carried into planning — Otodom ToS / EU database-right exposure, possible
datacenter-IP blocking, and unmeasured per-audit OpenRouter cost — plus the §5 risk register and §6 release gates.
Seed the register from those; do not restate them elsewhere.

## When to update

| Event | Action |
|---|---|
| Limitation, bug or unmeasured assumption discovered during work | Add a new `L-XXX` entry, status `active` |
| Limitation fixed in code | Status `resolved`, add **Resolved** date and PR/issue; move to the *Resolved* section |
| Deliberately deferred | Status `deferred`, link the issue or the blueprint §4.8 step in **Target** |
| Assumption invalidated (e.g. a blueprint *estimate* is measured, a release gate result comes in) | Edit or supersede the entry; keep history |
| A blueprint *inferred* / *estimate* claim you could not verify | Register it, tagged `unverified` |

## Entry format

In parallel work, record new evidence immediately in the unique RM handoff using an issue-local key;
the integrator assigns the next canonical L ID and updates this register/references in the same feature
PR before readiness (`parallel-work.md`). Never invent a global number from a stale branch or pause
unrelated implementation for an ID collision. Existing IDs and history remain immutable.

```
### L-012 — <short title>
- **Status:** active | resolved | deferred
- **Discovered:** YYYY-MM-DD
- **Affects:** module, route, queue, table or release gate
- **Evidence:** confirmed (test/log/vendor page) | inferred | estimate
- **Description:** factual, no speculation
- **Workaround:**
- **Target:** issue / blueprint section / release gate #
```

IDs increment (`L-010` → `L-011`); never reuse a retired ID.

## Always register

Scraping / anti-bot and legal exposure, memory and connection budgets, RPO/RTO claims not yet drilled, Stripe API-version
or BLIK-bank coverage gaps, KSeF/VAT treatment awaiting the accountant, LLM cost and quality gaps, any
`succeeded_degraded` path that hides a missing input.

## Cross-links

- Mention critical `active` limitations in the PR body when your change touches them.
- Resolving one that a release gate depends on → note the gate evidence in the entry.

## Do not

- Leave a known limit only in a code comment or a commit message.
- Delete an entry; resolve or supersede it with a note.
- Use the register as a TODO list — actionable work is an issue.
