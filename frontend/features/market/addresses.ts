import type { CohortKey } from "./filters";

/**
 * Every Rynek address in one place. The two tabs are paths, not hidden state, so each can be opened, reloaded and
 * shared: `/app/market/otodom` (default) and `/app/market/gus`. A place is a path segment, a group of flats the
 * `cohort` query, so Back and Forward walk through exactly what the person did.
 */
export const MARKET_ROOT = "/app/market";
export const OTODOM = `${MARKET_ROOT}/otodom`;
export const GUS = `${MARKET_ROOT}/gus`;

const query = (entries: Readonly<Record<string, string | null | undefined>>): string => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(entries))
    if (value !== null && value !== undefined && value !== "") params.set(key, value);
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
};

const cohortParam = (cohort: CohortKey | undefined) =>
  cohort === undefined || cohort === "all" ? null : cohort;

export const otodomAddress = (
  state: { cohort?: CohortKey; view?: string; sel?: string | null; ids?: readonly string[] } = {},
) =>
  `${OTODOM}${query({
    cohort: cohortParam(state.cohort),
    view: state.view === undefined || state.view === "map" ? null : state.view,
    sel: state.sel ?? null,
    ids: state.ids === undefined || state.ids.length === 0 ? null : state.ids.join(","),
  })}`;

export const compareAddress = (ids: readonly string[], cohort?: CohortKey) =>
  otodomAddress({ view: "compare", ids, ...(cohort === undefined ? {} : { cohort }) });

export const placeAddress = (locationId: string, cohort?: CohortKey) =>
  `${OTODOM}/${encodeURIComponent(locationId)}${query({ cohort: cohortParam(cohort) })}`;

/** A district is identified by the last segment of the source's district path, unique within its place. */
export const districtKey = (districtId: string): string => districtId.split("/").at(-1) ?? districtId;

export const districtAddress = (locationId: string, key: string, cohort?: CohortKey) =>
  `${OTODOM}/${encodeURIComponent(locationId)}/${encodeURIComponent(key)}${query({ cohort: cohortParam(cohort) })}`;

export const gusAddress = (state: { sel?: string | null; ids?: readonly string[] } = {}) =>
  `${GUS}${query({ sel: state.sel ?? null, ids: state.ids === undefined || state.ids.length === 0 ? null : state.ids.join(",") })}`;

export const gusPlaceAddress = (locationId: string) => `${GUS}/${encodeURIComponent(locationId)}`;
