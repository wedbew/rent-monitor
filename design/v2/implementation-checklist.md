# Frontend delivery checklist and Claude handoff

2026-10-15 · Use with [implementation-guide.md](implementation-guide.md), [design-system.md](design-system.md) and [frontend-tooling.md](frontend-tooling.md).

## How to use this file

Turn these slices into repository issues with dependencies and acceptance criteria. These are planning slices, not new issue IDs or claims of delivered work. The ordering prioritizes the authenticated analysis journey; do not wait for every creative-tool contract to exist before delivering that journey. Conversely, a placeholder route is not a reason to fabricate a backend integration.

The foundation ticket records selected dependency versions, package manager/runtime, primitive library, browser support and source layout. Later tickets reuse those decisions. Change a shared decision through a small documented update, not by silently introducing a competing stack.

## Slices and exit evidence

| Slice | Work | Exit evidence / dependency |
|---|---|---|
| F01 · Scope and foundation | Reconcile Phase 2 authorization, inspect checkout, scaffold/extend SPA, pin tools and create script contract | Clean install, dev/mock startup, types/lint/format/unit/build all run in CI; no production Node runtime |
| F02 · API seam and fixtures | Generate client, normalize problems, define typed scenario fixtures and mock isolation | Deterministic drift check; representative success/error/degraded fixtures; production cannot start mocks |
| F03 · Foundations and shell | Tokens, light/dark, core controls, one navigation registry, desktop/mobile shell | Component catalog examples; theme/storage fallback; keyboard/zoom/narrow-width screenshots; border-only hover |
| F04 · Session boundary | Integrate current auth and entitlement endpoints; private route handling | Expired session and sign-out clear old-user caches/streams/media; deep-link return works; no tokens in storage |
| F05 · URL analysis journey | Entry form, server credit confirmation, submit, pending/result route and SSE | Disposable local backend/browser journey; double-click/network ambiguity, stream replay and terminal credit outcomes tested |
| F06 · Complete report | Agree versioned result model; qualified overview, units/provenance, progressive disclosure | Real canonical fixture rendering; missing/unknown/degraded/schema-version states; no frontend financial calculations |
| F07 · Collection redesign | Replace placeholder cards; pagination, table switch, URL filters/search/sort | Backend pagination/search contract first; tested beyond one page; back/refresh/filter reset and empty state; table semantics |
| F08 · Market inventory | Inventory actual datasets, provenance, grains, coverage, freshness and missingness; redesign Rynek | Data mapping reviewed; asking/deed remain separate; useful real-data view with source dates and genuine gaps |
| F09 · Manual analysis | Approve manual-input/media/ownership contract and job pipeline; implement form | Server validation and limits, unknown-vs-zero, fractional rejection, photo failures/removal and reload behavior; canonical result |
| F10 · Interior tool | Define project/persistence/media/AI cost model; implement one operation at a time | Explicit example vs generated result; operation progress/errors, originals and job costs; render/export only if implemented |
| F11 · Listing assistant | Facts, versioned draft/edit/revision, image-specific advice, enhancement/export boundaries | No chat; no invented amenities; edits survive failed regeneration; partial failures recover; publishing separately authorized |
| F12 · Settings and documents | Implement actual settings; replace legal placeholders with approved versioned content | Real save/error feedback; public document access as decided; no placeholder legal copy at launch |
| F13 · Release hardening | Cross-browser, accessibility, measured performance, build/deep-link/cache/recovery checks | Reviewed evidence, observability redaction, staging/rollback verification through existing deployment process |

F10/F11 can retain honest unavailable states until their integrations are ready. The repository's delivery gates and actual dependency contracts take precedence over the labels/order above.

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
- [ ] Appropriate behavioral/contract/browser checks pass; screenshots reviewed rather than blindly regenerated.
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
