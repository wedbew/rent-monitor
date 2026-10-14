# renti V2 — Precision · renti.tech

**V2 is the owner-selected starting point for the frontend application.** Its design principles and navigation direction are defined; some page layouts and integrations remain placeholders and should evolve during implementation.

For implementation, start with [the implementation guide](implementation-guide.md), then [the unstyled design-system approach](design-system.md), [environment/tooling and production checks](frontend-tooling.md) and [the delivery checklist / Claude handoff](implementation-checklist.md). These are planning documents, not installed frontend tooling or a Phase 1 scope change.

For visual review, start with [main-view.html](main-view.html). Compare with [V1](../v1/main-view.html).

- [Pulpit](main-view.html) is the application-wide dashboard: tools, sample recent activity and a market entry point.
- [Nowa analiza](new-analysis.html) is the separate analysis entry, with Otodom URL and manual apartment-data/photo tabs.
- [Moje analizy](analyses.html), [Rynek](market.html) and [the analysis report scaffold](analysis.html?id=p1) remain separate pages.
- [Architekt wnętrz](interior.html) is the interior-planning workspace.
- [Stwórz ogłoszenie](create-listing.html) is a guided listing assistant with facts, photos, an editable draft and practical tips; it has no chat interface.
- [Full analysis UX contract](analysis-page-ux.md) specifies how the future data-rich report uses drawers, dialogs and accordions.
- [Design principles](design-principles.md) define the concept, tokens, motion, accessibility and asset provenance.
- [tokens.css](tokens.css) holds the new visual and motion tokens.
- [architecture-hero.jpg](architecture-hero.jpg) is original AI-generated decorative imagery; it is not listing evidence.

Serve both versions from the repository root with `python3 -m http.server 8766 --bind 127.0.0.1 --directory design`, then open `/v2/main-view.html` or `/v1/main-view.html`. The prototype is also usable through direct local file navigation.

Light is the default on a first visit, regardless of the operating-system theme. “Tryb ciemny” / “Tryb jasny” controls in the desktop sidebar and mobile header switch every page. Only the explicit appearance preference is saved (`renti-v2-theme` in localStorage); when storage is unavailable, switching still works for the current page. `theme.js` applies the preference before styles paint.

Branding follows the owner-supplied renti.tech lockup: negative Goldman Bold R in a forest square, emerald corner dot, renti wordmark and JetBrains Mono tech suffix. [Light logo](renti-logo.svg), [dark logo](renti-logo-dark.svg), [standalone mark](renti-icon.svg) and [favicon](favicon.svg) use outlined letters, require no Google Fonts requests and work offline. The lockup viewBox trims unused horizontal space. The favicon adds a pale backing behind the cutout for legibility in either browser theme. Font attribution and licenses are in `Goldman-OFL.txt`, `Inter-OFL.txt` and `JetBrainsMono-OFL.txt`; UI typography remains the system stack.

## Placeholder views — not approved designs

- **Moje analizy:** the current cards are temporary placeholders. Their design is inadequate and will be replaced. Search and status filtering work only on the twelve fictional fixtures; there is no proper pagination and no switch to a table view. Replacement designs must include pagination, a table-view option and review with larger collections. These features are pending, not implemented by this appearance update.
- **Rynek:** a temporary view added to avoid a blank destination. Its small city/rent summary does not represent the breadth of market data available to the project. Substantially more data needs a separate information architecture and a fuller view; this prototype does not include it or demonstrate production data integration.
- **Analysis report:** remains a navigation scaffold; see the report UX contract for the planned full report.

These limitations are also recorded in [L-024](../../docs/LIMITATIONS.md#l-024--v2-analysis-collection-and-market-views-are-placeholders).

Fictional fixtures only; no runtime network calls, finance calculation, payment or audit submission. The old analysis-first home and its preview-state selector have been replaced by the application dashboard; earlier verification notes below describe the previous design.

[Light desktop preview](main-view-desktop.jpg) · [Light mobile preview](main-view-mobile.jpg) · [Dark desktop preview](main-view-dark.jpg)

Historical verification on 2026-10-12 (dark version before the light/branding update):

- Home has no horizontal overflow or controls outside the viewport at 320, 390, 768, 1,024 and 1,440 px. Property grids use 1 / 2 / 3 columns at the intended sizes.
- All five home review states render. Submission opens the credit confirmation. Drawers use the entrance animation; Escape closes them and restores focus after the exit animation.
- Moje analizy and Rynek navigate to separate V2 URLs without dialogs; the clarification filter returns 3 fixtures and selecting Warszawa updates the city summary. Both pages fit mobile width.
- Desktop and mobile screenshots were visually inspected; no browser errors observed. All four scripts pass `node --check`; `git diff --check` passes.

Reduced-motion handling was reviewed in CSS/JS; browser preference emulation was not performed. Cross-document transition support depends on the browser. Formal screen-reader, contrast, and user research validation remain production prerequisites. Backend tests were not run for this isolated design alternative.

UX refinement: viewport-height desktop/tablet sidebar and a mobile navigation side panel; clearly bounded apartment cards with status badges, grouped metrics and full-width actions. Moje analizy includes name/city search, status filtering and empty-result recovery. Updated grids use three columns at ≥1,440 px, two at 761–1,439 px, and one at ≤760 px, accounting for sidebar width.

Refinement verification: no page overflow or controls outside the viewport at 320, 390, 768, 1,024 or 1,440 px; desktop/tablet sidebar height matches the 900 px viewport. Searching `lodz` finds Łódź, an unmatched search shows the recovery action, and the clarification filter returns three cards. Escape from mobile navigation restores Menu focus. Mobile navigation successfully opens the separate home page. [Updated analysis collection preview](analyses-page.jpg).

Report navigation refinement supersedes the earlier summary-drawer interaction: property actions now link to `analysis.html?id=…` and display “Zobacz analizę” (or “Sprawdź postęp”). The example uses the same page. Full analytic rendering is intentionally deferred; the report UX contract defines the next design step.

Verified report navigation: a completed/partial property opens its own page with no dialog; a running property uses the same route with its running status; the example opens `id=p1`; an unknown ID shows the missing-analysis state. Return navigation works. The scaffold has no horizontal overflow at 320, 768 or 1,440 px; no browser errors observed. [Report scaffold preview](analysis-page.jpg).

## Light theme and branding verification — 2026-10-15

Verified in local headless Chrome: all four pages in both themes at 320, 390, 768, 1,024 and 1,440 px (40 combinations), with no horizontal overflow, missing images, failed asset responses or JavaScript errors. Light remains the first-visit default with an OS dark preference. Desktop/mobile controls switch themes; the explicit choice survives navigation and reloads. With localStorage blocked, the page still defaults to light and the toggle works within that page. Search (`lodz`), the clarification filter (3 results), city switching and Escape from mobile navigation also passed. All six V2 scripts pass `node --check`; `git diff --check` passes.

Desktop light/dark and mobile light previews were refreshed and visually inspected. Collection/report screenshots were refreshed; [market preview](market-page.jpg) was added. Pagination, table view, replacement cards, broader market content and formal accessibility testing remain pending. Backend tests were not run for this design-only update.


## Navigation and hover effects — 2026-10-15

Hover and keyboard focus use a clean border and a brief icon animation. Navigation and action controls keep fixed bounds; hover adds no glass surface, shadow, icon tile, reflection or translation. Active destinations retain a quiet tinted background. Supporting browsers still animate the workspace between pages with navigation anchored; unsupported browsers use normal navigation. Reduced motion disables decorative icon/page animation.


## Settings and document placeholders — 2026-10-15

- [Ustawienia](settings.html) is a navigation/layout placeholder. Profile changes, notifications and saving settings are not implemented. Theme switching remains functional in the shared navigation.
- [Regulamin](terms.html) is a placeholder for future approved terms; it is not an operative legal document.
- [Polityka prywatności](privacy.html) is a placeholder for the future approved privacy policy; it does not state current data-processing practices.

All three pages have independent URLs, active navigation states, shared branding and both themes. Ustawienia appears in primary navigation; legal documents are linked in the sidebar and mobile navigation. The sidebar theme switch now aligns with the other navigation rows. Its icon shows a moon for switching to dark and a sun for switching to light; text and icons update together. Mobile uses a compact icon button with the same accessible dark-mode toggle state. Final settings functionality and legal copy remain pending.

Verified in local Chrome across seven pages, both themes and 320/768/1,440 px widths (42 combinations): theme/navigation icon columns align; sun/moon icons update correctly; desktop and mobile links reach the placeholders; active destinations and help dialogs work; no horizontal overflow, missing assets or JavaScript errors. All V2 scripts pass syntax checks.


## Application dashboard and tools — 2026-10-15

Pulpit now covers the whole application. The sidebar/mobile menu contains Pulpit, Nowa analiza, Moje analizy, Rynek, Architekt wnętrz, Stwórz ogłoszenie and Ustawienia. “TWOJA PRZESTRZEŃ” has been removed from navigation. All analysis-start links now point to `new-analysis.html`; the dashboard has no URL submission form. Its recent analysis records and credit balance are explicitly fictional; it does not invent existing interior or listing projects.

### Analysis from a URL or manual inputs

`new-analysis.html` has keyboard-accessible tabs for an Otodom URL or an apartment form: name, city/district, area, rooms, purchase price, administrative fee, floor, condition, ownership and notes, plus local photo/floor-plan previews. Administrative fees are costs; an unknown fee stays unknown. Fractional ownership is blocked from this design flow. Manual preflight requires at least one image; photos can be added/removed. Up to 25 JPG/PNG/WebP files at 10 MB each are accepted. The URL route validates the URL structure only, not the listing content or SALE classification. Neither route calls a service, reserves credits or calculates financial results. Its preflight explicitly points to a separate fictional report, not a result derived from the entered data.

### Interior planning

`interior.html` accepts a room, style, goal and images, then displays an explicitly labeled example plan about layout, furniture and lighting. The advice is generic. Photo assessment, tailored design, generated renderings and cost estimates require a future integration and are not implemented here.

### Guided listing assistant

`create-listing.html` is a structured, non-chat flow: factual apartment inputs → photos and selected improvement areas → editable description draft and photo tips. It builds a local template from the user's facts, without an LLM or invented amenities. Users can edit and copy the draft; copy failure selects the text for manual copying. Selected photo issues produce tips about lighting, furniture/clutter and framing. A brightness slider changes the local image preview only; it does not export edited files. Automatic image assessment, image enhancement/export, AI copy generation and Otodom publishing are pending. Tips do not claim to be inferred from the uploaded images.

Image files are kept in memory as local object URLs in the current tab. They are not uploaded or saved to browser storage. New form data and drafts are not persisted, and leave/reload may discard them. Only the existing explicit theme preference is persisted. See [L-025](../../docs/LIMITATIONS.md#l-025--v2-manual-analysis-and-creative-tools-are-local-design-flows) for the integration boundary.


Verification for the application reorganization: local Chrome passed 60 page/theme/viewport combinations (10 pages × 2 themes × 320/768/1,440 px), with no overflow, asset failures or JavaScript errors. Confirmed all seven primary destinations, no navigation caption, dashboard without an analysis form, URL validation, keyboard tab selection, manual field preflight, image preview/removal, unknown administrative fee handling, fractional-ownership rejection, interior example, editable listing draft, selected photo tips, brightness preview and mobile navigation/Escape. User strings were checked as plain text; no external data requests occurred. Dashboard previews were refreshed. All scripts and `git diff --check` pass; backend tests were not run for these design artifacts.
