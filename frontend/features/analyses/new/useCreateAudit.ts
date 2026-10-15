import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api, unwrap } from "../../../api/client";
import { TransportError } from "../../../api/errors";
import { refreshAccount } from "../../../shell/session";
import type { AuditPage } from "../queries";

/**
 * Submit a listing. Never retried by the library (api/query.ts) and never twice for one click: the button is busy
 * while the request is in flight. `lang` is always Polish and `analyst` is never sent (the API answers
 * FEATURE_NOT_IN_PLAN for it), so the body is exactly what the product offers today.
 */
export function useCreateAudit() {
  const client = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: async (listingRef: string) =>
      unwrap(
        await api.POST("/api/audits", { body: { listing_ref: listingRef, lang: "pl", analyst: false } }),
      ),
    onSuccess: (accepted) => {
      refreshAccount(client); // the reserved report shows in the balance, from the server
      void navigate(`/app/analyses/${accepted.audit_id}`);
    },
  });
}

export type Reconciled = { readonly found: { readonly auditId: string } } | { readonly unknown: true };

const OTODOM_ID = /(ID[0-9A-Za-z]{3,20})(?:[/?#]|$)/;

/** The Otodom id inside what the person typed (an id, or the end of a listing URL); null when there is none. */
export function otodomIdOf(listingRef: string): string | null {
  return OTODOM_ID.exec(listingRef.trim())?.[1] ?? null;
}

/**
 * After a failure that says nothing about whether the server got the request (dropped connection, timeout), the
 * list of analyses can tell, but only for THIS listing: a row with the same Otodom id created since the click
 * means an analysis of it exists. An unrelated recent analysis, a missing row, a clock that disagrees or a list
 * that cannot be read prove nothing: the answer is then "unknown", never "not sent". Nothing here resubmits.
 */
export async function reconcileAfterAmbiguousFailure(
  error: unknown,
  listingRef: string,
  since: number,
): Promise<Reconciled | null> {
  if (!(error instanceof TransportError) || (error.kind !== "network" && error.kind !== "timeout"))
    return null;
  const id = otodomIdOf(listingRef);
  if (id === null) return { unknown: true };
  try {
    const page: AuditPage = unwrap(await api.GET("/api/audits", { params: { query: { limit: 10 } } }));
    const created = page.items.find((a) => a.otodom_id === id && Date.parse(a.created_at) >= since - 300_000);
    return created === undefined ? { unknown: true } : { found: { auditId: created.audit_id } };
  } catch {
    return { unknown: true };
  }
}
