# Full analysis page — UX contract

2026-10-12 · Direction for the next report-design step. The current prototype implements navigation and a minimal page scaffold, not the full report.

## Page boundary

“Zobacz analizę” on home or Moje analizy opens `analysis.html?id=<fixture-id>` as a separate page. “Sprawdź postęp” opens the same destination in a running state. The example action opens a clearly labeled example on that page. A complete analysis is never squeezed into a collection drawer.

The report keeps the sidebar, highlights Moje analizy as its parent and offers a clear return path. Production needs a stable audit URL, reload/deep-link support and browser Back/Forward. Returning to the collection should restore search, filter, pagination and scroll. Do not consume a credit just to open an existing report. Unknown/foreign reports follow tenant-scoped 404 semantics; the prototype displays an unknown-ID state rather than silently substituting another property.

## User questions before data structure

The user wants to understand:

1. What does this analysis suggest, and what is uncertain?
2. What rent could this apartment generate, and what stays after owner costs?
3. How much capital does purchase and preparation require?
4. What purchase price meets my return target?
5. What should I check before making an offer?

Use these questions to order the report. Do not recreate the POC's long technical report or expose every engine field as a default table.

## First load: a useful, qualified overview

- Apartment identity, location, size, analysis status and report date.
- A short conclusion supported by the engine, separated from data-quality status. “Gotowa” is job completion, not an endorsement to buy.
- At most three primary financial summaries: estimated owner income after costs, total starting capital, and price meeting the target. Show only canonical engine values with units and assumptions appropriate to the metric. If one is unsupported, show the missing input or omit the metric rather than replacing it with zero.
- Asking price remains clearly named beside purchase context; an estimate is never presented as a recorded transaction.
- Essential warnings and one next step. Missing admin fee, placeholder CAPEX or thin evidence must qualify the compact overview without requiring a click.

Do not lead with IRR/MOIC/CAGR, a ten-year wealth total, multiple confidence percentages or a wall of green badges. Do not hide severe uncertainty to make the overview look clean.

## Report organization

| Section | Compact presentation | Reveal on interaction |
|---|---|---|
| Overview | Qualified conclusion, key summaries, next step | Meaning of a metric or how the conclusion was reached |
| Rent | Bounded estimate, owner-income basis, strongest caveat | Comparables, segment/cohort, adjustments and source evidence |
| Costs and condition | Starting-capital breakdown at category level; material renovation risks | Itemized CAPEX, purchase costs, operating costs, relevant photo/floor-plan evidence |
| Purchase price and scenarios | Target-based price and engine-supported scenario context | Return target, deterministic assumptions, sensitivity and annual cash flow |
| What to verify | A short prioritized checklist | Specific missing inputs and supporting evidence |

The overview is the initial destination. Use a compact local section navigator on a full report; it is distinct from app navigation. Keep detailed tables closed by default. Preserve section state and scroll when opening evidence. On mobile, use stacked sections with concise headings and accessible expansion controls.

## Progressive disclosure rules

- **Accordion:** details belonging directly to a section: costs by category, yearly cash flow, assumptions, long evidence lists. Labels describe content; optionally include item count. Users can open multiple sections. Do not automatically close the section they were reading.
- **Drawer:** bounded evidence in the current report: one comparable, source provenance, one photo assessment, or the explanation of one metric. Give the panel a specific title; retain the report context. On mobile it can use the full screen. Escape/close restores the trigger and report position.
- **Dialog:** a focused task or consequence: confirm rerunning a charged analysis, an engine-supported assumption edit, or a blocking condition. State cost and effect before confirmation. Do not nest dialogs or make a large report a modal.
- **Inline explanation:** a short definition adjacent to a number. Optional tooltips may supplement it, but essential assumptions, cost and risk must remain accessible without hover.
- **Separate page:** the full report itself, comparison or another top-level task. A drawer is not a replacement for a report route.

There should be one obvious way to reach a given detail. Avoid duplicating the same figures across cards, tabs, drawers and bottom tables. Disclosure reduces visual density, not access to evidence.

## Status and recovery

| State | User-facing behavior |
|---|---|
| Running | Explain current work using persisted progress; allow leaving and reopening; no placeholder result values |
| Complete | Show supported results and their qualifications |
| Degraded / incomplete | Preserve usable data, identify missing input and suppress unsupported conclusions |
| Placeholder CAPEX | Prominent preliminary label and a concrete need to validate renovation cost |
| Failed / rejected | Explain the specific recovery and server-confirmed credit outcome |
| Missing / foreign ID | Resource unavailable; return to own analyses, without exposing another tenant's data |

Use versioned engine assumptions and canonical JSON for every money value. Never calculate yields, tax, financing, return or Max Bid in the UI. Do not offer a mortgage calculator or unsupported scenario as though it exists. User-adjustable assumptions require an approved engine/API contract and explicit recalculation behavior.

## Accessibility and acceptance criteria

- A new user can identify the apartment, price basis, result qualification and next step within ten seconds.
- The overview contains no full financial table; deeper data is available in one clearly labeled action from its section.
- Material warnings are readable before interaction and distinguished by wording, not color alone.
- All section controls and evidence triggers work with keyboard and touch; disclosures have correct expanded/control relationships, headings and focus restoration.
- A drawer does not lose the report's scroll or edited context. Confirmation explains whether a rerun consumes another analysis.
- Validate at 320, 390, 768, 1,024 and 1,440 px, with reduced motion, long translated labels and missing fields.
- Conduct task-based research with non-professionals: explain estimated income, identify starting costs, locate a source, recognize a missing fee and find a sensible next action. “Perfect UX” requires this evidence, not aesthetic approval alone.

## Current implementation boundary

Implemented now: dedicated route and links, fictional property identity/status/asking price, visible caveat, parent navigation, return link, unknown-ID state and a small accordion explaining the planned hierarchy. Full analytic data, section navigation, evidence drawers, assumption editing, server progress, persistence of list state and report-specific research are future work. The scaffold explicitly identifies that boundary.
