# Rule: maintain CHANGELOG.md

`CHANGELOG.md` at the repo root follows [Keep a Changelog](https://keepachangelog.com/) (create it with an
`## [Unreleased]` section if absent).

## When to update

In the same PR as any change that is user-visible or operator-visible:

- API contract: routes, request/response shapes, problem `code`s, SSE events.
- Billing and entitlement behaviour: plans, allowance, passes, grace period, invoices.
- Auth and session behaviour.
- Schema migrations, new env vars, compose/deploy or backup changes an operator must act on.
- Dependency additions or upgrades (the PR body must also say why — `agents.md` §4).
- Security fixes.

Skip pure refactors, test-only changes and doc typos, unless they ship with a notable change.

## Edit pattern

1. Add bullets under `## [Unreleased]` using `Added`, `Changed`, `Fixed`, `Removed`, `Deprecated`, `Security`.
2. End each bullet with the ticket: `(RM-<issue>)`. Breaking changes (`type(RM-n)!:`) are prefixed `**BREAKING**`.
3. Operator actions (migration to run, env var to set, Stripe Dashboard toggle) are stated in the bullet.
4. On a release tag, move `[Unreleased]` to a dated `## [x.y.z] - YYYY-MM-DD` section.

```markdown
### Added
- `POST /api/audits` returns 409 `AUDIT_IN_PROGRESS` with the existing `audit_id` (RM-42)

### Fixed
- Replayed `invoice.paid` no longer creates a second `usage_period` (RM-57)

### Security
- Magic-link tokens are now single-use under concurrent verify (RM-61)
```

## Do not

- Duplicate the blueprint or the issue text; one line per change.
- Log internal refactors with no behaviour change.
- Put secrets, real emails or customer data in entries.
