# Rynek UX review (RM-439)

Reviewed against the commit that carries this file. Gate: `frontend/e2e/ux.spec.ts` (lane `ux`, `pnpm ux`), run after
the functional lanes. Screenshots are written to the gitignored `frontend/ux-out/`; the committed evidence is the
visual baselines `frontend/e2e/__screenshots__/visual-*/market-*.png` (pinned Linux image, `pnpm visual`).

## What the gate checks

States: populated, empty, loading, restricted, error (explorer, map with preview, comparison, place, district, GUS
ranking and profile). Viewports 390, 768 and 1280 px, light and dark: 19 states x 3 x 2 = 114 runs, plus two keyboard
walkthroughs (explorer; comparison and ranking). 116 tests passed on the final run.

| Criterion | How it is asserted |
|---|---|
| Clipping and horizontal overflow | no element wider than the viewport outside a scroll container; page does not scroll sideways |
| Overlap | map labels do not overlap each other; the preview does not cover the map controls; chart tick labels do not overlap |
| Touch targets | every button, link, input, summary at least 44 px (24 px floor for axe `target-size`, which also fails a marker partly under another control) |
| Wrapped labels | no heading, label or legend wrapped to one word per line |
| Chart readability | axis text at least 11 px; title, axes, legend and table equivalent present |
| Section separation | heading-to-content and section gaps are shared spacing tokens |
| Accessibility | axe clean in each state and theme; keyboard walkthrough shows a visible focus ring on every stop and Escape closes the preview |
| Visual regression | 16 Rynek pictures x light/dark x desktop/mobile |

## Findings fixed because of the gate

- "Szczegóły wskaźnika" links were 21 px high: now `min-height: 2rem` inline-flex.
- Preview buttons were "small" (36 px): now full size.
- Markers could sit under the zoom controls or the open preview (axe `target-size`): such markers are not drawn
  until the map moves or the preview closes; selecting a place pans it clear of the sheet or card.
- Neighbouring markers closer than 44 px are merged into one cluster; label collision boxes enlarged.
- Opening a preview moves focus into it; closing it returns focus to the marker.

## Visual inspection notes (screenshots opened and read)

- Desktop map with preview: marker symbols distinct (filled circle = median, diamond = withheld, dashed = no
  data), city labels legible, preview card clear of the controls.
- Place page: cards, median chart with gaps, composition bars, district bars, "how to read" section; a vertical
  rhythm consistent with tokens.
- GUS ranking: score, rank, cohort, component table with weights and contributions, higher-is-better stated.
- Known weakness: on a 390 px phone the preview sheet covers most of the map frame; the selected place is panned
  into the visible strip, but the map is small while a preview is open. Closing the preview restores it.
- Not measured: real devices, Firefox/WebKit visual rendering (baselines are Chromium only).
