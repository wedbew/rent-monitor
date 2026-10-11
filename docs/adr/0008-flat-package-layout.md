# ADR 0008 — Flat package layout (no `src/`, no same-name nesting)

- **Status:** accepted · **Date:** 2026-10-11 · **Decided by:** maintainer · **Ticket:** RM-61
- **Amends:** blueprint §4.1 layout (paths only)

## Decision
The package folder is the module: `packages/rm_core/`, `packages/rm_contracts/`, `services/rm_api/`, `services/rm_worker/`, each
with its `pyproject.toml` and the `.py` files directly inside (RM-63 completed what RM-61 started; RM-61 had left
`packages/rm-core/rm_core/`). The `src/` layer and the same-name nesting are dropped. Rule: `.agent/rules/repo-layout.md` (no directory with a single child directory).

## Consequences
- Shorter paths everywhere; blueprint path comments changed from `…/src/rm_core/…` to `…/rm_core/…`.
- The `src/` layout's protection against importing the working tree by accident is not needed: the workspace installs
  every package editable and tests run through `uv run`.
