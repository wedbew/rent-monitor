import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, unwrap, unwrapEmpty } from "../../api/client";
import { TransportError } from "../../api/errors";
import { tenantKey } from "../../api/query";
import { whileSignedIn } from "../../shell/cancellable";
import { useMe } from "../../shell/session";
import { readSaved, type SavedItem } from "./items";

/** The API's most generous page of `GET /api/saved` (its maximum is 200; there is no cursor). */
export const SAVED_PAGE = 200;

const savedKey = (userId: string) => tenantKey(userId, "saved");

export type SavedState =
  | { readonly status: "loading" }
  | { readonly status: "error"; readonly retry: () => void }
  | {
      readonly status: "ready";
      readonly items: readonly SavedItem[];
      readonly byId: ReadonlyMap<string, SavedItem>;
      /** The list may hold more than the API returned: a listing missing from it may still be saved (L-037). */
      readonly truncated: boolean;
    };

export function useSavedState(): SavedState {
  const me = useMe();
  const query = useQuery({
    queryKey: savedKey(me.id),
    queryFn: async ({ signal }): Promise<readonly SavedItem[]> => {
      const items = readSaved(
        unwrap(await api.GET("/api/saved", { params: { query: { limit: SAVED_PAGE } }, signal })),
      );
      if (items === null) throw new TransportError("invalid-response");
      return items;
    },
    staleTime: 15_000,
  });
  const items = query.data;
  const byId = useMemo(() => new Map((items ?? []).map((item) => [item.otodomId, item])), [items]);
  const { refetch } = query;
  if (items !== undefined) return { status: "ready", items, byId, truncated: items.length >= SAVED_PAGE };
  if (query.isError) return { status: "error", retry: () => void refetch() };
  return { status: "loading" };
}

/**
 * Save, or replace the note of a saved listing. The API replaces the whole row (an absent note clears it), so the
 * caller always sends the note it means to keep. Not optimistic: the list is asked again after the answer, so what
 * is shown is what the server holds, also after an ambiguous failure.
 */
export function useSaveListing() {
  const client = useQueryClient();
  const me = useMe();
  return useMutation({
    mutationFn: (variables: { otodomId: string; note: string | null }): Promise<void> =>
      whileSignedIn(async (signal) => {
        unwrap(
          await api.PUT("/api/saved/{otodom_id}", {
            params: { path: { otodom_id: variables.otodomId } },
            body: { note: variables.note },
            signal,
          }),
        );
      }),
    onSettled: () => client.invalidateQueries({ queryKey: savedKey(me.id) }),
  });
}

export function useUnsaveListing() {
  const client = useQueryClient();
  const me = useMe();
  return useMutation({
    mutationFn: (otodomId: string): Promise<void> =>
      whileSignedIn(async (signal) =>
        unwrapEmpty(
          await api.DELETE("/api/saved/{otodom_id}", { params: { path: { otodom_id: otodomId } }, signal }),
        ),
      ),
    onSettled: () => client.invalidateQueries({ queryKey: savedKey(me.id) }),
  });
}
