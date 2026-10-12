# Main view: design and handoff

2026-10-12 · Proposed signed-in home. Desktop, tablet and mobile share one hierarchy.

## Scope and assumption

“Main view” is interpreted as the application home after sign-in, rather than the public marketing landing page. Polish is the initial language; production strings should live in pl/en translation resources. Anna and all property/market numbers are fictional fixtures. The default view represents a returning user; the bottom preview selector is a review tool, never product chrome.

## First-load hierarchy

1. Navigation: Pulpit, Moje analizy, Rynek; secondary help and account. No permanently visible map, comparison tools or interior AI playground.
2. Greeting and one task: a sale-listing URL and “Sprawdź mieszkanie”. A low-emphasis example makes first use understandable without onboarding.
3. Three aggregate activity counts: completed analyses, results requiring clarification, running analyses. These are mutually exclusive counts in one 12-analysis fixture cohort (8 + 3 + 1). They describe work state, not investment recommendation.
4. Three recent property summaries. Address/identity, size/rooms, asking price, rental estimate if available, meaningful status, essential caveat and one action. More details require the drawer.
5. A quiet city-context invitation. No market numbers load on home. Production omits this module if the market API/flag is unavailable at launch.

The desktop/tablet navigation rail is sticky and limited to the viewport height, with independent overflow on short screens. Property summaries and loading placeholders use three columns above 1,200 px, two columns at 761–1,200 px, and one column at 760 px and below. The third recent summary starts the second row on tablet; it does not stretch across both columns.

The home never exposes IRR, MOIC, cash-flow tables, Max Bid, raw photo detection, source tables or advanced filters on first load. A caution can appear without requiring a click. Do not aggregate financial returns across independent hypothetical listings.

## Interaction contract

| Trigger | Prototype response | Production behavior |
|---|---|---|
| Check URL | HTTPS Otodom listing-path validation; inline error or cost confirmation | Server revalidates the reference and listing kind/ownership; authoritative entitlements and cost |
| Start confirmation | Clearly labeled preview of running state; no request or mutation | Create audit, reserve once, show persisted progress; duplicate active audit opens existing job |
| Activity counter | Filter the fixture cohort; reset returns to three recent summaries | Apply status filter with explicit result count and stable server pagination |
| Property summary | Native side drawer with key facts; closed accordions reveal costs, quality and sources | Canonical API values; entry point to a separately designed full report |
| Moje analizy / Wszystkie analizy | Navigate to `analyses.html`, a separate page listing the 12 fixtures with a status filter; each property opens its contextual summary drawer | Dedicated tenant-scoped list route; saving, comparison and pagination designed later |
| City invitation / Rynek navigation | Navigate to `market.html`, a separate page with city selection, a bounded rental-context example and expandable source details | Dedicated market route with date/provenance; omit unavailable module |
| Account | Available analyses and contextual credit explanation | Account/access/billing page under approved commercial contract |
| Help/example | Three plain-language steps / fixture drawer | Help content / clearly marked example with consent-safe evidence |

Native dialogs provide Escape and focus containment. Overlay close returns focus to the original home trigger, even when the help overlay switches to a property. Clicking the backdrop closes an overlay. Opening a second overlay replaces the first; no nested modal stacks. Field values are preserved through overlays and view-state changes. No arbitrary URL is injected into markup.

## Designed state behavior

| State | Design behavior |
|---|---|
| Returning user | Three recent summaries; 8 ready / 3 requiring clarification / 1 running |
| First use | No activity counters; no zero-dashboard; short empty-state copy and example |
| Loading history | Stable skeleton blocks with an announced loading label; no fabricated success |
| Source unavailable | Visible service notice; existing results remain readable; preserve URL; no fake retry time |
| No credits | Balance and form hint show limit before submit; dialog explains recovery without invented plan prices |
| Invalid URL | Clear error connected to input; input receives focus; entry is retained |
| Running | Progress action rather than rent/return values; no invented progress percentage |
| Partial result | Essential missing administrative fee remains visible on card; no unsupported return/grade |

Additional production cases to implement when API contracts land: session expiry with preserved link; rejected RENT/fractional ownership; listing gone; timeout/worker failure and server-confirmed credit release; degraded successful result and capture; SSE disconnect/replay; unavailable feature; withheld city cohort; stale data; canceled confirmation; account export/delete. These are specified here, not falsely simulated as implemented backend behavior.

## Data mapping and implementation boundaries

- Activity counts/history come from tenant-scoped API queries and a defined grouping policy. Home's “do wyjaśnienia” group is a UX proposal: derive it from explicit engine quality/missing-input fields agreed in the API, not a new invented backend terminal status. A `succeeded_degraded` audit belongs there when it needs user action; a complete low-return deal may still be ready.
- Asking price, rent interval, admin costs, CAPEX, Max Bid, cash flow and confidence are displayed from canonical engine JSON. The client formats values only. No mortgage, tax, yield or wealth computation in this design code.
- Placeholders/absence must be carried through the contract. `prices_are_placeholders` produces a prominent qualification and suppresses unqualified positive verdicts. Do not infer evidence reliability from a grade.
- Source month, observation period, asking/deed basis, cohort count and freshness belong to market values. Production cannot turn the mock fixtures into default fallback market data.
- Credit balance, reservation/capture/release and pass/subscription access come from the server. The prototype does not choose the launch allowance, gross/net VAT display, price, pass duration or refund policy.
- Production content/photos require the project's legal/GDPR feature flags, evidence retention and attribution rules. This artifact contains no real listing images or seller information.
- No production work is started under `frontend/`. Design tokens and interaction contracts can be implemented during N-25/N-26; market work remains N-29 and conditional on D-12.

## Review criteria

- A person can identify the main action in five seconds, submit a link without choosing settings, and understand cost before starting.
- First load has three or fewer recent items and no analytical table or speculative return total.
- Essential price basis, estimate units and missing-data warning remain visible without opening a drawer.
- Keyboard users can reach every control, operate drawers/accordions, close with Escape and return to the trigger.
- At 320, 390, 768, 1024 and 1440 px, there is no horizontal page overflow, clipped control text or overlapping panels. Mobile inputs use 16 px text and targets remain at least 44 px.
- Confirm field errors, no-credit/source-unavailable recovery, filter reset, all-list consistency and city switching in the browser.
- Before production: validate colors with a contrast tool, test with screen readers and actual API strings, conduct the task-based research described in the principles, and validate commercial/legal copy. Prototype inspection does not replace those checks.

## Primary navigation contract

Pulpit (`main-view.html`), Moje analizy (`analyses.html`) and Rynek (`market.html`) are separate pages, never overlay collections. Both “Moje analizy” in navigation and “Wszystkie analizy” on home lead to the analyses page. Each destination uses the same app shell, highlights its active navigation item and supports browser Back/Forward, reload and direct access. Secondary evidence and property summaries can still use drawers without leaving the current collection. The prototype analyses page supports All / Ready / Needs clarification / Running filters; backend pagination, search, saving and comparison remain future work.
