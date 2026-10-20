import { t } from "../../i18n";

/**
 * Everything the market pages show is chosen in the address, so Back, Refresh and a shared link restore it. Each
 * value is read against a closed vocabulary: an unknown value in the URL falls back to the default and is never
 * sent to the API.
 */
export const SERIES = ["cohort", "additions"] as const;
export type Series = (typeof SERIES)[number];

export const PERIODS = [30, 90, 365] as const;
export type Period = (typeof PERIODS)[number];

export const COHORT_KEYS = [
  "all",
  "rooms_1",
  "rooms_2",
  "rooms_3",
  "rooms_4plus",
  "size_lt30",
  "size_30_45",
  "size_45_60",
  "size_60_80",
  "size_80plus",
] as const;
export type CohortKey = (typeof COHORT_KEYS)[number];

export interface Selection {
  readonly series: Series;
  readonly cohort: CohortKey;
  readonly days: Period;
}

export const DEFAULT_SELECTION: Selection = { series: "cohort", cohort: "all", days: 90 };

/** The API's `q` is 1 to 60 characters; control characters never reach it. */
const MAX_SEARCH = 60;
// eslint-disable-next-line no-control-regex
const CONTROL = /[\u0000-\u001f\u007f]/;

export function cleanSearch(raw: string | null): string {
  const text = (raw ?? "").trim();
  return text.length === 0 || text.length > MAX_SEARCH || CONTROL.test(text) ? "" : text;
}

export function readSelection(params: URLSearchParams): Selection {
  const series = SERIES.find((s) => s === params.get("series")) ?? DEFAULT_SELECTION.series;
  const cohort = COHORT_KEYS.find((c) => c === params.get("cohort")) ?? DEFAULT_SELECTION.cohort;
  const days = PERIODS.find((d) => String(d) === params.get("days")) ?? DEFAULT_SELECTION.days;
  return { series, cohort, days };
}

/** Only non-default values are written; `q` rides along so the way back to the list keeps the search. */
export function writeSelection(selection: Selection, q: string): URLSearchParams {
  const params = new URLSearchParams();
  if (selection.series !== DEFAULT_SELECTION.series) params.set("series", selection.series);
  if (selection.cohort !== DEFAULT_SELECTION.cohort) params.set("cohort", selection.cohort);
  if (selection.days !== DEFAULT_SELECTION.days) params.set("days", String(selection.days));
  if (q !== "") params.set("q", q);
  return params;
}

export const PERIOD_LABELS: Readonly<Record<Period, string>> = {
  30: t.rynek.periods.d30,
  90: t.rynek.periods.d90,
  365: t.rynek.periods.d365,
};
