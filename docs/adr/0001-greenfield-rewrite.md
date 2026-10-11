# ADR 0001 — Greenfield rewrite; the POC is reference only

- **Status:** accepted · **Date:** 2026-10-11 · **Decided by:** maintainer
- **Supersedes:** blueprint §4.0 rule 1 ("wrap, don't rewrite"), §4.1 "UNCHANGED engines", §4.8 step 1 as worded, TOOLCHAIN §8 decision 2 ("keep `apps/` untouched").

## Context
The blueprint assumed the proof of concept (`otodom-rent-report`) would be copied into `apps/` and given two seams. A first
attempt (copy of three packages) showed what that brings: ~190 files and ~590 tests coupled to a 65 MB on-disk corpus,
float money, a sync engine that fetches network data from inside itself, SQLite caches, and files-as-database. The goal is a
production-ready service that is safe under real traffic, not a hosted prototype.

## Decision
Write the product from scratch. The POC is read-only reference for requirements and for the defects to avoid. No POC code,
tests, fixtures, corpus or docs are copied. Blueprint paths under `apps/` remain the locations of the new packages.
Rule: `.agent/rules/poc-reference.md`.

## Consequences
- Slower first milestone; far lower defect inheritance. Engine math is re-derived from the blueprint and requirements and
  re-verified by the four named invariant tests plus new property tests.
- The `ContextRepository` / `ProgressSink` seams become native design (no retrofitting).
- `CONTEXT.md` §4 becomes a requirements-and-lessons map, not a porting map.
- Open question for the maintainer: formulas and thresholds that exist only in the POC (e.g. grade cut-offs, tax model)
  must be specified in the issue before implementation; agents ask, they do not read them out of POC code and transcribe.
