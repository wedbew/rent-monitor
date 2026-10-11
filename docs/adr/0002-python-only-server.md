# ADR 0002 — Python-only server runtime

- **Status:** accepted (blueprint decision table, "Runtime") · **Date:** 2026-10-11 · **Ticket:** RM-31

## Context
The product is a small SaaS on one VPS with a single maintainer and autonomous agents. Every extra runtime adds an image,
a dependency tree, a test suite and a failure mode.

## Decision
The server is Python only: FastAPI (API), Procrastinate (workers), Postgres. Node exists only at build time to bundle the SPA.
No Node service, no second migration tool, no server-side rendering runtime.

## Consequences
- One image, one lockfile (`uv.lock`), one test runner. Agents need one toolchain.
- The financial engine is Python only; the frontend never derives a financial number (invariant 4).
- Anything needing Node at runtime (SSR, a BFF) is out of scope and needs a new ADR.
