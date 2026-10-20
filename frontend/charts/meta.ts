/**
 * The five answers every statistic carries (`.agent/rules/statistics.md` section 1). `MetricCard` and `ChartFigure`
 * take a `StatMeta` and refuse to render without all of it, so a figure cannot ship as a bare number.
 */
export interface StatMeta {
  /** What is measured, in plain Polish ("Mediana ceny ofertowej najmu za m²"). */
  readonly measure: string;
  /** The unit ("zł/m²", "osób na 1000 mieszkańców"). */
  readonly unit: string;
  /** The geographic area, with its level when it could be misread ("Toruń, miejscowość z katalogu Otodom"). */
  readonly area: string;
  /** The reading date, window or statistical year ("ostatnie 90 dób do 19 października 2026"). */
  readonly period: string;
  /** The source ("Otodom, ogłoszenia najmu"). */
  readonly source: string;
  /** The sample or coverage ("12 ofert z ceną"). */
  readonly sample: string;
  /** One sentence: what a higher value means and what the figure is not. */
  readonly interpretation: string;
}

/** A plotting coordinate from a decimal string. Used for positions only: never shown, summed or compared as money. */
export function plotValue(value: string | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
