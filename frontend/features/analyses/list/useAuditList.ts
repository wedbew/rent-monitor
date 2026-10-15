import { useInfiniteQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../../api/client";
import { tenantKey } from "../../../api/query";
import { useMe } from "../../../shell/session";
import type { AuditPage, AuditSummary } from "../queries";
import { apiQuery, type CollectionFilters } from "./filters";

export const PAGE_SIZE = 24;

/**
 * The collection, page by page over the API's cursor: each page is what the server returned, the next one is
 * asked for with the previous `next_cursor` and only while there is one. Nothing is sliced on the client.
 * Filters are part of the key, so a different filter is a different list (never a filtered view of another).
 */
export function useAuditList(filters: CollectionFilters) {
  const me = useMe();
  const query = useInfiniteQuery({
    queryKey: tenantKey(me.id, "audits", "list", filters.status, filters.grade, filters.q),
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }): Promise<AuditPage> =>
      unwrap(
        await api.GET("/api/audits", {
          params: { query: apiQuery(filters, PAGE_SIZE, pageParam) },
          signal,
        }),
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 15_000,
  });
  const seen = new Set<string>();
  const items: AuditSummary[] = [];
  for (const page of query.data?.pages ?? []) {
    for (const item of page.items) {
      if (!seen.has(item.audit_id)) {
        seen.add(item.audit_id);
        items.push(item);
      }
    }
  }
  return { query, items };
}
