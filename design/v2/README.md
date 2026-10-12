# RentMonitor V2 — Precision

Start with [main-view.html](main-view.html). Compare with [V1](../v1/main-view.html).

- [Moje analizy](analyses.html), [Rynek](market.html) and [the analysis report scaffold](analysis.html?id=p1) are separate pages.
- [Full analysis UX contract](analysis-page-ux.md) specifies how the future data-rich report uses drawers, dialogs and accordions.
- [Design principles](design-principles.md) define the concept, tokens, motion, accessibility and asset provenance.
- [tokens.css](tokens.css) holds the new visual and motion tokens.
- [architecture-hero.jpg](architecture-hero.jpg) is original AI-generated decorative imagery; it is not listing evidence.

Serve both versions from the repository root with `python3 -m http.server 8766 --bind 127.0.0.1 --directory design`, then open `/v2/main-view.html` or `/v1/main-view.html`. The prototype is also usable through direct local file navigation.

Fictional fixtures only; no runtime network calls, finance calculation, payment or audit submission. The home preview-state selector is a review control outside the proposed production interface.

[Desktop preview](main-view-desktop.jpg) · [Mobile preview](main-view-mobile.jpg)

Verified on 2026-10-12 in the local browser:

- Home has no horizontal overflow or controls outside the viewport at 320, 390, 768, 1,024 and 1,440 px. Property grids use 1 / 2 / 3 columns at the intended sizes.
- All five home review states render. Submission opens the credit confirmation. Drawers use the entrance animation; Escape closes them and restores focus after the exit animation.
- Moje analizy and Rynek navigate to separate V2 URLs without dialogs; the clarification filter returns 3 fixtures and selecting Warszawa updates the city summary. Both pages fit mobile width.
- Desktop and mobile screenshots were visually inspected; no browser errors observed. All four scripts pass `node --check`; `git diff --check` passes.

Reduced-motion handling was reviewed in CSS/JS; browser preference emulation was not performed. Cross-document transition support depends on the browser. Formal screen-reader, contrast, and user research validation remain production prerequisites. Backend tests were not run for this isolated design alternative.

UX refinement: viewport-height desktop/tablet sidebar and a mobile navigation side panel; clearly bounded apartment cards with status badges, grouped metrics and full-width actions. Moje analizy includes name/city search, status filtering and empty-result recovery. Updated grids use three columns at ≥1,440 px, two at 761–1,439 px, and one at ≤760 px, accounting for sidebar width.

Refinement verification: no page overflow or controls outside the viewport at 320, 390, 768, 1,024 or 1,440 px; desktop/tablet sidebar height matches the 900 px viewport. Searching `lodz` finds Łódź, an unmatched search shows the recovery action, and the clarification filter returns three cards. Escape from mobile navigation restores Menu focus. Mobile navigation successfully opens the separate home page. [Updated analysis collection preview](analyses-page.jpg).

Report navigation refinement supersedes the earlier summary-drawer interaction: property actions now link to `analysis.html?id=…` and display “Zobacz analizę” (or “Sprawdź postęp”). The example uses the same page. Full analytic rendering is intentionally deferred; the report UX contract defines the next design step.

Verified report navigation: a completed/partial property opens its own page with no dialog; a running property uses the same route with its running status; the example opens `id=p1`; an unknown ID shows the missing-analysis state. Return navigation works. The scaffold has no horizontal overflow at 320, 768 or 1,440 px; no browser errors observed. [Report scaffold preview](analysis-page.jpg).
