# renti: an unstyled foundation with a defined visual system

2026-10-15 · Proposed frontend implementation approach · Read with [implementation-guide.md](implementation-guide.md).

## What “styleless” means here

Use an **unstyled/headless behavior layer**, then apply one small renti visual system. It does not mean removing design, shipping raw controls, or making every page choose its own look. The goal is to reuse keyboard behavior, semantics, state and focus management while retaining V2's identity.

Recommended starting point: native elements for ordinary links, buttons, inputs and selects; **Base UI** for dialogs, tabs, comboboxes, popovers and other complex controls. Its components are unstyled and can be composed with CSS Modules; verify the API of each installed component rather than guessing props ([quick start](https://base-ui.com/react/overview/quick-start), [styling](https://base-ui.com/react/handbook/styling)). This is a proposed choice, not an installed package.

Consider React Aria or existing Radix primitives instead if the implementation already depends on them or a concrete control requirement makes them a better fit. Decide once in the foundation issue. Do not mix primitive libraries for the same control or adopt a large themed kit merely to restyle every part. A primitive library helps with accessibility; correct composition and application-level testing are still required.

## Four layers

| Layer | Owns | Does not own |
|---|---|---|
| Foundations | Reset, semantic tokens, typography, spacing, focus, theme, motion | Page layouts or server data |
| UI primitives | Button, LinkButton, Field, Dialog, Tabs, Status, Skeleton | API calls, credits, property meaning |
| Product patterns | AnalysisStatus, MoneyValue, EvidencePanel, PhotoPicker, CollectionToolbar | Generic interaction engines or financial calculation |
| Feature screens | Route state, orchestration, canonical data, complete journeys | A private duplicate of Button or theme tokens |

Prefer composition over a universal configurable component. Add a variant when two real uses need it. Avoid both one-off copies and a speculative “EnterpriseDataEverything” abstraction. A component is ready to share when its semantics, states and visual responsibilities are clear.

## Tokens and styling

Start from [tokens.css](tokens.css), but consolidate the prototype's repeated overrides into clean component CSS. Do not paste the whole minified stylesheet into production or preserve its historical cascade as an architectural pattern.

Suggested semantic groups:

- Surfaces: `--canvas`, `--surface`, `--surface-hover`, `--surface-raised`.
- Text: `--ink`, `--muted`, `--subtle`, inverse text and link/focus colors where needed.
- Boundaries: structural border, control border, hover border and selected background/border.
- Actions: primary fill/text/hover; disabled and danger states with explicit contrast.
- Status: success/warning/error/info text, surface and border; status is also conveyed in words/icons.
- Geometry: spacing scale, control heights, radius, content width, sidebar width, overlay layer scale.
- Motion: duration/easing tokens; one reduced-motion policy.

Use color literals in the token source and documented asset-specific exceptions only. Semantic tokens should describe purpose, not `green-thing-2`. Keep status palette separate from brand accent. Add tokens when a shared semantic need exists; do not create one token for every pixel. Use CSS custom properties globally and CSS Modules for component selectors. Avoid selectors coupled to deep page ancestry, `nth-child` semantics or incidental DOM order.

Keep global CSS limited to reset, default text, focus, theme, accessibility utilities and deliberate browser fixes. Use cascade layers only with a documented order and an understanding that unlayered rules outrank layered rules. Prefer a small obvious stylesheet to a specificity contest. Avoid routine `!important`; reduced-motion overrides are an explicit exception.

TypeScript should not own a second palette. Expose only values needed by JavaScript through a deliberate bridge; charts should consume semantic colors. Use CSS for responsive layout, not a competing React breakpoint system.

### Initial visual constraints

- Mineral light canvas `#F5F7F4`, white surface, forest text `#182C28`; dark counterparts follow current tokens.
- Local/system sans-serif for UI. Outlined brand assets do not require Google Fonts requests.
- 4 px spacing base; common gaps 8/12/16/24/32/48 px. Tokenize recurring sizes rather than enforce a rigid grid on content.
- Clear modest radii; no redesign into large pill controls, frosted tiles or decorative dashboard gradients.
- Shared shell content cap starts at 1,280 px. The current 232/210 px rail and 760 px mobile boundary are useful references, not device categories to hardcode everywhere.
- Body/form text should remain readable; tiny prototype captions are not a production readability standard. Inputs on mobile start at 16 px; meaningful controls generally target 44 px hit areas.
- Hover: stable 1 px border (reserve transparent border at rest), no padding/size changes, no whole-control movement. Only the icon briefly animates; keyboard focus gets equivalent feedback plus a visible outline.

## Core component inventory and contracts

| Component | Required behavior / states |
|---|---|
| Button / IconButton | Native button, explicit type, accessible name, default/hover/focus/pressed/disabled/busy/danger; stable width for busy state |
| LinkButton / NavItem | Real link with destination; modified clicks/back/history work; active route indicated with `aria-current`; no nested button/link |
| ThemeControl | Light default, explicit persistence, safe storage fallback, synchronized label/icon/state in desktop and mobile |
| Field / FormSection | Label, hint, error associations, required semantics, stable IDs, grouped fields, server error integration |
| Input / Textarea / Select | Native where possible; touched/invalid/disabled/read-only and long/localized values |
| Tabs | Correct tab/panel association, roving focus, arrow/Home/End keys, selected state; keyboard focus is distinct from selection |
| Dialog / Sheet | Label, optional description, portal/layering, initial focus, trapped focus when modal, Escape, backdrop policy and focus restoration |
| InlineNotice / Status | Semantic status text, appropriate live-region behavior, optional action, no color-only meaning |
| EmptyState / ErrorState | Explanation and next action; loading must not appear as empty |
| Skeleton / Pending | Reserve meaningful layout; no fabricated numbers; respect reduced motion |
| Pagination / ViewSwitcher | URL state, keyboard labels, disabled boundaries, consistent filters and result context |
| Table | Native table semantics, associated headers, sort state, horizontal overflow inside its own region; sticky elements cannot cover focused cells |
| PhotoPicker / PhotoTile | Accessible file input, limits, preview/decoding/error/removal states, progress/cancel when real uploads exist |
| Disclosure / EvidencePanel | Important warnings visible without opening; named trigger, expanded state and preserved reading order |
| CopyAction | Success/error announcement; graceful manual-copy fallback; no false “copied” toast |

Forward refs/DOM props only when meaningful and type them. Expose variants such as `primary`, `secondary`, `danger` and sizes only as real product needs emerge. Do not expose arbitrary color strings or fifty booleans. Prefer a separate `LinkButton` to an unrestricted polymorphic Button that can accidentally lose navigation semantics.

For compound primitives, keep their structural requirements intact. Follow documented state/data attributes for styling, not assumed internal DOM. Test portals, focus restoration and stacking against the app shell and mobile browser chrome. Keep portals inside a theme-aware root or ensure inherited tokens are available at their target.

## State ownership

- UI component: open/focus/selected presentation state when not controlled by a feature.
- Feature form: editing values, touched fields, validation and unsaved changes.
- Router URL: selected tab where useful, filters, sort, view mode and page/cursor state that must survive back/refresh.
- Query cache: fetched server state; never duplicate it in a page-wide global store.
- Server: authorization, entitlements, credit ledger, financial results, job truth and persistent projects.

Choose controlled vs uncontrolled behavior intentionally. Do not make a wrapper both controlled and uncontrolled through accidental `undefined` props. File previews should not outlive their owning feature/session. Reset state deliberately when the underlying resource changes.

## Theme and responsive shell

Apply the initial theme before the first paint with a small bootstrap compatible with the chosen CSP. Default to light; accept only known stored values; catch storage access failures. No inline-script CSP exception should be added casually: choose an external bootstrap, hash or approved nonce policy.

The same navigation registry drives desktop and mobile destinations. Derive current location from the router, not click state. Handle nested reports/new-analysis paths deliberately so the wrong item does not appear active. Primary links, legal links, theme and account controls must remain reachable on short screens and at 200% zoom.

On route change update the document title and move focus to a meaningful page heading/main region when appropriate. Native navigation behavior in the prototype is not automatically reproduced by an SPA. Close the mobile sheet after navigation. Ensure the destination receives focus rather than a closed or hidden menu trigger.

Use optional router-compatible View Transitions only after basic navigation works. The prototype's cross-document transition CSS cannot simply be pasted into a single-document router and assumed to work. Motion must not affect routing, history, access or focus correctness.

## Accessibility acceptance criteria

Target WCAG 2.2 AA and verify the actual implementation, not just the component library. [W3C quick reference](https://www.w3.org/WAI/WCAG22/quickref/) is the source for the standard; the 44 px touch target here is a product usability target, not a claim that every WCAG AA control must be 44 px.

- Landmarks, logical headings, skip link, Polish document language and meaningful route titles.
- Complete keyboard journey: navigation, tabs, forms, upload/removal, dialogs, sorting, pagination and copy.
- Visible unobscured focus; restoring focus must not land on removed/disabled/hidden elements.
- Text contrast at least 4.5:1 for normal text; large text and meaningful non-text controls meet their applicable 3:1 requirements. Test hover, disabled context, charts and both themes.
- Accessible names for icon-only actions; decorative icons hidden from assistive technology. Tooltip alone does not repair a missing name.
- Errors described in text and connected to fields. Announce results/state changes sparingly; do not announce every SSE event.
- Reflow without whole-page horizontal scrolling at 320 CSS px, 200% text zoom and browser zoom. Data tables may have a labeled local scrolling region.
- Reduced-motion disables decorative animation. No required content/function exists only on hover; touch gets an equivalent action.
- Verify with real keyboard and at least one supported screen reader/browser combination. Automated axe checks do not establish compliance by themselves.

## Component catalog as an implementation tool

Start the catalog with the first shared primitives (#270), not in the foundation scaffold. Use Storybook for a small living catalog, with mocked network states where relevant. This gives Claude a reliable place to inspect variants before building a page. Each shared component/pattern should show realistic Polish labels and long values, not just “Button” and lorem ipsum.

Minimum examples: default, keyboard focus, disabled/busy, invalid/error, empty/loading and dark theme as applicable. Add RTL only if language scope requires it, but do not hardcode avoidable directional assumptions. Include a narrow viewport and 200% zoom review of dense patterns.

Name stories by user state (`InsufficientCredits`, `UnknownAdminFee`, `Reconnecting`, `EmptyFilteredList`), not by implementation detail. Use interaction/accessibility checks for important composition. [Storybook accessibility testing](https://storybook.js.org/docs/writing-tests/accessibility-testing) supports automated checks; still run route-level and manual checks.

When updating a shared component: update its examples, assess affected routes, run focused interaction/visual checks and explain the intended difference. Do not automatically accept a screenshot diff because code compiled. Keep a small reviewed baseline set in deterministic CI conditions.

## Avoid these prototype-to-production mistakes

- Copying repeated HTML navigation into every React route.
- Keeping all fixtures, dialogs, financial display and page behavior in one global script.
- Replacing a proper collection contract with a sliced in-memory array while calling it pagination.
- Shipping incomplete report sections or legal placeholders as finished content.
- Turning prototype limits or generic advice into undocumented server/business rules.
- Reintroducing rejected visual experiments because a component library demo uses them.
- Building a full design-system package/monorepo before a few reusable controls and the first journey work.
