import {
  useMutation,
  useQuery,
  useQueryClient,
  type MutateOptions,
  type QueryClient,
} from "@tanstack/react-query";
import { useRef } from "react";

import { api, unwrap, unwrapEmpty } from "../../api/client";
import { tenantKey } from "../../api/query";
import type { components } from "../../api/schema.generated";
import { whileSignedIn } from "../../shell/cancellable";
import { useMe } from "../../shell/session";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";

type Schemas = components["schemas"];
export type ProjectSummary = Schemas["ProjectSummary"];
export type ProjectOut = Schemas["ProjectOut"];
export type GenerationOut = Schemas["GenerationOut"];
export type CandidateOut = Schemas["CandidateOut"];
export type OfferOut = Schemas["OfferOut"];
export type CatalogueStatus = Schemas["CatalogueStatus"];
export type CustomItemOut = Schemas["CustomItemOut"];
export type SelectionOut = Schemas["SelectionOut"];
export type RevisionOut = Schemas["RevisionOut"];
export type Brief = Schemas["Brief-Input"];
export type CustomItemIn = Schemas["CustomItemIn"];
export type MediaRef = Schemas["MediaRef"];

/** Tenant data lives under the signed-in person's key; a session change purges it (api/query.ts). */
export const projectsKey = (userId: string) => tenantKey(userId, "interior", "projects");
export const projectKey = (userId: string, projectId: string) =>
  tenantKey(userId, "interior", "project", projectId);
export const generationsKey = (userId: string, projectId: string) =>
  tenantKey(userId, "interior", "generations", projectId);
const catalogueKey = (userId: string) => tenantKey(userId, "interior", "catalogue");
const searchKey = (userId: string, projectId: string, params: SearchParams) =>
  tenantKey(userId, "interior", "search", projectId, params.q, params.category, params.maxPrice);

/** Same-origin, cookie-authenticated delivery of a stored image (the only way to reach one). */
export const mediaUrl = (projectId: string, mediaId: string): string =>
  `/api/interior/projects/${projectId}/media/${mediaId}`;

/** Polling while an operation is active, so a missed event can never leave the screen "running" forever. */
export const GENERATION_POLL_MS = 2_500;
/** Mutable only so a test can poll fast; the app never changes it. */
export const generationPoll = { ms: GENERATION_POLL_MS };
const ACTIVE = new Set(["queued", "running"]);
export const isActive = (state: string): boolean => ACTIVE.has(state);

export function useProjects() {
  const me = useMe();
  return useQuery({
    queryKey: projectsKey(me.id),
    queryFn: async ({ signal }): Promise<ProjectSummary[]> =>
      unwrap(await api.GET("/api/interior/projects", { signal })),
    staleTime: 15_000,
    retry: false,
  });
}

export function useProject(projectId: string) {
  const me = useMe();
  return useQuery({
    queryKey: projectKey(me.id, projectId),
    queryFn: async ({ signal }): Promise<ProjectOut> =>
      unwrap(
        await api.GET("/api/interior/projects/{project_id}", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
  });
}

export function useCatalogueStatus() {
  const me = useMe();
  return useQuery({
    queryKey: catalogueKey(me.id),
    queryFn: async ({ signal }): Promise<CatalogueStatus> =>
      unwrap(await api.GET("/api/interior/catalogue", { signal })),
    staleTime: 60_000,
    retry: false,
  });
}

export function useGenerations(projectId: string) {
  const me = useMe();
  return useQuery({
    queryKey: generationsKey(me.id, projectId),
    queryFn: async ({ signal }): Promise<GenerationOut[]> =>
      unwrap(
        await api.GET("/api/interior/projects/{project_id}/generations", {
          params: { path: { project_id: projectId } },
          signal,
        }),
      ),
    staleTime: 0,
    refetchOnMount: "always",
    retry: false,
    // Polls while something is active and stops on a terminal state, unmount and sign-out (the query is torn down).
    refetchInterval: (query) =>
      query.state.data?.some((g) => isActive(g.state)) === true ? generationPoll.ms : false,
  });
}

export interface SearchParams {
  readonly q: string;
  readonly category: string;
  readonly maxPrice: string;
}

export function useCatalogueSearch(projectId: string, params: SearchParams | null) {
  const me = useMe();
  return useQuery({
    queryKey:
      params === null
        ? tenantKey(me.id, "interior", "search", projectId, "idle")
        : searchKey(me.id, projectId, params),
    enabled: params !== null,
    queryFn: async ({ signal }): Promise<CandidateOut[]> => {
      const p = params ?? { q: "", category: "", maxPrice: "" };
      return unwrap(
        await api.GET("/api/interior/projects/{project_id}/catalogue/search", {
          params: {
            path: { project_id: projectId },
            query: {
              q: p.q,
              ...(p.category === "" ? {} : { category: p.category }),
              ...(p.maxPrice === "" ? {} : { max_price_pln: p.maxPrice }),
            },
          },
          signal,
        }),
      );
    },
    staleTime: 0,
    retry: false,
  });
}

/** Ask for a project again unless the session that made the change has ended (a late answer is not the next person's). */
function refresh(client: QueryClient, userId: string, projectId: string | null, generation: number) {
  if (!isCurrentSession(generation)) return undefined;
  return Promise.all([
    projectId === null ? undefined : client.invalidateQueries({ queryKey: projectKey(userId, projectId) }),
    projectId === null
      ? undefined
      : client.invalidateQueries({ queryKey: generationsKey(userId, projectId) }),
    client.invalidateQueries({ queryKey: projectsKey(userId) }),
  ]);
}

/**
 * Every write goes through this one door: it stops when the session ends, is not optimistic (the screen shows what
 * the server holds, also after an ambiguous failure) and asks for the project again once the answer is in.
 */
function useWrite<V, R>(
  projectIdOf: (variables: V) => string | null,
  run: (variables: V, signal: AbortSignal) => Promise<R>,
) {
  const client = useQueryClient();
  const me = useMe();
  const mutation = useMutation({
    mutationFn: (variables: V): Promise<R> => whileSignedIn((signal) => run(variables, signal)),
    onMutate: () => sessionGeneration(),
    onSettled: (_data, _error, variables, generation) =>
      generation === undefined ? undefined : refresh(client, me.id, projectIdOf(variables), generation),
  });
  // `isPending` only changes after a render, so two clicks in one frame would both pass an `isPending` check. This
  // ref is synchronous: while a write of this hook is in flight, another call does nothing (rules/frontend.md section 2).
  const inFlight = useRef(false);
  const guarded = (variables: V, options?: MutateOptions<R, Error, V, number>): void => {
    if (inFlight.current) return;
    inFlight.current = true;
    const merged: MutateOptions<R, Error, V, number> = {
      ...options,
      onSettled: (...args) => {
        inFlight.current = false;
        options?.onSettled?.(...args);
      },
    };
    mutation.mutate(variables, merged);
  };
  return { ...mutation, mutate: guarded };
}

/** A request body that is a file, typed the way the generated client declares an `application/octet-stream` body. */
const asBody = (file: Blob): string => file as unknown as string;
const OCTET = { "Content-Type": "application/octet-stream" } as const;

export const useCreateProject = () =>
  useWrite<{ name: string; brief: Brief }, ProjectOut>(
    () => null,
    async (v, signal) => unwrap(await api.POST("/api/interior/projects", { body: v, signal })),
  );

export const useDeleteProject = () =>
  useWrite<{ projectId: string }, void>(
    () => null,
    async (v, signal) =>
      unwrapEmpty(
        await api.DELETE("/api/interior/projects/{project_id}", {
          params: { path: { project_id: v.projectId } },
          signal,
        }),
      ),
  );

export const useUpdateProject = () =>
  useWrite<{ projectId: string; name: string; brief: Brief }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.PUT("/api/interior/projects/{project_id}", {
          params: { path: { project_id: v.projectId } },
          body: { name: v.name, brief: v.brief },
          signal,
        }),
      ),
  );

export const useAddItem = () =>
  useWrite<{ projectId: string; item: CustomItemIn }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/items", {
          params: { path: { project_id: v.projectId } },
          body: v.item,
          signal,
        }),
      ),
  );

export const useUpdateItem = () =>
  useWrite<{ projectId: string; itemId: string; item: CustomItemIn }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.PUT("/api/interior/projects/{project_id}/items/{item_id}", {
          params: { path: { project_id: v.projectId, item_id: v.itemId } },
          body: v.item,
          signal,
        }),
      ),
  );

export const useDeleteItem = () =>
  useWrite<{ projectId: string; itemId: string }, void>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrapEmpty(
        await api.DELETE("/api/interior/projects/{project_id}/items/{item_id}", {
          params: { path: { project_id: v.projectId, item_id: v.itemId } },
          signal,
        }),
      ),
  );

export const useUploadSource = () =>
  useWrite<{ projectId: string; file: Blob }, MediaRef>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/source", {
          params: { path: { project_id: v.projectId } },
          body: asBody(v.file),
          bodySerializer: (body) => body,
          headers: OCTET,
          signal,
        }),
      ),
  );

export const useUploadItemPhoto = () =>
  useWrite<{ projectId: string; itemId: string; file: Blob }, MediaRef>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.PUT("/api/interior/projects/{project_id}/items/{item_id}/photo", {
          params: { path: { project_id: v.projectId, item_id: v.itemId } },
          body: asBody(v.file),
          bodySerializer: (body) => body,
          headers: OCTET,
          signal,
        }),
      ),
  );

export const useSelectProduct = () =>
  useWrite<
    { projectId: string; provider: string; productId: string; variantId: string; quantity: number },
    ProjectOut
  >(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/selections", {
          params: { path: { project_id: v.projectId } },
          body: {
            provider: v.provider,
            product_id: v.productId,
            variant_id: v.variantId,
            quantity: v.quantity,
          },
          signal,
        }),
      ),
  );

export const useSetQuantity = () =>
  useWrite<{ projectId: string; selectionId: string; quantity: number }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.PUT("/api/interior/projects/{project_id}/selections/{selection_id}", {
          params: { path: { project_id: v.projectId, selection_id: v.selectionId } },
          body: { quantity: v.quantity },
          signal,
        }),
      ),
  );

export const useRemoveSelection = () =>
  useWrite<{ projectId: string; selectionId: string }, void>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrapEmpty(
        await api.DELETE("/api/interior/projects/{project_id}/selections/{selection_id}", {
          params: { path: { project_id: v.projectId, selection_id: v.selectionId } },
          signal,
        }),
      ),
  );

export const useRefreshSelection = () =>
  useWrite<{ projectId: string; selectionId: string }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/selections/{selection_id}/refresh", {
          params: { path: { project_id: v.projectId, selection_id: v.selectionId } },
          signal,
        }),
      ),
  );

export const useSaveRevision = () =>
  useWrite<{ projectId: string }, ProjectOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/revisions", {
          params: { path: { project_id: v.projectId } },
          signal,
        }),
      ),
  );

/** `key` is the click's `Idempotency-Key`: the same key on a retry after a lost answer can never start a second paid operation. */
export const useStartGeneration = () =>
  useWrite<{ projectId: string; revisionId: string; key: string }, GenerationOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/generations", {
          params: { path: { project_id: v.projectId }, header: { "Idempotency-Key": v.key } },
          body: { revision_id: v.revisionId },
          signal,
        }),
      ),
  );

export const useCancelGeneration = () =>
  useWrite<{ projectId: string; generationId: string }, GenerationOut>(
    (v) => v.projectId,
    async (v, signal) =>
      unwrap(
        await api.POST("/api/interior/projects/{project_id}/generations/{generation_id}/cancel", {
          params: { path: { project_id: v.projectId, generation_id: v.generationId } },
          signal,
        }),
      ),
  );
