import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, unwrap, unwrapEmpty } from "../../api/client";
import { TransportError } from "../../api/errors";
import { tenantKey } from "../../api/query";
import { whileSignedIn } from "../../shell/cancellable";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";
import { useMe } from "../../shell/session";
import { readSaved, type SavedItem } from "./items";

/**
 * One request asks for the per-account cap (500), the API's maximum, so the answer holds every saved listing. A full
 * answer may still be incomplete (the cap is soft), so then a listing that is absent stays unknown (L-037).
 */
export const SAVED_PAGE = 500;

const savedKey = (userId: string) => tenantKey(userId, "saved");

/** Ask for the list again, unless the session that made the change is gone (a late answer is not the next person's). */
function refreshWhileCurrent(client: QueryClient, userId: string, generation: number) {
  return isCurrentSession(generation) ? client.invalidateQueries({ queryKey: savedKey(userId) }) : undefined;
}

export type SavedState =
  | { readonly status: "loading" }
  | { readonly status: "error"; readonly retry: () => void }
  | {
      readonly status: "ready";
      readonly items: readonly SavedItem[];
      readonly byId: ReadonlyMap<string, SavedItem>;
      /** The list may hold more than the API returned: a listing missing from it is unknown, not unsaved (L-037). */
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
 * Save a listing, or edit its note. Without `note` the request has no note key and the server keeps the stored note;
 * a string sets it and `null` clears it (the note editor says so explicitly). Not optimistic: the list is asked again after the answer, so what
 * is shown is what the server holds, also after an ambiguous failure.
 */
export function useSaveListing() {
  const client = useQueryClient();
  const me = useMe();
  return useMutation({
    mutationFn: (variables: { otodomId: string; note?: string | null }): Promise<void> =>
      whileSignedIn(async (signal) => {
        unwrap(
          await api.PUT("/api/saved/{otodom_id}", {
            params: { path: { otodom_id: variables.otodomId } },
            body: variables.note === undefined ? {} : { note: variables.note },
            signal,
          }),
        );
      }),
    onMutate: () => sessionGeneration(),
    onSettled: (_data, _error, _variables, generation) =>
      generation === undefined ? undefined : refreshWhileCurrent(client, me.id, generation),
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
    onMutate: () => sessionGeneration(),
    onSettled: (_data, _error, _variables, generation) =>
      generation === undefined ? undefined : refreshWhileCurrent(client, me.id, generation),
  });
}
