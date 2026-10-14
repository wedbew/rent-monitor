# V2 frontend implementation guide

2026-10-15 · Owner-selected starting point for the frontend · Implementation handoff for Claude and other contributors.

## 1. Start here

**Build the frontend from V2's principles and information architecture. V2 is a starting point, not a frozen screen-by-screen specification.** Improve inadequate layouts and incomplete flows as real data, accessibility work and user feedback require. Preserve the decisions below unless the owner changes them. A polished prototype is not evidence of an implemented backend feature.

Read in this order:

1. [Repository rules](../../.agent/agents.md), [CONTEXT](../../CONTEXT.md) and [delivery status](../../docs/STATUS.md).
2. This guide and the [current design README](README.md).
3. [Design system](design-system.md), [frontend tooling](frontend-tooling.md) and [delivery checklist](implementation-checklist.md).
4. [Design principles](design-principles.md), [report UX contract](analysis-page-ux.md) and the live prototype pages.
5. Relevant sections of [BLUEPRINT](../../docs/BLUEPRINT.md), [TOOLCHAIN](../../docs/TOOLCHAIN.md), [OpenAPI](../../docs/openapi.json) and actual API code.

**Scope:** this handoff does not create a production frontend, install tools or change the repository's Phase 1 restriction. The authorized Phase 2 ticket must reconcile that restriction before implementation under `frontend/`. This documentation request needs no phase change. Follow the repository issue/branch/PR process when implementation begins; do not create a second process from this guide.

### Sources and precedence

| Source | What it establishes |
|---|---|
| Latest owner instruction | Product direction, including V2 as the frontend starting point |
| Repository rules, approved architecture and current contracts | Runtime, security, money, isolation, delivery constraints |
| This handoff and V2 principles | Implementation direction and proposed frontend defaults |
| Prototype HTML/CSS/JS | Visual and interaction reference, including explicitly incomplete examples |
| Screenshots | Historical review evidence; live files and latest instructions take precedence |

The new library/tool choices are recommendations for the foundation ticket, not dependencies already adopted. Confirm compatible versions then record the decision. If a source conflicts with the approved architecture, flag the conflict in the ticket rather than silently switching frameworks or designing a new service.

## 2. Preserve these product and visual decisions

- Company **renti**, domain **renti.tech**; use the supplied outlined logo assets and favicon, including the dark logo. Retain font licenses.
- Light is the first-visit default even when the system prefers dark. Explicit light/dark choice persists; storage failures must not break rendering. Theme text and moon/sun icons agree.
- Pulpit is the dashboard for the entire application. It is not the analysis submission screen.
- Separate destinations: Pulpit, Nowa analiza, Moje analizy, Rynek, Architekt wnętrz, Stwórz ogłoszenie and Ustawienia. Regulamin and Polityka prywatności are secondary destinations.
- URL/manual inputs are tabs **inside Nowa analiza**. Reports have their own shareable route. Top-level navigation must not become dialogs.
- Stwórz ogłoszenie is an assisted workflow with facts, draft and photo tips, **without a chat interface**.
- Use restrained typography, forest/mineral colors, precise spacing and clear borders. Desktop navigation has a viewport-height rail; mobile gets an accessible menu. Remove the former “TWOJA PRZESTRZEŃ” navigation caption.
- Latest hover decision: a clean border and brief icon animation. Keep labels and control bounds fixed. Do not reintroduce glass, moving green bars, reflections, icon tiles or raised hover shadows.
- Critical warnings, units, source dates and missing-input information remain visible. Avoid inventing financial values, AI results, completed work or source coverage to make a page look populated.

What may evolve: density, exact spacing, responsive breakpoints, table columns, form grouping, illustrations, optional motion and dashboard composition. Use actual content and acceptance criteria to justify changes. Keep the design tokens and component examples current when a shared decision changes.

## 3. Page maturity and implementation map

Proposed SPA paths below are **UI route proposals**, not existing server endpoints. Keep URLs stable once adopted. An authenticated `/app` namespace is recommended to distinguish app routes from public legal/auth pages; confirm with deployment/auth work.

| Destination / reference | Proposed route | Reuse from V2 | Design/integration work remaining |
|---|---|---|---|
| [Pulpit](main-view.html) | `/app` | App-wide orientation, tool entry points, recent activity | Real activity/credit contracts, loading/empty/error states; never fabricate creative-project history |
| [Nowa analiza](new-analysis.html) | `/app/analyses/new` | URL/manual tabs, field grouping, photo previews | Live URL journey; separate manual-input/upload contract before enabling that route |
| [Moje analizy](analyses.html) | `/app/analyses` | Navigation, search/filter intent, visible status | **Replace inadequate placeholder cards**, add proper pagination and a table-view option; design with large collections |
| [Report](analysis.html?id=p1) | `/app/analyses/:auditId` | Dedicated report destination and disclosure principles | Full canonical report rendering, pending/terminal states and schema compatibility; scaffold is not a complete report |
| [Rynek](market.html) | `/app/market` | Separate market destination; provenance concepts | **Placeholder to avoid a blank page**; substantially more market data exists than it displays; inventory that data and redesign |
| [Architekt wnętrz](interior.html) | `/app/interior` | Room/style/goal workflow | Generic example plan only; project, media, AI, render/export and persistence contracts are pending |
| [Stwórz ogłoszenie](create-listing.html) | `/app/listings/new` | Non-chat assistance, facts → draft → photo tips | Local template and brightness preview only; AI assessment, enhancement/export and provider publishing are pending |
| [Ustawienia](settings.html) | `/app/settings` | Shell/destination | Placeholder; build real settings only against explicit contracts |
| [Regulamin](terms.html), [privacy](privacy.html) | `/terms`, `/privacy` | Reachability and document layout | Placeholder content is not operative legal copy; approved documents/versioning needed before launch |

See limitations [L-024 and L-025](../../docs/LIMITATIONS.md). A placeholder can establish navigation, spacing, color, typography and interaction principles while its content/design still needs replacement. “V2 selected” does not mean every placeholder is approved.

## 4. Architecture to implement

### Retain the existing architecture direction

Use the blueprint's **Vite + React 19 + TypeScript SPA**, statically served by Caddy on the API's origin. Python remains the only server runtime. Do not introduce SSR, a Next.js server, a Node API, a BFF or a second session system for frontend convenience.

Inspection on 2026-10-15 found no `frontend/` directory or frontend package manifest in this checkout. The blueprint's historical “keep existing SPA” language is not proof that an application exists here. Recheck the checkout before scaffolding; extend an existing implementation if one has since landed.

Proposed baseline:

| Responsibility | Recommendation |
|---|---|
| Routing | React Router, client SPA mode; route-level code splitting and error boundaries |
| Server state | TanStack Query over the blueprint's `openapi-fetch` client |
| API types | `openapi-typescript` generated from committed `docs/openapi.json` |
| Interaction primitives | Native HTML first; Base UI for complex accessible controls; see design-system guide |
| Styles | Semantic CSS variables + CSS Modules, with small global foundations |
| Larger forms | React Hook Form; explicit form-value → request adapters; Zod only for justified UI schemas |
| UI state | Local React state/reducers; URL for shareable collection filters; small context for theme/session access |

Use React Router in its appropriate client mode ([mode guidance](https://reactrouter.com/start/modes)); it must not introduce a server runtime. For form-library/schema integration, consult the [React Hook Form resolvers](https://github.com/react-hook-form/resolvers) and [Zod documentation](https://zod.dev/) for the versions selected.

Do not add Redux/Zustand, a generic schema-form renderer, a second query cache or a custom component framework before a concrete requirement justifies it. Use effects for external synchronization, not to maintain redundant derived state ([React guidance](https://react.dev/learn/you-might-not-need-an-effect)).

### Keep the layout shallow and responsibilities visible

Suggested structure once Phase 2 work is authorized; adapt to actual files and the [repository layout rule](../../.agent/rules/repo-layout.md):

```text
frontend/
  package.json                 # exact package manager, scripts, engines
  pnpm-lock.yaml
  index.html                   # early theme bootstrap and root
  main.tsx                     # providers and startup
  routes.tsx                   # centralized route definitions
  vite.config.ts
  tsconfig.json
  eslint.config.mjs
  api/
    schema.generated.ts        # generated; never hand edit
    client.ts                  # transport/error normalization
  ui/
    Button.tsx                 # domain-free wrappers + adjacent module CSS
    Field.tsx
    Dialog.tsx
  shell/
    AppShell.tsx
    navigation.ts              # single desktop/mobile destination registry
  features/
    analyses/                  # forms, hooks, list/detail and their tests
    market/
    interior/
    listings/
  styles/
    tokens.css
    globals.css
  test/
    setup.ts
    handlers.ts                # contract-shaped MSW fixtures
  e2e/
    analysis-journey.spec.ts
    navigation.spec.ts
```

This is a direction, not permission to create empty directories. Add a directory when it has multiple real contents; colocate feature tests and CSS. Do not introduce pass-through `src/app/lib` trees. Any necessary tool-specific layout exception belongs in the PR. Keep UI primitives free of API/business imports; features consume `ui`, `api` and their own logic; shell consumes a stable route registry. Import across features through a small public entry when needed; avoid circular dependencies and giant barrel files.

## 5. Contract-first API work

Confirmed contracts and gaps from code inspection, not assumptions based on mock screens (also registered as [L-026](../../docs/LIMITATIONS.md#l-026--frontend-collection-and-report-typing-need-contract-work)):

- `packages/rm_contracts/audits.py` defines URL/id `AuditCreate` with `listing_ref`, `lang` and `analyst`. It does **not** accept the manual form or arbitrary images. Do not POST extra fields and hope the server accepts them.
- `GET /api/audits` in `services/rm_api/audits.py` currently returns an array with only `limit` (default 50, maximum 100). It does **not** provide a cursor/page, total count or collection-wide search/filter contract. A frontend cannot honestly paginate the complete history using this alone.
- Report `result` is currently an opaque object in `AuditOut`; generating OpenAPI types will not magically type its internal sections. Agree a versioned report schema/adapter and test unknown or unsupported versions. Do not use unchecked casts as a report schema.
- Progress uses `GET /api/audits/{audit_id}/events`. Some blueprint route descriptions are broader than implemented code; for example, do not display cancellation as working until its route is confirmed.
- Manual analyses, interior projects, creative media and AI listing assistance need explicit backend capabilities. Keep separate typed mock handlers until those exist. Do not invent `/api/interior` or upload endpoints in production code.
- Consult actual billing contracts and [Paddle pilot specification](../../docs/PADDLE-INTEGRATION.md); do not implement obsolete subscription/pass screens from historical blueprint prose.

For every feature, write a small contract map: operation, request, success, problem codes, auth, entitlements, side effects, idempotency/retry policy, progress, missing-data behavior. Distinguish verified routes from proposed extensions in the issue and PR.

Generate types with the checked-in schema, import request/response types and implement **explicit adapters** between form strings, transport types and display models. UI refinements are allowed; silently redefining API meaning is not. Reject or safely display incompatible responses at the appropriate boundary. Do not introduce a second hand-maintained copy of the complete API schema.

### Transport, cache and errors

- Use relative same-origin `/api` URLs, existing session cookies and server Origin validation. API error bodies are RFC 9457 problems; map stable codes to safe Polish actions and retain request IDs for support.
- Set retry, stale time, invalidation and cache ownership deliberately. TanStack Query has behavior defaults that must be reviewed, especially retries and refetches ([official defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)).
- Do not automatically retry paid/costly mutations. Disable accidental double submission; use idempotency only where the server contract supports it. A browser abort is not proof that a submitted job was cancelled.
- Reconcile server responses before changing credit displays. Refetch authoritative entitlement/account state after settlement; never derive credits from local counters.
- Use bounded read retries for transient failures. Do not retry 401/403/404/validation problems indefinitely. On session expiry close streams, clear tenant-scoped caches and media and return through the sign-in flow.
- Include user/tenant scope in cache ownership; clear all prior-user state on sign-out or account changes. Do not persist financial reports or personal data to browser storage by default.
- Distinguish initial loading, refreshing with prior results, empty, filtered-empty, offline, permission/feature unavailable, degraded success and recoverable failure. Stale content may remain visible only with an honest status.

### EventSource lifecycle

Keep the SSE hook small and tied to one active audit. Reuse the accepted response's validated same-origin events URL. Parse event payloads defensively, deduplicate replay and reconcile the canonical audit after terminal events. Display the server's stages, percentages and charge outcomes; no fake progress timers.

Native EventSource reconnects on the same instance with its last event ID. A newly constructed instance does not inherit that cursor, and native EventSource cannot be given an arbitrary `Last-Event-ID` header. Do not invent a query parameter for resume unless the server implements it. Re-fetch canonical status after remount; agree any cross-instance replay extension with backend work.

Close on unmount, logout and confirmed terminal completion; handle React Strict Mode's repeated setup/cleanup. Show a reconnecting state for interruptions. If a bounded polling fallback is chosen, document its contract, backoff and stop conditions. Test duplicates, disconnect/reconnect, terminal replay, expired session and an unknown event. Event IDs need not be contiguous for one user's stream.

## 6. Forms, media and guided tools

### Forms

Keep transport values separate from editing state. Money/area fields need tests for empty strings, `0`, Polish decimal commas, invalid/partial input and precision. An unknown cost is `null`/absent according to the contract, never silently zero. Do not convert every field through `Number()` or spread a form into a request body.

Use labels, descriptions, fieldsets and inline errors; after invalid submission focus an error summary/first invalid field. Preserve entered values after failures. Avoid wiping forms on background query refresh. For multi-step flows preserve deliberate edits when moving backward; define whether changing source/method retains or discards each draft. Ask before discarding genuinely unsaved user work, not before ordinary navigation.

Frontend checks improve feedback; server validation, ownership, upload rules and entitlements remain authoritative. SALE-vs-RENT classification cannot be inferred from a valid Otodom URL. Fractional ownership must also be rejected server-side. Manual analysis needs a separately approved schema and pipeline, not reuse of the URL endpoint with hidden fields.

### Media

V2's 25-file / 10 MB JPG/PNG/WebP limits describe its local preview, not an agreed upload contract. Establish MIME/content verification, per-file/total limits, dimensions, orientation, processing, retention, erasure, ownership and retry/cancellation before shipping uploads. Browser `accept`/MIME checks alone do not validate a file.

Revoke object URLs when removed or no longer needed; handle decode failure, duplicate selection, large images and low-memory phones. Scope images to the current job/project. Never put raw files or base64 in global stores, query keys, logs, analytics or localStorage. If persistent drafts are required, specify the server-backed model and privacy implications first.

Render image-specific assessment with an explicit source/status and a suggested action. Distinguish advice, a generated preview, an exported image and the original. Never imply the CSS brightness preview is an improved/exported file. Preserve originals and truthful representation. Any provider processing must follow repository image/personal-data tagging and approved feature flags.

### Interior and listing assistance

Model structured steps and jobs, not chat messages. A listing draft should track its input version and user edits. Regeneration must not silently overwrite edited text. Suggestions need accept/dismiss actions and clear applicability; missing facts must remain questions/placeholders rather than invented amenities.

Furniture, clutter, lighting and framing guidance should become image-specific only after real assessment. Show progress/error/retry per operation; a partial image failure need not erase a valid text draft. Keep draft generation, image assessment, enhancement, export and publishing distinct operations with explicit costs and permissions. Publication to Otodom is a separate reviewed capability, not an implied consequence of “Stwórz ogłoszenie”.

## 7. Financial, trust and security boundaries

Display canonical engine values only. No client IRR, yield, tax, cash flow, CAPEX, Max Bid or credit-settlement implementation. Display formatting is allowed; business derivation is not. Preserve decimal precision at the transport/display boundary, including large amounts; test the formatter rather than converting money blindly to binary floats. Show asking vs deed provenance separately, administrative fees as costs, and unknown vs zero accurately.

Escape user content through React text rendering. Do not port prototype `innerHTML` patterns for untrusted input. If rich content is necessary, define a restricted renderer/sanitization policy and tests. Validate external navigation URLs and uploaded-media URLs; never expose provider keys or session tokens to the app bundle. All `VITE_*` values are public ([Vite environment guidance](https://vite.dev/guide/env-and-mode)).

Keep analytics/errors free of raw listing URLs, descriptions, images, notes and contact details. Redact request/response bodies. Disable session replay by default unless approved. Feature flags hide unsupported entry points but are not authorization. Session checks and tenant access are enforced by the API, including indistinguishable foreign/unknown 404s.

## 8. Delivery order and definition of done

Use the [delivery checklist](implementation-checklist.md) to turn this handoff into small issues:

1. Foundation/toolchain and typed mocked client; component examples.
2. Theme, navigation and responsive app shell.
3. Authenticated URL-analysis journey and SSE, including server credit confirmation and canonical report states.
4. Analyses collection and report completion; coordinate pagination and report-schema contracts.
5. Data inventory and redesign of Rynek.
6. Manual-input analysis after its backend contract.
7. Interior/listing integrations one operation at a time; keep unimplemented paths explicitly unavailable.
8. Settings and approved public documents; launch verification.

Scaffolding a route is not completing its feature. A completed slice has its real states, keyboard/touch behavior, contract tests, screenshots and an honest scope note. New visual requirements should refine the shared component first, not add a page-specific override chain. Stop introducing features when the ticket's acceptance criteria are met; capture further work separately.

The [tooling guide](frontend-tooling.md) defines proposed scripts and CI gates. Existing backend gates remain required. Do not deploy/publish based on this handoff; follow repository deployment and pre-launch rules.
