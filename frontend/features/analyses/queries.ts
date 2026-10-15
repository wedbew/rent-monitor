import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import type { components } from "../../api/schema.generated";
import { refreshBalance } from "../../shell/session";

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

export type AuditOut = components["schemas"]["AuditOut"];

export const auditKey = (auditId: string) => ["audits", "one", auditId] as const;

/** While an analysis is active the API is asked again at least this often, whatever the stream does. */
export const SAFETY_POLL_MS = 10_000;
export const FALLBACK_POLL_MS = 3_000;

const ACTIVE = new Set(["queued", "running"]);

/**
 * One analysis. It is re-read on every mount (a remount cannot resume a stream, so the status is asked again) and,
 * while it is active, polled: slowly as a safety net (a stream that connects but goes silent, a terminal frame
 * that never comes) and quickly once the stream is known to be down. The API stays the source of truth. When a
 * read shows the analysis finished, the balance is asked again too (captured or released is the server's to say).
 */
export function useAudit(auditId: string, options: { fast: boolean }) {
  const client = useQueryClient();
  return useQuery({
    queryKey: auditKey(auditId),
    queryFn: async (): Promise<AuditOut> => {
      const before = client.getQueryData<AuditOut>(auditKey(auditId));
      const audit = unwrap(
        await api.GET("/api/audits/{audit_id}", { params: { path: { audit_id: auditId } } }),
      );
      if (before !== undefined && ACTIVE.has(before.status) && !ACTIVE.has(audit.status))
        refreshBalance(client);
      return audit;
    },
    staleTime: 0,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === undefined || !ACTIVE.has(status)) return false;
      return options.fast ? FALLBACK_POLL_MS : SAFETY_POLL_MS;
    },
  });
}
