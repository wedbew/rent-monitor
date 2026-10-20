import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import { tenantKey } from "../../api/query";
import type { components } from "../../api/schema.generated";
import { useMe } from "../../shell/session";
import type { Selection } from "./filters";

// LEGAL[third-party-data]: reads aggregates of Otodom asking rents; terms unreviewed (B-012) (RM-422)
export type LocationPage = components["schemas"]["LocationPage"];
export type LocationSummary = components["schemas"]["LocationSummaryOut"];
export type LocationDetail = components["schemas"]["LocationDetailOut"];
export type LocationHistory = components["schemas"]["LocationHistoryOut"];
export type AskingRent = components["schemas"]["AskingRentOut"];

export type Overview = components["schemas"]["OverviewOut"];
export type OverviewPlace = components["schemas"]["OverviewPlaceOut"];
export type LocationContext = components["schemas"]["LocationContextOut"];
export type MetricView = components["schemas"]["MetricViewOut"];
export type LocationDistricts = components["schemas"]["LocationDistrictsOut"];
export type DistrictRow = components["schemas"]["DistrictOut"];
export type LocationIndex = components["schemas"]["LocationIndexOut"];
export type IndexView = components["schemas"]["IndexOut"];
export type IndexComponent = components["schemas"]["IndexComponentOut"];
export type RankingOverview = components["schemas"]["RankingOverviewOut"];
export type RankingEntry = components["schemas"]["RankingEntryOut"];

export const PAGE_SIZE = 30;

/**
 * The places, page by page over the API's cursor. The search text is part of the key, so a different search is a
 * different list and a slow answer to an earlier search can never replace the latest one. Nothing is sliced here.
 */
export function useLocations(q: string) {
  const me = useMe();
  const query = useInfiniteQuery({
    queryKey: tenantKey(me.id, "market", "list", q),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }): Promise<LocationPage> =>
      unwrap(
        await api.GET("/api/market/locations", {
          params: {
            query: {
              limit: PAGE_SIZE,
              ...(q === "" ? {} : { q }),
              ...(pageParam === null ? {} : { cursor: pageParam }),
            },
          },
          signal,
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 30_000,
  });
  const seen = new Set<string>();
  const items: LocationSummary[] = [];
  for (const page of query.data?.pages ?? []) {
    for (const item of page.items) {
      if (!seen.has(item.location_id)) {
        seen.add(item.location_id);
        items.push(item);
      }
    }
  }
  return { query, items };
}

/** One place: its freshness and the cohorts the API publishes for it. */
export function useLocationDetail(locationId: string) {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "place", locationId),
    queryFn: async ({ signal }): Promise<LocationDetail> =>
      unwrap(
        await api.GET("/api/market/locations/{location_id}", {
          params: { path: { location_id: locationId } },
          signal,
        }),
      ),
    staleTime: 30_000,
  });
}

/** The daily readings of the chosen series and cohort. Every part of the selection is in the key. */
export function useLocationHistory(locationId: string, selection: Selection, enabled: boolean) {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(
      me.id,
      "market",
      "history",
      locationId,
      selection.series,
      selection.cohort,
      selection.days,
    ),
    queryFn: async ({ signal }): Promise<LocationHistory> =>
      unwrap(
        await api.GET("/api/market/locations/{location_id}/history", {
          params: {
            path: { location_id: locationId },
            query: { series: selection.series, cohort: selection.cohort, days: selection.days },
          },
          signal,
        }),
      ),
    staleTime: 30_000,
    enabled,
  });
}

/**
 * Every place this account may see, in one answer, for one apartment-size or rooms group (`cohort`): what the map,
 * the sort and the comparison read. The group is part of the key, so a different group is a different answer; the
 * previous one stays on screen (marked busy) until the new one arrives, never a blank map.
 */
export function useOverview(cohort: string = "all") {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "overview", cohort),
    queryFn: async ({ signal }): Promise<Overview> =>
      unwrap(
        await api.GET("/api/market/overview", {
          params: { query: cohort === "all" ? {} : { cohort } },
          signal,
        }),
      ),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}

/** The districts the source names under one place, with their own statistics for one group of flats. */
export function useDistricts(locationId: string, cohort: string, enabled = true) {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "districts", locationId, cohort),
    queryFn: async ({ signal }): Promise<LocationDistricts> =>
      unwrap(
        await api.GET("/api/market/locations/{location_id}/districts", {
          params: {
            path: { location_id: locationId },
            query: cohort === "all" ? {} : { cohort },
          },
          signal,
        }),
      ),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    enabled,
  });
}

/** The experimental GUS locality index of the gmina a place belongs to. */
export function useLocationRanking(locationId: string, enabled = true) {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "ranking", locationId),
    queryFn: async ({ signal }): Promise<LocationIndex> =>
      unwrap(
        await api.GET("/api/market/locations/{location_id}/ranking", {
          params: { path: { location_id: locationId } },
          signal,
        }),
      ),
    staleTime: 5 * 60_000,
    enabled,
  });
}

/** The places of the account with the index of their gmina, best position first. */
export function useRankingOverview() {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "ranking-overview"),
    queryFn: async ({ signal }): Promise<RankingOverview> =>
      unwrap(await api.GET("/api/market/ranking", { signal })),
    staleTime: 5 * 60_000,
  });
}

/** The GUS BDL context of one place; `enabled` keeps a comparison from asking for places it does not show. */
export function useLocationContext(locationId: string, enabled = true) {
  const me = useMe();
  return useQuery({
    queryKey: tenantKey(me.id, "market", "context", locationId),
    queryFn: async ({ signal }): Promise<LocationContext> =>
      unwrap(
        await api.GET("/api/market/locations/{location_id}/context", {
          params: { path: { location_id: locationId } },
          signal,
        }),
      ),
    staleTime: 5 * 60_000,
    enabled,
  });
}
