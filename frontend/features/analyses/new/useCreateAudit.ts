import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api, unwrap } from "../../../api/client";
import { TransportError } from "../../../api/errors";
import { refreshAccount } from "../../../shell/session";
import { isCurrentSession, sessionGeneration } from "../../../shell/tenant";
import type { AuditPage } from "../queries";

/**
 * Submit a listing. Never retried by the library (api/query.ts) and never twice for one click: the button is busy
 * while the request is in flight. Every submission carries an `Idempotency-Key`: the server creates at most one
 * audit (and one reservation) per key, so sending the same submission again can never charge twice. `lang` is
 * always Polish and `analyst` is never sent (the API answers FEATURE_NOT_IN_PLAN for it).
 */
export function useCreateAudit() {
  const client = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    // The session generation is read at the click (`submission`), not here: the library starts this a tick later,
    // by when a sign-out may already have happened.
    mutationFn: async ({ listingRef, generation, requestKey }: Submission) => {
      const accepted = unwrap(
        await api.POST("/api/audits", {
          body: { listing_ref: listingRef, lang: "pl", analyst: false },
          params: { header: { "Idempotency-Key": requestKey } },
        }),
      );
      return { accepted, generation };
    },
    onSuccess: ({ accepted, generation }) => {
      // An answer that arrives after the person signed out (or somebody else signed in) belongs to nobody here.
      if (!isCurrentSession(generation)) return;
      refreshAccount(client); // the reserved report shows in the balance, from the server
      void navigate(`/app/analyses/${accepted.audit_id}`);
    },
  });
}

export interface Submission {
  readonly listingRef: string;
  readonly generation: number;
  /** The `Idempotency-Key`: one per submission, kept when the same submission is sent again. */
  readonly requestKey: string;
}

/**
 * What one click submits: the reference, the session it was made in and its request key. When the previous
 * submission's answer was lost and the person sends the same listing again, it is the SAME submission (same key):
 * the server then answers with the audit that request created, if it did, instead of reserving again.
 */
export function submission(listingRef: string, unanswered: Submission | null = null): Submission {
  const generation = sessionGeneration();
  if (unanswered !== null && unanswered.listingRef === listingRef && unanswered.generation === generation)
    return unanswered;
  return { listingRef, generation, requestKey: crypto.randomUUID() };
}

/**
 * What the server says about a submission whose answer was lost: it created this audit (`found`), it has no
 * audit for this request key (`notReceived`: sending the same submission again is safe), or it could not be asked
 * (`unknown`).
 */
export type Reconciled =
  | { readonly found: { readonly auditId: string } }
  | { readonly notReceived: true }
  | { readonly unknown: true };

/**
 * After a failure that says nothing about whether the server got the request (dropped connection, timeout), ask
 * the server, read-only, whether THIS request (its key) created an audit. Nothing is guessed from other rows,
 * listings or clocks, and nothing here resubmits: the person decides to send it again.
 */
export async function reconcileAfterAmbiguousFailure(
  error: unknown,
  submitted: Submission,
): Promise<Reconciled | null> {
  if (!(error instanceof TransportError) || (error.kind !== "network" && error.kind !== "timeout"))
    return null;
  try {
    const page: AuditPage = unwrap(
      await api.GET("/api/audits", { params: { query: { request_key: submitted.requestKey, limit: 1 } } }),
    );
    // A list read after the session changed is somebody else's: it says nothing about this request.
    if (!isCurrentSession(submitted.generation)) return null;
    const created = page.items[0];
    return created === undefined ? { notReceived: true } : { found: { auditId: created.audit_id } };
  } catch {
    return { unknown: true };
  }
}
