import { t } from "../../i18n";
import { COHORT_KEYS, type CohortKey } from "./filters";
import type { MapMetric } from "./MarketMap";
import { metricValue } from "./MarketMap";
import type { OverviewPlace } from "./queries";

/** Everything the explorer shows is chosen in the address, read against closed vocabularies (unknown means default). */
export const VIEWS = ["map", "list", "compare"] as const;
export type ViewName = (typeof VIEWS)[number];
export const METRICS = ["ppm2", "rent", "sample"] as const;
export const SORTS = ["name", "ppm2", "rent", "sample"] as const;
export type SortName = (typeof SORTS)[number];
export const MAX_COMPARED = 4;
const ID = /^[a-z0-9-]{1,64}$/;

export interface ExploreState {
  readonly view: ViewName;
  readonly metric: MapMetric;
  readonly sort: SortName;
  readonly cohort: CohortKey;
  readonly sel: string | null;
  readonly ids: readonly string[];
}

export const parseIds = (raw: string | null): string[] =>
  (raw ?? "")
    .split(",")
    .filter((id) => ID.test(id))
    .filter((id, i, all) => all.indexOf(id) === i)
    .slice(0, MAX_COMPARED);

export function readExplore(params: URLSearchParams): ExploreState {
  const pick = <T extends string>(all: readonly T[], raw: string | null, fallback: T): T =>
    all.find((x) => x === raw) ?? fallback;
  const sel = params.get("sel");
  return {
    view: pick(VIEWS, params.get("view"), "map"),
    metric: pick(METRICS, params.get("metric"), "ppm2"),
    sort: pick(SORTS, params.get("sort"), "name"),
    cohort: pick(COHORT_KEYS, params.get("cohort"), "all"),
    sel: sel !== null && ID.test(sel) ? sel : null,
    ids: parseIds(params.get("ids")),
  };
}

/** Only non-default values are written, so the plain address stays plain. */
export function writeExplore(state: ExploreState, keep: URLSearchParams | null = null): URLSearchParams {
  const p = new URLSearchParams();
  if (state.view !== "map") p.set("view", state.view);
  if (state.metric !== "ppm2") p.set("metric", state.metric);
  if (state.sort !== "name") p.set("sort", state.sort);
  if (state.cohort !== "all") p.set("cohort", state.cohort);
  if (state.sel !== null) p.set("sel", state.sel);
  if (state.ids.length > 0) p.set("ids", state.ids.join(","));
  const q = keep?.get("q");
  if (q !== null && q !== undefined && q !== "") p.set("q", q);
  return p;
}

export const METRIC_LABELS: Readonly<Record<MapMetric, string>> = t.rynek.explore.metrics;
export const SORT_LABELS: Readonly<Record<SortName, string>> = t.rynek.explore.sorts;

/** Missing values sort last in either direction of a measure; names sort by Polish collation. */
export function sortPlaces(places: readonly OverviewPlace[], sort: SortName): OverviewPlace[] {
  const out = [...places];
  if (sort === "name") return out.sort((a, b) => a.name.localeCompare(b.name, "pl"));
  const key = (p: OverviewPlace) => metricValue(p, sort);
  return out.sort((a, b) => {
    const x = key(a);
    const y = key(b);
    if (x === null && y === null) return a.name.localeCompare(b.name, "pl");
    if (x === null) return 1;
    if (y === null) return -1;
    return y - x || a.name.localeCompare(b.name, "pl");
  });
}

/** Names fold diacritics so "Torun" finds "Toruń"; the search is a substring of the name, nothing fuzzier. */
const fold = (s: string): string =>
  s.toLocaleLowerCase("pl").normalize("NFD").replace(/\p{M}/gu, "").replace(/ł/g, "l");

export const matchesName = (name: string, needle: string): boolean =>
  needle.trim() === "" || fold(name).includes(fold(needle.trim()));

export const toggleCompared = (ids: readonly string[], id: string): readonly string[] =>
  ids.includes(id) ? ids.filter((x) => x !== id) : ids.length >= MAX_COMPARED ? ids : [...ids, id];
