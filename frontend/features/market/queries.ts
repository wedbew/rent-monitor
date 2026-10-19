import { useInfiniteQuery, useQuery } from "@tanstack/react-query";

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
