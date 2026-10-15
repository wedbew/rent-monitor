import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema.generated";

export type AuditPage = components["schemas"]["AuditPage"];
export type AuditSummary = components["schemas"]["AuditSummary"];

/** Tenant data lives under `["audits", ...]`: sign-out empties the whole cache, so nothing outlives the person. */
export const RECENT_AUDITS_KEY = ["audits", "recent"] as const;

/** The newest analyses, for the dashboard. Fresh for 15 s: a running one should not look stale after a navigation. */
export function useRecentAudits(limit = 5) {
  return useQuery({
    queryKey: [...RECENT_AUDITS_KEY, limit],
    queryFn: async (): Promise<AuditPage> =>
      unwrap(await api.GET("/api/audits", { params: { query: { limit } } })),
    staleTime: 15_000,
  });
}
