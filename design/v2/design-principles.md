# V2 — Precision

Updated 2026-10-15 · Owner-selected starting point for the frontend; not a shipped application.

## Design idea

An architectural, monochrome workspace: light mineral canvas by default, forest typography, an optional near-black theme, a persistent sidebar, precise edges and an original residential image. The [Starlink homepage](https://starlink.com/) was inspected as visual reference: bold sans-serif hierarchy, dark photographic scenes, sparse navigation and direct contrasting actions. renti adopts those composition principles while keeping property analysis, evidence and plain-language explanation at the center. No Starlink branding, imagery, wording or code is reused.

V1 is warm, editorial and rounded. V2 is spacious, typographic and architectural. It retains a viewport-height navigation rail, and replaces V1’s warm colors, serif headings and illustrated property thumbnails with clearly bounded analysis cards (temporary placeholders to replace). The signed-in home orients the user across the application; each tool has its own task-focused workspace.

## Product rules carried forward

- Pulpit, Moje analizy and Rynek are separate pages with independent URLs and an active navigation state. “Wszystkie analizy” and “Sprawdź miasto” navigate to those destinations; neither opens an overlay.
- Home is the application dashboard: entry points for analysis, interior planning and listing preparation, recent work and market context. Analysis starts on a separate page with URL/manual-input tabs. Each property opens a dedicated analysis page; drawers, dialogs and accordions reveal secondary data within that report. Critical missing-data warnings remain visible before interaction.
- Asking prices remain distinct from recorded transactions; administrative fees remain costs. Missing values are not zero. Numbers are fictional fixtures here; production displays canonical engine values without client-side finance.
- Credit cost is confirmed before submission. No request, reservation, payment or data transmission takes place in the prototype.
- Home is the dashboard for the entire application, not an investment portfolio. Completed work does not imply a recommendation to buy.
- Do not hide essential units or risk labels in hover effects. Polish body copy remains sentence case; large display copy and navigation can use uppercase sparingly.

## Tokens

`tokens.css` is the editable source of truth. Component styles consume the tokens in `main-view.css`.

| Family | Tokens / usage |
|---|---|
| Backgrounds | Light: `--canvas #F5F7F4`, `--surface #FFFFFF`, raised `#E5EDE7`; dark palette under `[data-theme="dark"]` |
| Text | Light: primary `#182C28`, secondary `#52625C`, subtle `#65746C`; dark: pale text |
| Dividers / controls | Light: structural `#D1DBD4`, controls `#7A8B80`; dark: `#353A40` / `#7F8790` |
| Action | Light: forest `#182C28` with white text; dark: white with black text |
| Semantic signals | Light: green `#24643E`, amber `#775016`, error `#A12C24`; dark uses pale semantic colors on dark fills |
| Type | Local Arial/Helvetica/system sans; no font download; headings 600–750, body 400 |
| Sizes | Home display 39–68 px; page headings 34–44 px; sections 23–28 px; body 14–15 px; compact labels 11–12 px |
| Spacing | 4 px base; 8, 12, 16, 24, 32, 48, 64 px |
| Geometry | Controls 3–4 px radius; overlays 6 px; analysis cards 8 px, distinct fill and a continuous border |
| Width | Content cap 1,280 px; three property columns at ≥1,440 px, two at 761–1,439 px, one at ≤760 px |

Dark color does not justify low contrast. The hero uses a pale scrim in light mode and a black scrim in dark mode behind copy and controls. Caution colors are reinforced by icons and words. Native controls, visible focus, at least 44 px targets and mobile input text ≥16 px remain required.

## Motion system

Motion should orient attention and preserve continuity. Nothing loops, autoscrolls or parallax-scrolls. No animated currency counters or fake analysis progress.

| Interaction | Motion |
|---|---|
| Initial headline/content | 560 ms ease-out, opacity and 12 px vertical movement; 60 ms delay |
| Property summaries / filter results | 420 ms ease-out; first three stagger at 0 / 50 / 100 ms |
| Hover / keyboard focus | 180 ms border transition inside fixed navigation/button bounds; one-shot 560 ms icon animation (arrows travel ≤5 px) |
| Drawer opening | 320 ms ease-out, opacity and 28 px horizontal travel |
| Dialog opening | 320 ms, 12 px vertical movement and slight scale |
| Overlay closing | 180 ms opacity/travel before native close and focus restoration |
| Page navigation | Optional native cross-document transition: sidebar stays anchored, active indicator moves in 360 ms, workspace fades out/up in 180 ms and enters from below in 420 ms; ordinary navigation fallback |

`--ease-out` is `cubic-bezier(.16,1,.3,1)`. `motion.js` handles overlay closing and preserves native focus behavior. `prefers-reduced-motion: reduce` disables CSS animation/transitions, smooth scroll and delayed closing. Essential content is present even if animation is unsupported. Cross-document transitions may be unavailable in a browser; navigation still works.

## Imagery and provenance

`architecture-hero.jpg` is an original AI-generated decorative image, not a source photograph, comparable property or listing evidence. The hero names that distinction. Generated using the built-in imagegen tool; no external image asset is fetched at runtime. No satellite/space visual is used: the imagery belongs to Polish residential property.

Generation prompt:

> Use case: photorealistic-natural. Asset type: cinematic architectural hero background for RentMonitor, a Polish apartment analysis app. Create an original wide 16:9 editorial architectural photograph at blue hour: a clean modern mid-rise Polish residential apartment building, stone and concrete facade, glass balconies, subtle warm windows, close low-angle view. Building concentrated on the right half; left half has deep charcoal sky and quiet negative space for UI text. Sophisticated, minimal, atmospheric, realistic materials and restrained near-monochrome charcoal palette with tiny warm window highlights. No humans, no visible signs, no text, no logos, no satellites, no stars, no branding, no watermark. Not a specific real address or listing. High-end architectural photography, natural lens, balanced perspective.

## Implementation and review

All files stay in `design/v2/`. Existing v1 artifacts and production code remain separate. Reused interaction logic and fictional fixtures come from RentMonitor's own v1 prototype. No new dependency, backend contract, entitlement, price or feature commitment is introduced.

Before production: user-task testing, formal screen-reader and contrast review, actual translated/API content and approved commercial/legal copy. V2 is the frontend starting point; its principles are defined, while incomplete layouts may change with real content and usability review. Visual polish alone does not establish better usability.

## Navigation and analysis collection refinement

Desktop/tablet navigation is a sticky 232 px sidebar (210 px on smaller tablets), limited to the viewport height with independent overflow and account/help at the bottom. On mobile, a clearly labeled Menu button opens a native side dialog with the same page destinations. Escape closes it and restores focus to Menu. Primary navigation still uses separate URLs rather than opening content in overlays.

Each analysis is one bounded object: a theme-appropriate raised surface, continuous visible border, 8 px radius, grouped identity/status, a separated numeric section and a full-width “Zobacz analizę” page link. Borders and spacing distinguish adjacent entries and rows even in grayscale. Important missing-data text receives a caution surface within its own card. A search field matches apartment names or cities (including unaccented Polish input), combines with the status filter, announces the result count and provides an empty-result recovery action. No property photos or financial values are fabricated beyond the explicitly labeled fixtures.

## Full analysis is a page

“Zobacz analizę”, “Sprawdź postęp” and the example open a dedicated report URL, not a property-summary drawer. The current page is a navigation scaffold; the full data-rich report will show a qualified overview and next step first, with details revealed through contextual evidence drawers, focused dialogs and section accordions. See [analysis-page-ux.md](analysis-page-ux.md) for the report hierarchy, disclosure policy, financial semantics, states and acceptance criteria.

## renti branding and themes

Company name: **renti**. Domain and lockup: **renti.tech**. The owner-supplied mark uses a Goldman Bold negative R in a square, forest `#182C28`, and a flush emerald `#10B981` corner dot. The wordmark uses Inter 750 and JetBrains Mono 400. SVG assets outline the letters so logos and favicon do not depend on external fonts. The light logo uses the supplied colors; the dark variant uses pale ink and keeps the emerald dot. The favicon has a pale backing so its negative R remains readable on browser chrome. Font licenses are included alongside the assets.

Light is the default, including for visitors whose system prefers dark. A visible keyboard-accessible toggle supports an explicit dark choice, saved across pages and reloads when browser storage is available. Theme tokens cover the hero, forms, navigation, cards, dialogs, status badges and market summary. Keep readable contrast in both appearances; formal accessibility validation remains pending.

## Known design gaps

**Moje analizy cards are placeholders and their design is inadequate. They will be replaced.** The collection currently lacks proper pagination and a table-view switch. Neither a filtered twelve-fixture grid nor the current card treatment is an approved scalable collection design. Add pagination and a table-view option in the replacement design.

**Rynek is a placeholder to avoid a blank page.** The project has substantially more market data than the city/rent sample presents; the current view omits that breadth. Plan the broader data presentation separately rather than treating this sample as the target product scope. See [V2 README](README.md#placeholder-views--not-approved-designs) and [L-024](../../docs/LIMITATIONS.md#l-024--v2-analysis-collection-and-market-views-are-placeholders).

## Interactive motion refinement — 2026-10-15

Hover styling is limited to a clean border and a brief icon animation, with matching keyboard focus and a visible focus outline. No glass fill, shadow, icon tile, reflection or hover translation is used. Controls keep fixed bounds and text positions. Active navigation retains a quiet tinted background distinct from hover. Primary actions keep their solid fill; secondary actions remain transparent.

Icons use one-shot home, file, market and arrow motions. Reduced motion disables decorative animations. Native page transitions keep navigation anchored and animate workspace content; ordinary links preserve browser history and provide a fallback.


## Application information architecture — 2026-10-15

Pulpit is the app-wide dashboard. Nowa analiza is the analysis entry for an Otodom link or user-supplied apartment facts and photos. Moje analizy remains the collection; individual results keep separate report URLs. Architekt wnętrz owns room, style, goal and image inputs. Stwórz ogłoszenie is a guided assistant without chat: facts, photos, editable description and photo-improvement tips. Settings and legal documents keep their own destinations. The former navigation caption has been removed.

Manual fields keep unknown costs unknown and reject fractional ownership before preview. Uploaded images are local previews only. Interior recommendations and photo tips are labeled examples or generic guidance. A listing draft uses only supplied facts and visibly asks for missing information. No AI assessment, generated image, financial result, upload, publication or completed backend job is implied. The brightness control changes display only. Production scope and integrations remain separate decisions; see README and L-025.


## Implementation handoff

Use [implementation-guide.md](implementation-guide.md) for route maturity, contracts and architecture, [design-system.md](design-system.md) for the proposed headless component system, [frontend-tooling.md](frontend-tooling.md) for environment/quality gates and [implementation-checklist.md](implementation-checklist.md) for delivery slices and a Claude task prompt. These documents extend the design principles without converting placeholders into completed features or changing the current repository phase.
