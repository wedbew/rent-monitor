# Frontend delivery checklist and Claude handoff

2026-10-15 · Use with [implementation-guide.md](implementation-guide.md), [design-system.md](design-system.md) and [frontend-tooling.md](frontend-tooling.md).

## How to use this file

Turn these slices into repository issues with dependencies and acceptance criteria. These are planning slices, not new issue IDs or claims of delivered work. The ordering prioritizes the authenticated analysis journey; do not wait for every creative-tool contract to exist before delivering that journey. Conversely, a placeholder route is not a reason to fabricate a backend integration.

The foundation ticket records selected dependency versions, package manager/runtime, primitive library, browser support and source layout. Later tickets reuse those decisions. Change a shared decision through a small documented update, not by silently introducing a competing stack.

## Slices and exit evidence

The slices are now GitHub issues with dependencies and acceptance criteria; [`docs/FRONTEND-PLAN.md`](../../docs/FRONTEND-PLAN.md) §5 is the
authoritative list. The earlier F01–F13 draft maps as follows (it lacked the data-first smoke test, auth pages, billing,
saved listings, observability and deployment, which the plan adds):

| Draft | Issue | Slice |
|---|---|---|
| — | #263 | FE-00 API smoke over every operation; samples in gitignored `data/` (**first**) |
| — | #264, #265, #266 | FE-A1 problem schema · FE-A2 audit paging · FE-A3 report schema (backend) |
| F01 | #267 | FE-01 Phase 2 authorisation and foundation |
| F02 | #268 | FE-02 typed client, problem copy, sample-derived fixtures |
| — | #269 | FE-03 e2e harness and interaction-coverage gate |
| F03 | #270 | FE-04 tokens, primitives, theme, shell |
| F04 | #271 | FE-05 auth pages and session boundary |
| — | #272 | FE-06 Pulpit |
| F05 | #273 | FE-07 Nowa analiza (URL) and SSE |
| F06 | #274 | FE-08 report page |
| F07 | #275 | FE-09 Moje analizy |
| — | #276, #277 | FE-10 saved listings · FE-11 packs, checkout, purchases |
| F12 | #278, #279 | FE-12 settings · FE-13 public pages and legal text |
| — | #280, #281 | FE-14 browser observability · FE-15 Caddy, CSP, deploy |
| F08 | #282 | FE-16 Rynek (needs `/api/market/*`, #21) |
| F09, F10, F11 | #283, #284, #285 | FE-17 manual analysis · FE-18 interior · FE-19 listing assistant (owner decisions) |
| F13 | #286 | FE-20 release hardening |

Blocked slices keep honest unavailable states. The repository's delivery gates and actual dependency contracts take precedence.

## Page implementation worksheet

Before coding a route, fill this in the issue/PR or a short feature note:

```text
User task:
V2 reference and principles retained:
Placeholder content/layout being replaced:
Route and active navigation mapping:
Contract operations confirmed in code/OpenAPI:
Missing backend contract or product decisions:
Data provenance and missing/zero semantics:
States: initial / loading / empty / filtered empty / ready / partial /
        validation error / network failure / session expiry / unsupported:
Mutation cost, confirmation, duplicate/retry handling:
Keyboard/touch/focus and mobile behavior:
Sensitive inputs, persistence and erasure/cleanup:
Meaningful tests and review screenshots:
Acceptance criteria and explicitly deferred work:
```

For a collection also define ordering stability, page size/cursor, sort/search/filter ownership, URL state, total-count availability and what happens when records change between pages. Do not claim a total or “no more results” from a capped incomplete array.

For an AI/media operation also define input and output versions, progress/cancel semantics, billing outcome, retry safety, partial outputs, retention, provider processing, original-vs-generated presentation and export permissions. UI cancellation is not proof of server cancellation.

## Definition of done for a feature PR

- [ ] Ticket and accepted Phase 2 scope identified; repository rules followed.
- [ ] Required contract exists; proposed endpoints/response fields are not silently invented.
- [ ] Uses shared shell/tokens/components; no page-specific design-system fork.
- [ ] Current owner decisions preserved: light default, app-wide dashboard, distinct tools, no chat, border/icon hover.
- [ ] Realistic content and complete relevant states; placeholder/mock labels remain wherever integration is absent.
- [ ] UI and request types have deliberate null/unknown/error handling; report schema/version recognized.
- [ ] User content is text/safely rendered; no credential/provider leakage or cross-user cache exposure.
- [ ] Keyboard, touch, focus, reduced motion, long Polish text, both themes and narrow/zoomed layouts reviewed.
- [ ] Every page, popup and clickable element registered and exercised by an e2e test; interaction-coverage gate green.
- [ ] Each data view renders at least 5 distinct sample-derived scenarios; screenshots reviewed rather than blindly regenerated.
- [ ] Production build passes; no fixture fallback, debug controls or service-worker mock startup in production.
- [ ] Docs/limitations/context updated when affected; PR includes repository-required Context and Legal/GDPR lines.
- [ ] Existing required checks remain intact. No blanket lint/test disabling, hidden browser errors or unreviewed dependency changes.

Record commands and outcomes. Separate “verified in source”, “tested”, “proposed” and “not implemented”. If a check cannot run, state the reason and affected confidence; never replace it with an invented passing claim.

## Ready-to-use Claude task prompt

Copy this with a concrete ticket/slice, not as a request to build every tool at once:

> Implement the authorized frontend slice [ticket/scope] using `design/v2` as the starting point. Read `.agent/agents.md`, `CONTEXT.md`, `docs/STATUS.md`, `design/v2/implementation-guide.md`, `design/v2/design-system.md`, `design/v2/frontend-tooling.md` and the relevant contracts first. This handoff does not override Phase 1 restrictions: confirm this ticket authorizes Phase 2 frontend work before modifying `frontend/`.
>
> Preserve V2's light-default renti.tech identity, app-wide Pulpit, separate analysis/interior/listing destinations, no-chat listing assistant, and fixed border/icon hover behavior. Some pages are placeholders: redesign them using the defined principles and real data instead of copying incomplete cards, market summaries or legal copy. Read the page maturity table and L-024/L-025.
>
> Inspect the actual checkout and installed versions. Reuse its established package manager, shared components and typed API seam. Use native/headless controls with renti tokens; do not introduce a second UI framework, global store, query cache, Node service or client financial engine. Read current official documentation for the exact library API you use.
>
> First state the relevant contract, missing dependencies and bounded acceptance criteria. Then implement the smallest complete user journey with meaningful error/empty/loading/accessibility states, focused tests and browser review. Keep missing integrations explicit; never substitute mock success in production. Work autonomously inside the ticket's authorization and existing repository workflow. Report what changed, evidence, remaining limitations and any actual blocker.

## Feedback and evolving V2

Treat design review as a change to the shared system when appropriate. If a screen needs a different density or pattern, document the reason, update examples and assess related routes. Preserve the principles while allowing better implementation. Record open decisions in the issue; keep delivery truth in `docs/STATUS.md`, limitations in `docs/LIMITATIONS.md` and this folder focused on frontend design/handoff.
