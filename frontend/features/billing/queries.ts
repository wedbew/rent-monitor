import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { api, unwrap } from "../../api/client";
import { ApiError, TransportError } from "../../api/errors";
import { tenantKey } from "../../api/query";
import { whileSignedIn } from "../../shell/cancellable";
import { refreshBalance, useMe } from "../../shell/session";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";
import {
  type PackCode,
  readInvoiceUrl,
  readPacks,
  readPurchase,
  readPurchases,
  SETTLED,
  type Purchase,
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
    queryFn: async ({ signal }) => {
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

export function pollDelayMs(attempt: number): number {
  return pollSchedule.stepsMs[attempt] ?? pollSchedule.steadyMs;
}

/**
 * One purchase, asked again with backoff until the server says it is settled (granted, failed, under review,
 * refunded). The browser's own "payment succeeded" is never evidence: only this answer is. When it settles the
 * balance is read again from the server.
 */
export function usePurchase(purchaseId: string | null) {
  const client = useQueryClient();
  const me = useMe();
  return useQuery({
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
      if (SETTLED.has(purchase.state)) {
        refreshBalance(client);
        void client.invalidateQueries({ queryKey: key(me.id, "purchases") });
      }
      return purchase;
    },
    staleTime: 0,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data !== undefined && SETTLED.has(data.state)) return false;
      return pollDelayMs(query.state.dataUpdateCount);
    },
  });
}

/** A failure after which the request MAY have been applied: the same key must be reused, never a new one. */
export function isAmbiguous(error: unknown): boolean {
  if (error instanceof TransportError) return error.kind !== "aborted";
  return error instanceof ApiError && error.status >= 500;
}

/**
 * Start a purchase. One idempotency key per intent (a pack the person chose): the key is created with the first
 * attempt and reused for every retry after an ambiguous failure, so a lost answer can never create a second order.
 * A definite answer (a purchase came back, or the server refused) ends the intent; the next click is a new one.
 * Never retried by a library (api/query.ts) and never resubmitted automatically.
 */
export function useCheckout() {
  const client = useQueryClient();
  const me = useMe();
  const intent = useRef<{ pack: PackCode; key: string } | null>(null);
  const mutation = useMutation({
    mutationFn: async (pack: PackCode): Promise<Purchase> => {
      if (intent.current?.pack !== pack) intent.current = { pack, key: crypto.randomUUID() };
      const started = sessionGeneration();
      const idempotencyKey = intent.current.key;
      const purchase = readPurchase(
        await whileSignedIn(async (signal) =>
          unwrap(
            await api.POST("/api/billing/checkout", {
              params: { header: { "Idempotency-Key": idempotencyKey } },
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
      intent.current = null;
      void client.invalidateQueries({ queryKey: key(me.id, "purchases") });
    },
    onError: (error) => {
      if (!isAmbiguous(error)) intent.current = null;
    },
  });
  return { ...mutation, retryingSameOrder: () => intent.current !== null };
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
