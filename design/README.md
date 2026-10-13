# RentMonitor design direction

2026-10-13 · Design proposal, not a shipped application.

## Design alternatives

| Version | Direction | Start |
|---|---|---|
| V1 | Warm paper, terracotta, serif headings, rounded surfaces, navigation rail | [V1 home](v1/main-view.html) |
| V3 | Light default + dark support, Polish architectural identity, forest-green actions, interactive login and fuller report | [V3 home](v3/main-view.html) · [login](v3/login.html) · [review and verification](v3/README.md) |
| V2 | Dark monochrome, architectural imagery, bold sans-serif, precise edges, a viewport-height sidebar, bounded analysis cards and restrained motion | [V2 home](v2/main-view.html) · [principles and tokens](v2/design-principles.md) |

Serve **all three versions** with `python3 -m http.server 8766 --bind 127.0.0.1 --directory design`, then visit `/v1/main-view.html`, `/v2/main-view.html` or `/v3/main-view.html`. V3 login is at `/v3/login.html`. V2's footer links to the corresponding V1 page for comparison. V2 now opens each property on a separate report page; [its UX contract](v2/analysis-page-ux.md) defines progressive disclosure within the future full analysis. Neither version is selected as the production design yet. V2 adds an original AI-generated decorative hero image; provenance and the generation prompt are in its principles file. The following review history describes V1.

Start with [main-view.html](v1/main-view.html). It is a self-contained, responsive, interactive prototype of the signed-in home screen, written from scratch. Open it in a browser, or serve this directory locally with `python3 -m http.server 8765 --bind 127.0.0.1 --directory design/v1` from the repository root.

- [design-principles.md](v1/design-principles.md): product principles, visual language, accessibility and disclosure rules for future views.
- [main-view-spec.md](v1/main-view-spec.md): information hierarchy, interactions, state handling, production handoff and usability acceptance criteria.
- [state-review.md](state-review.md): findings from the roadmap, changelog, context, competitor and POC screenshots.
- [Desktop preview](v1/main-view-desktop.jpg) and [mobile preview](v1/main-view-mobile.jpg): rendered reference images of this direction.
- [Tablet preview](v1/main-view-tablet.jpg): two-column apartment grid with the viewport-height sidebar visible while the page is scrolled.
- [City context page](v1/market.html) and [preview](v1/market-page.jpg): a separate page reached from both the home invitation and the sidebar.
- [My analyses page](v1/analyses.html) and [preview](v1/analyses-page.jpg): a separate collection page with status filtering and contextual property summaries.

The prototype uses fictional fixtures and makes no network requests. No listing photos, source code, documents or data were copied from the POC. Listing detail is demonstrated only as a summary drawer; full property-report and comparison pages remain future work. The analysis collection lives on the separate [analyses.html](v1/analyses.html) page with a status filter and contextual summary drawers. The city context now lives on the separate [market.html](v1/market.html) page, reached by “Sprawdź miasto” and “Rynek”. The prototype's bottom preview controls expose returning-user, first-use, loading, source-unavailable and no-credit states. Those controls are outside the proposed product experience.

This is design exploration for Phase 2. It does not change `frontend/`, backend contracts, financial rules, commercial entitlements or launch gates. No pricing or allowance decision is implied. No dependencies are added.

Responsive follow-up: the desktop/tablet sidebar is sticky and viewport-height; short screens keep account controls accessible. Verified column boundaries at 760 px (one), 761–1,200 px (two) and 1,201 px (three), with no horizontal overflow. At a 600 px viewport height, the sidebar is 600 px and the account control remains visible.

Market navigation follow-up: verified “Sprawdź miasto” and “Rynek” navigate to `market.html` without opening a dialog, city selection updates the summary, and the return link navigates back home. No horizontal overflow at 320, 768 or 1,440 px; no browser errors observed. Both design scripts pass `node --check`.

Verified in the local browser on 2026-10-12: URL error and confirmation, preview progress, missing-data drawer, accordion disclosure, Escape and focus restoration, activity filtering/reset, 12-item history, city switching, first-use/loading/source-unavailable/no-credit states and recovery dialogs. At 320, 390, 768, 1024 and 1440 px the final layout had no horizontal overflow or controls outside the viewport. Desktop and mobile renders were visually inspected. No browser warnings/errors were observed. `node --check design/main-view.js` and `git diff --check` passed. Backend tests were not run for this isolated design artifact. Screen-reader, formal contrast and user research checks remain prerequisites for production implementation.

Primary navigation rule: Pulpit, Moje analizy and Rynek open separate pages. “Wszystkie analizy” follows the same analyses-page route as the sidebar. Drawers show contextual details; dialogs do not replace top-level destinations.

Analyses navigation follow-up: verified both entry points open `analyses.html` with no dialog, all 12 fixtures render, the clarification filter returns 3, and property summaries close with Escape and restore focus. Home still renders only 3 recent summaries. No overflow at 320, 768 or 1,440 px and no browser errors observed.
