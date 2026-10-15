import { QueryClient } from "@tanstack/react-query";

import { ApiError, TransportError } from "./errors";

/** Reads are retried at most twice, and only when the failure may be transient. */
export const MAX_READ_RETRIES = 2;
/**
 * Server state is fresh for 30 s: enough that moving between pages does not refetch everything, short enough that
 * credits and audit status never look stale. Queries that need otherwise (an audit being processed, the packs list)
 * set their own `staleTime` next to the hook and say why.
 */
export const DEFAULT_STALE_MS = 30_000;

export function isTransient(error: unknown): boolean {
  if (error instanceof TransportError) return error.kind === "network" || error.kind === "timeout";
  if (error instanceof ApiError) return error.status >= 500;
  return false;
}

/** 4xx (validation, 401, 403, 404, 409, 429) never helps by asking again. */
export function shouldRetryRead(failureCount: number, error: unknown): boolean {
  return failureCount < MAX_READ_RETRIES && isTransient(error);
}

export function retryDelayMs(attempt: number): number {
  const base = Math.min(1000 * 2 ** attempt, 8000);
  return base / 2 + Math.random() * (base / 2);
}

/**
 * One cache per signed-in person: `clearTenantState` empties it on sign-out and on a 401 so the next person never
 * sees the last one's audits. Mutations are never retried: a charge or a purchase must not be repeated by a library.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: shouldRetryRead,
        retryDelay: retryDelayMs,
        staleTime: DEFAULT_STALE_MS,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}

export function clearTenantState(client: QueryClient): void {
  void client.cancelQueries();
  client.clear();
}
