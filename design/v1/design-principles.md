# Design principles

2026-10-12 · Proposed foundation for the production UI.

## 1. Design for a person making a purchase decision

The primary user is an ordinary person considering a Polish apartment for rental income. They may know property prices without knowing IRR, MOIC or cash-on-cash. Every view answers one question and makes the next step obvious. Home answers: “What should I check, and where did I leave off?” It is an analysis workspace, not a portfolio tracker: saved listings are not owned assets.

The visual direction is **quiet confidence**: warm paper, precise ink, restrained terracotta, generous whitespace and an editorial heading. Beauty comes from typography, alignment and a clear hierarchy. Avoid trading-terminal chrome, decorative charts, glass effects, flashy AI badges and oversized metric walls.

## 2. Start small; reveal depth deliberately

Use three information layers:

| Layer | What the user sees | Example |
|---|---|---|
| Glance | One conclusion or status, key fact, next action | “Do wyjaśnienia · brak opłaty administracyjnej” |
| Understand | Drawer or expanded section with reasons and relevant numbers | Rent range, owner costs, missing evidence |
| Investigate | Full report/evidence view after another explicit action | Comparables, scenarios, yearly cash flow, formulas |

Home shows at most three recent properties and three activity counters. The complete list is reached intentionally on the separate “Moje analizy” page. Detailed metrics, sources, filters, account usage and assumptions open on interaction. Do not hide essential identity, units, material risks, missing inputs, billing cost or error recovery. Progressive disclosure reduces clutter; it must not obscure qualifications.

## 3. Give one action visual priority

“Sprawdź mieszkanie” is the home action. Keep the URL input beside it on desktop and above it on mobile. Say what the person receives: rental potential, costs and purchase context. No multi-field onboarding, compulsory city selection or financing wizard before a first analysis. Advanced assumptions belong after the initial result, with engine-supported defaults.

Before a paid/credit-consuming submission, show cost, balance and whether the result will use limited data. Preserve the link after sign-in, paywall or recoverable failure. An unsupported rental listing or ownership share receives a clear explanation with the backend-defined credit outcome.

## 4. Show meaning before financial vocabulary

Use “Cena z ogłoszenia”, “Najem dla właściciela”, “Koszty utrzymania”, “Budżet remontu” and “Cena spełniająca Twój cel”. Introduce “Max Bid” or IRR only in the relevant detail with a plain-language definition. Do not equate an investment grade to data confidence. Do not label one simulated return “pewny zysk”.

Use Polish formatting: `425 000 zł`, `2 400–2 700 zł / mies.`, `5,2%`, `42 m²`. Prefer bounded estimates over false decimal precision. Unknown is “Brak danych”, never zero. A long-term estimate always names its horizon, assumptions and inclusion of sale proceeds in its detail.

## 5. Keep evidence and uncertainty honest

Asking prices and recorded transaction prices are separate, explicitly labeled series. Administrative fees are operating costs, not rent income. Never sum saved-property returns into “your wealth”. Never synthesize money, counts of successful results or confidence on the frontend from unrelated fields.

Dates and source basis travel with market values. Stale, thin or partial evidence appears near the affected number. A result affected by placeholder CAPEX prices is labeled “Wynik wstępny” and cannot receive an unqualified ready/positive status. A low-quality result may show an estimate only when the engine supplies one, with its qualification; otherwise it shows no number. Essential caveats survive the compact view.

## 6. Choose the smallest suitable interaction

- Tooltip: a short, optional definition; never the only place for risk or essential instructions. Support focus and tap, not hover alone.
- Inline expansion: a small explanation in the current context.
- Drawer: inspect one property or its evidence without losing home context. On mobile, use the full width and allow vertical scrolling.
- Dialog: confirm a credit cost, handle a blocking condition or explain a bounded concept. Never nest dialogs.
- Dedicated page: lengthy reports, comparison, market exploration and account management. “Moje analizy” and “Wszystkie analizy” navigate to a dedicated analyses page. “Sprawdź miasto” and “Rynek” navigate to the separate market page; source details expand within that page. Full reports, comparison and account pages remain later work.

Closing an overlay restores focus to its trigger and preserves filters/scroll. Native dialog behavior supplies focus containment and Escape. A blocked user gets a specific next action; a toast is insufficient for submission failure.

## 7. Make the navigation predictable

Core navigation: **Pulpit · Moje analizy · Rynek**. Every primary navigation item opens a separate page with its own URL and active navigation state, supporting browser Back/Forward, reload and direct links. Collections and market exploration never open as dialogs or drawers. Drawers are reserved for contextual property summaries/evidence; dialogs for bounded help, account previews, confirmations and blockers. Saved properties and comparison are contextual actions in analyses, not extra home widgets. Account and help occupy the secondary area. Redesign, seller questions and advanced valuation are discovered within the relevant property if enabled, not permanent top-level navigation.

Unavailable modules are omitted in production through entitlements/feature flags. A preview may show their proposed placement, clearly separating design intent from launch commitment. Do not sell an unavailable feature with a functioning-looking CTA.

## 8. Treat all states as designed experiences

First use: empty activity counts are replaced by a short explanation and a sample report action; keep the same primary task. Loading: reserve layout and name the work; don't invent percentage completion. Running analysis: allow navigation away and recover progress after reconnection. Partial result: show what is usable and what is missing. Source unavailable: preserve the URL and show a supplied retry time if known. No credits: explain the limit before submission and offer the approved access options. Failure: show the backend credit outcome and a clear recovery path.

Do not charge a second time for opening an existing report. Duplicate submission opens the active analysis. Credit release/capture follows the server, never a client-side timer.

## 9. Visual system

| Token | Direction |
|---|---|
| Canvas / surface | Warm off-white `#F6F5F1` / white `#FFFFFF` |
| Primary text / secondary | Ink `#202C35` / slate `#58646B` |
| Action / hover | Deep terracotta `#A6412D` / `#893422`, white text |
| Positive / caution | Forest `#285845` on `#EDF4EF`; ochre `#805321` on `#FAF0DE` |
| Divider / tinted surface | `#E3E5DF` / warm blush `#F0E7DE` |
| Type | System sans for UI; Georgia for the main editorial headline; no font download required |
| Type sizes | Body 15–16 px; secondary 13–14 px; section 21–24 px; main heading 40–50 px desktop / 32 px mobile |
| Spacing | 4 px base; 8, 12, 16, 24, 32, 48, 64 px steps |
| Shape | 20–24 px hero/panels, 12–16 px summary cards, 8–12 px controls; pill only for statuses |
| Shadows | Subtle overlay elevation; structural panels mostly rely on spacing and hairlines |
| Icons | Consistent 20 px line icons; always pair action icons with visible labels or accessible names |

Prototype tokens are defined in `main-view.css`. Currency uses tabular numerals. Property illustrations are original abstract architectural placeholders, not listing evidence. Real production photos require the agreed storage, attribution and privacy policy.

## 10. Accessibility is part of elegance

Aim for WCAG 2.2 AA: 4.5:1 normal text, 3:1 large text and meaningful control boundaries. Use at least 44 px interactive targets, visible keyboard focus, explicit input labels and useful errors tied to fields. Never use color alone for status. Respect reduced motion. Do not truncate an address or make essential details hover-only. Announce completed actions and errors, not every animation.

Desktop uses a sticky, viewport-height 220 px navigation rail and a centered content area capped at 1,180 px. The rail stays visible while the main page scrolls; it can scroll independently on short screens. Property cards use three columns above 1,200 px, two columns from 761–1,200 px, and one column at 760 px and below. Below 1,050 px simplify hero artwork; at 760 px and below reflow navigation into the page header. Design down to 320 px without horizontal scrolling. Overlays can scroll vertically; the underlying page does not scroll while one is open. Inputs use 16 px on mobile.

## 11. Evaluate the design through tasks

Test with 5–8 people who are not property professionals before UI implementation is treated as settled. Ask them to check a sale listing, locate a previous result, explain a rent estimate, identify a missing input, and explain whether the shown price is asking or recorded. Target ≥80% unassisted completion; everyone must notice material missing data and understand credit cost before submission. Measure hesitation, misinterpretation and recovery as well as completion speed. Aesthetic approval alone is insufficient.

Home succeeds when the person can name the next action within five seconds and understand the difference between an estimate and a fact. These are proposed acceptance criteria; no user testing has been performed yet.
