import { t } from "../../i18n";
import type { MapMetric } from "./MarketMap";
import { metricValue } from "./MarketMap";
import type { OverviewPlace } from "./queries";

/** Everything the explorer shows is in the address, read against closed vocabularies. */
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
  readonly sel: string | null;
  readonly ids: readonly string[];
}

export function readExplore(params: URLSearchParams): ExploreState {
  const pick = <T extends string>(all: readonly T[], raw: string | null, fallback: T): T =>
    all.find((x) => x === raw) ?? fallback;
  const sel = params.get("sel");
  const ids = (params.get("ids") ?? "")
    .split(",")
    .filter((id) => ID.test(id))
    .filter((id, i, all) => all.indexOf(id) === i)
    .slice(0, MAX_COMPARED);
  return {
    view: pick(VIEWS, params.get("view"), "map"),
    metric: pick(METRICS, params.get("metric"), "ppm2"),
    sort: pick(SORTS, params.get("sort"), "name"),
    sel: sel !== null && ID.test(sel) ? sel : null,
    ids,
  };
}

export function writeExplore(state: ExploreState): URLSearchParams {
  const p = new URLSearchParams();
  if (state.view !== "map") p.set("view", state.view);
  if (state.metric !== "ppm2") p.set("metric", state.metric);
  if (state.sort !== "name") p.set("sort", state.sort);
  if (state.sel !== null) p.set("sel", state.sel);
  if (state.ids.length > 0) p.set("ids", state.ids.join(","));
  return p;
}

export const METRIC_LABELS: Readonly<Record<MapMetric, string>> = t.market.explore.metrics;
export const SORT_LABELS: Readonly<Record<SortName, string>> = t.market.explore.sorts;

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

export const toggleCompared = (ids: readonly string[], id: string): readonly string[] =>
  ids.includes(id) ? ids.filter((x) => x !== id) : ids.length >= MAX_COMPARED ? ids : [...ids, id];
