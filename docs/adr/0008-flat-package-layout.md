# ADR 0008 — Flat package layout (no `src/`)

- **Status:** accepted · **Date:** 2026-10-11 · **Decided by:** maintainer · **Ticket:** RM-61
- **Amends:** blueprint §4.1 layout (paths only)

## Decision
Python packages live at `packages/<dist>/<module>/` and `services/<name>/<module>/`, with `pyproject.toml` beside the module.
The `src/` layer is dropped. Rule: `.agent/rules/repo-layout.md` (no directory with a single child directory).

## Consequences
- Shorter paths everywhere; blueprint path comments changed from `…/src/rm_core/…` to `…/rm_core/…`.
- The `src/` layout's protection against importing the working tree by accident is not needed: the workspace installs
  every package editable and tests run through `uv run`.
