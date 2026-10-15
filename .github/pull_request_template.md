Closes #

## What changed
<!-- One paragraph. Blueprint section(s) implemented: -->

## How it was tested
<!-- Named tests added or changed. Paste the pytest summary line. -->

## Definition of done
- [ ] Title is `type(RM-<issue>): subject`
- [ ] New behaviour has named tests; bug fixes start with a failing test
- [ ] No `invariant` test deleted, skipped or weakened
- [ ] Money stays `Decimal` / `NUMERIC`; no financial math outside `apps/deal_analyzer`
- [ ] Tenant-owned queries go through a `Principal`-scoped repository
- [ ] Migration is expand-only (contract comes in a later PR), pytest-alembic and squawk pass
- [ ] Golden DealAnalysis snapshots unchanged, or each diff explained below
- [ ] No new dependency, or the reason is given below
- [ ] **Frontend:** `.agent/rules/frontend.md` checklist holds (`make fe-check` summary pasted), or no `frontend/` change
- [ ] **Legal / GDPR:** tags added / changed / removed, or none (`.agent/rules/legal-tags.md`)
- [ ] **Context:** `CONTEXT.md` updated (§n), or not affected and why (`.agent/rules/context.md`)

## Deviations from the blueprint
<!-- None, or what and why. -->
