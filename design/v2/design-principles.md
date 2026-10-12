# V2 — Precision

2026-10-12 · Alternative direction, not a replacement for v1 or a shipped product.

## Design idea

An architectural, monochrome workspace: near-black canvas, restrained white typography, a persistent sidebar, precise edges and an original residential image. The [Starlink homepage](https://starlink.com/) was inspected as visual reference: bold sans-serif hierarchy, dark photographic scenes, sparse navigation and direct contrasting actions. RentMonitor adopts those composition principles while keeping property analysis, evidence and plain-language explanation at the center. No Starlink branding, imagery, wording or code is reused.

V1 is warm, editorial and rounded. V2 is spacious, typographic and architectural. It retains a viewport-height navigation rail, and replaces V1’s warm colors, serif headings and illustrated property thumbnails with dark, clearly bounded analysis cards. The signed-in home still prioritizes one real task rather than becoming a promotional landing page.

## Product rules carried forward

- Pulpit, Moje analizy and Rynek are separate pages with independent URLs and an active navigation state. “Wszystkie analizy” and “Sprawdź miasto” navigate to those destinations; neither opens an overlay.
- Home starts with one URL field, a clearly labeled action, three activity counts and three recent summaries. Each property opens a dedicated analysis page; drawers, dialogs and accordions reveal secondary data within that report. Critical missing-data warnings remain visible before interaction.
- Asking prices remain distinct from recorded transactions; administrative fees remain costs. Missing values are not zero. Numbers are fictional fixtures here; production displays canonical engine values without client-side finance.
- Credit cost is confirmed before submission. No request, reservation, payment or data transmission takes place in the prototype.
- Home is an analysis workspace, not a portfolio. Completed work does not imply a recommendation to buy.
- Do not hide essential units or risk labels in hover effects. Polish body copy remains sentence case; large display copy and navigation can use uppercase sparingly.

## Tokens

`tokens.css` is the editable source of truth. Component styles consume the tokens in `main-view.css`.

| Family | Tokens / usage |
|---|---|
| Backgrounds | `--canvas #08090A`, `--surface #111315`, raised `#1A1D20` |
| Text | Primary `#F5F6F7`, secondary `#A9AEB4`, subtle `#818891` |
| Dividers / controls | Structural `#353A40`; meaningful control boundaries `#7F8790` |
| Action | White `#F5F6F7` on black text `#0A0B0C`; hover `#DCE1E5` |
| Semantic signals | Sage `#B1D5BC` / green dark fill; amber `#EFCF98` / amber dark fill; error `#FFC0B4` |
| Type | Local Arial/Helvetica/system sans; no font download; headings 600–750, body 400 |
| Sizes | Home display 39–68 px; page headings 34–44 px; sections 23–28 px; body 14–15 px; compact labels 11–12 px |
| Spacing | 4 px base; 8, 12, 16, 24, 32, 48, 64 px |
| Geometry | Controls 3–4 px radius; overlays 6 px; analysis cards 8 px, distinct fill and a continuous border |
| Width | Content cap 1,280 px; three property columns at ≥1,440 px, two at 761–1,439 px, one at ≤760 px |

Dark color does not justify low contrast. The hero has a strong black scrim behind copy and controls. Caution colors are reinforced by icons and words. Native controls, visible focus, at least 44 px targets and mobile input text ≥16 px remain required.

## Motion system

Motion should orient attention and preserve continuity. Nothing loops, autoscrolls or parallax-scrolls. No animated currency counters or fake analysis progress.

| Interaction | Motion |
|---|---|
| Initial headline/content | 560 ms ease-out, opacity and 12 px vertical movement; 60 ms delay |
| Property summaries / filter results | 420 ms ease-out; first three stagger at 0 / 50 / 100 ms |
| Hover | 160–240 ms color change, ≤3 px elevation/arrow movement |
| Drawer opening | 320 ms ease-out, opacity and 28 px horizontal travel |
| Dialog opening | 320 ms, 12 px vertical movement and slight scale |
| Overlay closing | 180 ms opacity/travel before native close and focus restoration |
| Page navigation | Optional native cross-document view transition; short 120/240 ms fades, ordinary navigation fallback |

`--ease-out` is `cubic-bezier(.16,1,.3,1)`. `motion.js` handles overlay closing and preserves native focus behavior. `prefers-reduced-motion: reduce` disables CSS animation/transitions, smooth scroll and delayed closing. Essential content is present even if animation is unsupported. Cross-document transitions may be unavailable in a browser; navigation still works.

## Imagery and provenance

`architecture-hero.jpg` is an original AI-generated decorative image, not a source photograph, comparable property or listing evidence. The hero names that distinction. Generated using the built-in imagegen tool; no external image asset is fetched at runtime. No satellite/space visual is used: the imagery belongs to Polish residential property.

Generation prompt:

> Use case: photorealistic-natural. Asset type: cinematic architectural hero background for RentMonitor, a Polish apartment analysis app. Create an original wide 16:9 editorial architectural photograph at blue hour: a clean modern mid-rise Polish residential apartment building, stone and concrete facade, glass balconies, subtle warm windows, close low-angle view. Building concentrated on the right half; left half has deep charcoal sky and quiet negative space for UI text. Sophisticated, minimal, atmospheric, realistic materials and restrained near-monochrome charcoal palette with tiny warm window highlights. No humans, no visible signs, no text, no logos, no satellites, no stars, no branding, no watermark. Not a specific real address or listing. High-end architectural photography, natural lens, balanced perspective.

## Implementation and review

All files stay in `design/v2/`. Existing v1 artifacts and production code remain separate. Reused interaction logic and fictional fixtures come from RentMonitor's own v1 prototype. No new dependency, backend contract, entitlement, price or feature commitment is introduced.

Before production: user-task testing, formal screen-reader and contrast review, actual translated/API content and approved commercial/legal copy. V2 is a proposal to compare with v1; visual polish alone does not establish better usability.

## Navigation and analysis collection refinement

Desktop/tablet navigation is a sticky 232 px sidebar (210 px on smaller tablets), limited to the viewport height with independent overflow and account/help at the bottom. On mobile, a clearly labeled Menu button opens a native side dialog with the same page destinations. Escape closes it and restores focus to Menu. Primary navigation still uses separate URLs rather than opening content in overlays.

Each analysis is one bounded object: dark raised surface, continuous visible border, 8 px radius, grouped identity/status, a separated numeric section and a full-width “Zobacz analizę” page link. Borders and spacing distinguish adjacent entries and rows even in grayscale. Important missing-data text receives a caution surface within its own card. A search field matches apartment names or cities (including unaccented Polish input), combines with the status filter, announces the result count and provides an empty-result recovery action. No property photos or financial values are fabricated beyond the explicitly labeled fixtures.

## Full analysis is a page

“Zobacz analizę”, “Sprawdź postęp” and the example open a dedicated report URL, not a property-summary drawer. The current page is a navigation scaffold; the full data-rich report will show a qualified overview and next step first, with details revealed through contextual evidence drawers, focused dialogs and section accordions. See [analysis-page-ux.md](analysis-page-ux.md) for the report hierarchy, disclosure policy, financial semantics, states and acceptance criteria.
