import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { api, unwrap } from "../../api/client";
import { ApiError, TransportError } from "../../api/errors";
import { tenantKey } from "../../api/query";
import { whileSignedIn } from "../../shell/cancellable";
import { refreshBalance, useMe } from "../../shell/session";
import { isCurrentSession, registerTenantCleanup, sessionGeneration } from "../../shell/tenant";
import { clearIntent, type Intent, loadIntent, saveIntent } from "./intent";
import {
  type PackCode,
  readInvoiceUrl,
  readPacks,
  readPurchase,
  readPurchases,
  SETTLED,
  type Purchase,
  type PurchaseList,
} from "./guards";

const key = (userId: string, ...parts: readonly string[]) => tenantKey(userId, "billing", ...parts);

/** The catalog is the server's: prices come as gross PLN strings and are never computed on. */
export function usePacks() {
  const me = useMe();
  return useQuery({
    queryKey: key(me.id, "packs"),
    queryFn: async ({ signal }) => {
      const packs = readPacks(unwrap(await api.GET("/api/billing/packs", { signal })));
      if (packs === null) throw new TransportError("invalid-response");
      return packs;
    },
    staleTime: 60_000,
  });
}

export function usePurchases() {
  const me = useMe();
  return useQuery({
    queryKey: key(me.id, "purchases"),
    queryFn: async ({ signal }): Promise<PurchaseList> => {
      const purchases = readPurchases(unwrap(await api.GET("/api/billing/purchases", { signal })));
      if (purchases === null) throw new TransportError("invalid-response");
      return purchases;
    },
    staleTime: 5_000,
    refetchOnMount: "always",
  });
}

/** 2 s, 3 s, 5 s, 8 s, then every 15 s: payment confirmation (BLIK) can take minutes, never a hammering loop. */
export const pollSchedule = { stepsMs: [2_000, 3_000, 5_000, 8_000], steadyMs: 15_000 };

/** Unsettled after this long, polling stops and the person decides: "check again" starts a new bounded round. */
export const pollLimits = { deadlineMs: 10 * 60_000 };

export function pollDelayMs(attempt: number): number {
  return pollSchedule.stepsMs[attempt] ?? pollSchedule.steadyMs;
}

/**
 * An answer that will not change by asking again: the purchase is not this person's or does not exist, or the session
 * is gone. Everything else (a timeout, a 5xx, a dropped connection, a limit) may pass.
 */
export function isPermanentFailure(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status >= 400 &&
    error.status < 500 &&
    error.status !== 408 &&
    error.status !== 429
  );
}

/**
 * One purchase, asked again with backoff until the server says it is settled (granted, failed, under review,
 * refunded). The browser's own "payment succeeded" is never evidence: only this answer is. When it settles the
 * balance is read again from the server.
 *
 * Polling is bounded: it stops at a settled answer, at a permanent failure (404/403 never fix themselves), after
 * `pollLimits.deadlineMs` without a settled answer (`gaveUp`), on unmount and on sign-out. The delay grows with every
 * attempt, answered or failed, so a failing server is not hammered either. `checkAgain` is the person's own retry;
 * it never creates an order, it only reads.
 */
export function usePurchase(purchaseId: string | null) {
  const client = useQueryClient();
  const me = useMe();
  const [round, setRound] = useState(0);
  // Kept per purchase, so opening another purchase never inherits a stopped poll or a used-up schedule.
  const [gaveUpFor, setGaveUpFor] = useState<string | null>(null);
  const gaveUp = purchaseId !== null && gaveUpFor === purchaseId;
  const [roundStart, setRoundStart] = useState<{ readonly id: string | null; readonly answers: number }>({
    id: purchaseId,
    answers: 0,
  });
  const answersBefore = roundStart.id === purchaseId ? roundStart.answers : 0;
  const query = useQuery({
    queryKey: key(me.id, "purchase", purchaseId ?? "none"),
    enabled: purchaseId !== null,
    queryFn: async ({ signal }): Promise<Purchase> => {
      const purchase = readPurchase(
        unwrap(
          await api.GET("/api/billing/purchases/{purchase_id}", {
            params: { path: { purchase_id: purchaseId ?? "" } },
            signal,
          }),
        ),
      );
      if (purchase === null) throw new TransportError("invalid-response");
      return purchase;
    },
    staleTime: 0,
    refetchInterval: (q) => {
      const data = q.state.data;
      if (data !== undefined && SETTLED.has(data.state)) return false;
      if (q.state.status === "error" && isPermanentFailure(q.state.error)) return false;
      if (gaveUp) return false;
      return pollDelayMs(q.state.dataUpdateCount + q.state.errorUpdateCount - answersBefore);
    },
  });
  const settledState = query.data !== undefined && SETTLED.has(query.data.state) ? query.data.state : null;
  const settled = settledState !== null;
  // Once per settled answer, not on every refetch of a settled purchase (window focus refetches with staleTime 0).
  useEffect(() => {
    if (settledState === null) return;
    refreshBalance(client);
    void client.invalidateQueries({ queryKey: key(me.id, "purchases") });
  }, [settledState, client, me.id]);
  const permanent = query.isError && isPermanentFailure(query.error);
  const active = purchaseId !== null && !settled && !permanent;
  useEffect(() => {
    if (!active) return;
    const timer = setTimeout(() => setGaveUpFor(purchaseId), pollLimits.deadlineMs);
    return () => clearTimeout(timer);
  }, [active, round, purchaseId]);
  const { refetch } = query;
  const checkAgain = () => {
    const state = client.getQueryState(key(me.id, "purchase", purchaseId ?? "none"));
    const answers = (state?.dataUpdateCount ?? 0) + (state?.errorUpdateCount ?? 0);
    setGaveUpFor(null);
    setRoundStart({ id: purchaseId, answers }); // a new round starts the backoff from its first step again
    setRound((n) => n + 1);
    void refetch();
  };
  return { ...query, gaveUp: gaveUp && !settled, permanentFailure: permanent, checkAgain };
}

/** A failure after which the request MAY have been applied: the same key must be reused, never a new one. */
export function isAmbiguous(error: unknown): boolean {
  if (error instanceof TransportError) return error.kind !== "aborted";
  return error instanceof ApiError && error.status >= 500;
}

/** Another pack was asked for while an order is unresolved: refused here, and the unresolved order is kept. */
export class IntentConflict extends Error {
  constructor() {
    super("an unresolved order is pending");
    this.name = "IntentConflict";
  }
}

/**
 * Start a purchase. One idempotency key per intent (a pack the person chose): the intent is saved before the request
 * and kept after an ambiguous failure, so the same key is reused by every retry, also after a reload, and a lost
 * answer can never create a second order. A definite answer (a purchase came back, or the server refused) ends the
 * intent; the next click is a new one. While an intent is unresolved the page offers no other pack (`unresolved`).
 * Never retried by a library (api/query.ts) and never resubmitted automatically.
 */
export function useCheckout() {
  const client = useQueryClient();
  const me = useMe();
  const [intent, setIntent] = useState<Intent | null>(() => loadIntent(me.id));
  const mutation = useMutation({
    mutationFn: async (pack: PackCode): Promise<Purchase> => {
      const remembered = loadIntent(me.id) ?? intent;
      const fresh = remembered === null || (remembered.parked === true && remembered.pack !== pack);
      if (!fresh && remembered.pack !== pack) throw new IntentConflict(); // never replaced silently
      // The same pack always goes out with its remembered key, also after "not found": a late arrival stays one order.
      const current: Intent = fresh ? { pack, key: crypto.randomUUID() } : { pack, key: remembered.key };
      saveIntent(me.id, current); // before the request: a reload after a lost answer can still ask about it
      setIntent(current);
      const started = sessionGeneration();
      const purchase = readPurchase(
        await whileSignedIn(async (signal) =>
          unwrap(
            await api.POST("/api/billing/checkout", {
              params: { header: { "Idempotency-Key": current.key } },
              body: { pack_code: pack },
              signal,
            }),
          ),
        ),
      );
      if (purchase === null) throw new TransportError("invalid-response");
      if (!isCurrentSession(started)) throw new TransportError("aborted");
      return purchase;
    },
    onSuccess: () => {
      clearIntent(me.id);
      setIntent(null);
      void client.invalidateQueries({ queryKey: key(me.id, "purchases") });
    },
    onError: (error) => {
      if (error instanceof IntentConflict) return; // the unresolved order stays exactly as it was
      if (!isAmbiguous(error)) {
        clearIntent(me.id);
        setIntent(null);
      }
    },
  });
  const resolve = useCallback(() => {
    clearIntent(me.id);
    setIntent(null);
  }, [me.id]);
  /** The server has no order with this key: keep the key for the same pack, free the choice of another. */
  const park = useCallback(() => {
    setIntent((current) => {
      if (current === null) return null;
      const parked: Intent = { ...current, parked: true };
      saveIntent(me.id, parked);
      return parked;
    });
  }, [me.id]);
  useEffect(() => registerTenantCleanup(() => clearIntent(me.id)), [me.id]); // a person's pending order is not the next one's
  return {
    ...mutation,
    intent,
    unresolved: intent !== null && intent.parked !== true && !mutation.isPending,
    resolve,
    park,
  };
}

/**
 * Ask the server for the purchase created with exactly this `Idempotency-Key`: zero or one. Never a guess from recent
 * purchases. A read: it creates nothing.
 */
export function useIntentLookup() {
  return useMutation({
    mutationFn: (intent: Intent): Promise<readonly Purchase[]> =>
      whileSignedIn(async (signal) => {
        const found = readPurchases(
          unwrap(
            await api.GET("/api/billing/purchases", {
              params: { query: { request_key: intent.key } },
              signal,
            }),
          ),
        );
        // An unreadable row is not "not found": the order may exist, so the answer settles nothing.
        if (found === null || found.hidden > 0) throw new TransportError("invalid-response");
        return found.purchases;
      }),
  });
}

/** The seller's document for a sale, fetched when asked for; the link is short-lived and never kept. */
export function useInvoice() {
  return useMutation({
    mutationFn: async (purchaseId: string): Promise<string> => {
      const url = readInvoiceUrl(
        await whileSignedIn(async (signal) =>
          unwrap(
            await api.GET("/api/billing/purchases/{purchase_id}/invoice", {
              params: { path: { purchase_id: purchaseId } },
              signal,
            }),
          ),
        ),
      );
      if (url === null) throw new TransportError("invalid-response");
      return url;
    },
  });
}
