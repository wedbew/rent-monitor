import { describe, expect, it } from "vitest";

import { ApiError, TransportError } from "./errors";
import {
  clearTenantState,
  createQueryClient,
  DEFAULT_STALE_MS,
  isTransient,
  MAX_READ_RETRIES,
  retryDelayMs,
  shouldRetryRead,
} from "./query";

describe("query defaults", () => {
  it("never retries a mutation", () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false);
  });

  it("retries a read at most twice, on network errors, timeouts and 5xx only", () => {
    expect(shouldRetryRead(0, new TransportError("network"))).toBe(true);
    expect(shouldRetryRead(1, new TransportError("timeout"))).toBe(true);
    expect(shouldRetryRead(0, new ApiError(503, null))).toBe(true);
    expect(shouldRetryRead(0, new ApiError(500, null))).toBe(true);
    expect(shouldRetryRead(MAX_READ_RETRIES, new TransportError("network"))).toBe(false);
  });

  it("never retries a 4xx, an abort or an unknown error", () => {
    for (const status of [400, 401, 403, 404, 409, 422, 429]) {
      expect(shouldRetryRead(0, new ApiError(status, null)), String(status)).toBe(false);
    }
    expect(shouldRetryRead(0, new TransportError("aborted"))).toBe(false);
    expect(isTransient(new TransportError("invalid-response"))).toBe(false);
    expect(shouldRetryRead(0, new Error("boom"))).toBe(false);
  });

  it("backs off with jitter inside a bound", () => {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const delay = retryDelayMs(attempt);
      expect(delay).toBeGreaterThanOrEqual(500);
      expect(delay).toBeLessThanOrEqual(8000);
    }
  });

  it("documents the default freshness and does not refetch on focus", () => {
    const options = createQueryClient().getDefaultOptions().queries;
    expect(options?.staleTime).toBe(DEFAULT_STALE_MS);
    expect(options?.refetchOnWindowFocus).toBe(false);
  });

  it("empties the whole cache on sign-out so the next person sees nothing of the last", () => {
    const client = createQueryClient();
    client.setQueryData(["audits"], { items: [1] });
    client.setQueryData(["me"], { id: "a" });
    clearTenantState(client);
    expect(client.getQueryCache().getAll()).toHaveLength(0);
  });
});
