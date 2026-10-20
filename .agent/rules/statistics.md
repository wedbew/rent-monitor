# Rule: statistics are shown so they can be interpreted (`frontend/`, RM-439)

Decision of record: owner brief of 2026-10-20 (item 8) after the first Rynek charts showed numbers without their
meaning. It applies to every chart, metric card, ranking and table that shows a statistic, in `frontend/` and in
any exported view. `rules/frontend.md` §7 (copy and numbers from one place) still holds; this rule says what a
statistic must carry.

## 1. The five answers (every metric and chart)

Every figure answers these before it is shown, in the figure itself (heading, subtitle, caption or `Meta`):

1. **What is measured?** A plain Polish name, not a field name ("Mediana ceny ofertowej najmu za m²").
2. **Unit and geographic area.** The unit (`zł/m²`, `osób na 1000 mieszkańców`) and the area it describes,
   with its territorial level when it can be misread (gmina, powiat, "dzielnica wg Otodom"). A proxy value names
   the unit actually measured.
3. **Period.** The reading date, the window ("ostatnie 90 dni") or the statistical year. A series shows its
   first and last date.
4. **Source and coverage.** The source (Otodom ogłoszenia, GUS BDL) and the sample or coverage: number of
   offers, number of units ranked, share of data present.
5. **How to interpret it.** One sentence: what a higher value means, what the figure is *not* (asking rent is not
   a signed rent), and any limit.

In code this is the typed `StatMeta` (`frontend/charts/meta.ts`): `MetricCard` and `ChartFigure` refuse to render
without all five. Do not bypass it with a bare `<h3>` and a number.

## 2. Terms in plain Polish, once

- **Mediana**: the middle value; half the offers are cheaper, half dearer. Prefer it to an average.
- **Kwartyle (P25 i P75)**: a quarter of offers are below P25, a quarter above P75; the band between them holds
  the middle half. A wide band means prices differ a lot.
- **Wynik (0 do 100)**, **pozycja**, **percentyl**: say what 100 is and which end is favourable. "Wyżej =
  korzystniej" or "Niżej = korzystniej" is stated next to every ranked value (the registry's direction decides).
- A rank always shows its **denominator** and the **named cohort** it is among ("miejsce 120 z 2 479 gmin w
  Polsce z kompletnym indeksem"). A rank without both is a defect.
- Descriptions live in `frontend/i18n/pl.ts` (`t.stats.*`), not in components.

## 3. Charts

- A meaningful **title** and a one-line description; **labelled axes** with units; **readable ticks** (at least
  11 px, no overlap, formatted through `api/format.ts`); a **legend** whenever there are two or more series or
  an area is encoded.
- **Tooltips** carry the date or category and every value with its unit, are reachable by keyboard (arrow keys
  on the chart) and are not the only way to read a value.
- **A textual or tabular equivalent** is always available next to the chart (a data table in a disclosure or a
  list), with the same numbers and units.
- **Never colour alone**: series differ by marker shape or line style as well; a band is labelled in the legend;
  states use text or an icon beside the colour.
- **Gaps and withheld values are shown as gaps**, with a reason ("za mało ofert z ceną"): never a zero, never an
  interpolated line across missing days, never a bar of height zero for "unknown".
- **One observation is a point**, not a trend: draw the point, say "mamy tylko jeden odczyt" and do not draw a
  line, a slope or a trend word. Two or three points say how few there are.
- Do not extrapolate, smooth or forecast. Do not average medians. Do not allocate a city figure to a district.
- Charts are loaded lazily (they are the heaviest dependency) and render a text fallback while loading and when
  they fail.

## 4. Cards and hierarchy

A statistical card reads top to bottom: **metric name**, **value with its unit**, **context** (period, area, how
it compares), then **supporting metadata** (sample, source). The value is the largest text; metadata is the
smallest and never the only place the unit appears.

## 5. Different things stay apart

Otodom asking rents (advertised, from ads) and GUS statistics (official, annual, administrative areas) are never
averaged, merged, ranked together or presented as the same place: each tab labels its source, period, territorial
grain and freshness. An Otodom place and a GUS gmina are *related* by a stored mapping, never interchangeable.

## Checklist (PR body, frontend line)

Every changed chart or metric: five answers present · direction and denominator on every rank · table
equivalent · gaps and single points honest · no colour-only encoding · ticks and units formatted through
`api/format.ts` · UX gate (`pnpm ux`) screenshots reviewed.

## Do not

- Show a bare number, a bare percentage or an unexplained score.
- Draw a line through missing days or invent a history for a district or a new place.
- Present a locality score as a property return or a forecast.
- Add a second chart library; the one in `frontend/package.json` (Recharts) is the library.
