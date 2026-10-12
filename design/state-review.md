# Current state and design evidence

Read on 2026-10-12. This is a documentation review, not a fresh certification of tests, deployment or vendor readiness.

## Confirmed in project documentation

- `docs/ROADMAP.md`, revision 2, is a planning baseline dated 2026-10-11. Frontend is M8 / Phase 2, required for paid launch; beta, operational evidence and launch gates follow. Radar/screener scope remains conditional on D-12.
- `CHANGELOG.md` records the data plane and migrations, API platform, local Docker setup, fetch/vision clients, GDPR tools, engine extraction/classification/rent/CAPEX/cash-flow/Max Bid/assembly/goldens, ledger/flags, AI budget and local CI tooling. These are recorded changes, not evidence of a fully integrated, deployed user journey.
- `CONTEXT.md` records approval of `docs/ENGINE-SPEC.md` (RM-73). The roadmap still describes D-01 as outstanding: the roadmap's decision calendar is older than this context and the engine additions. Treat it as sequencing guidance, not live completion status.
- Changelog wording for RM-19 says awaiting money review, while the context header refers to RM-24 merged after RM-19. This review does not resolve that review/merge discrepancy or assert a fresh CI result.
- CAPEX pricing is explicitly placeholder data (L-007 / B-015). Finance figures must come from canonical engine JSON. The UI must surface placeholder assumptions where they affect a result, rather than give an unqualified positive verdict.
- Pricing/VAT presentation, final Pro allowance, free-tier scope and launch extras remain decisions in context/roadmap. Mockup credit figures are fixtures, not commercial promises.
- The current engine cash-flow model recorded in the changelog is unlevered, after tax, over 10 years. Do not offer a working mortgage simulator in the production UI without an approved engine contract.

## POC evidence reviewed

Read-only directory: `/Users/marcin/Projects/otodom-rent-report/screenshots`. Inspected home, rent map, screener, comparison, listing overview, capital, rent, returns, data quality and interior playground screenshots. These are visual evidence, not permission to import the POC.

| Observation | New design response |
|---|---|
| Home mixes technical pipeline controls and a long report table | One listing input and three recent summaries; no CLI or stage controls |
| Tables show many financial dimensions before a user asks a question | Activity counts first; each property has price, one rent estimate and a meaningful status |
| Listing screens repeat KPI rows above long reports and many tabs | One summary drawer now; later detail pages organize around user questions |
| Dense acronyms, IDs, English diagnostics and local paths appear in product copy | Plain Polish, contextual definitions, diagnostics reserved for support |
| Missing-data warnings sit beside strong-looking scores | Missing evidence changes the result status; no numerical grade when unsupported |
| Bright “BEST” values and ten-year totals compete for attention | Avoid leaderboard claims and speculative wealth totals on home |
| Admin fees and rent can be confused | Always label “Najem dla właściciela”; administrative fees are costs, never income |
| Maps expose hundreds of points before intent is clear | City summary behind a deliberate market action; map belongs to a future market view |

## Competitor evidence

[Rentier.io homepage](https://rentier.io/) reviewed on 2026-10-12. It leads with an address and a simple valuation action, offers sale/rent estimates and comparable properties, and describes reports and city price exploration. Its published application example labels the valuation as based on asking prices. Only the public homepage was reviewed; no claim is made about authenticated UX, accuracy or competitor limitations.

Design inference: preserve that low-friction entry, then differentiate RentMonitor through a clear purchase decision journey: rental estimate, owner costs, renovation needs, evidence quality and a price that meets a return target. Expose these through questions and disclosure, rather than more home-screen metrics. This is a proposed positioning, not a validated user-research result.
