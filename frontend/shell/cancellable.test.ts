import { describe, expect, it } from "vitest";

import { whileSignedIn } from "./cancellable";
import { runTenantCleanups } from "./tenant";

describe("whileSignedIn", () => {
  it("aborts the request when the session ends, and says so to the request", async () => {
    let seen: AbortSignal | null = null;
    const pending = whileSignedIn(
      (signal) =>
        new Promise<string>((_resolve, reject) => {
          seen = signal;
          signal.addEventListener("abort", () => reject(new Error("aborted")));
        }),
    );
    expect(seen).not.toBeNull();
    expect((seen as unknown as AbortSignal).aborted).toBe(false);
    runTenantCleanups();
    await expect(pending).rejects.toThrow("aborted");
    expect((seen as unknown as AbortSignal).aborted).toBe(true);
  });

  it("stops listening once the request is done, so a later session end touches nothing", async () => {
    let seen: AbortSignal | null = null;
    const value = await whileSignedIn((signal) => {
      seen = signal;
      return Promise.resolve(42);
    });
    expect(value).toBe(42);
    runTenantCleanups();
    expect((seen as unknown as AbortSignal).aborted).toBe(false);
  });

  it("releases the cleanup when the request fails too", async () => {
    let seen: AbortSignal | null = null;
    await expect(
      whileSignedIn((signal) => {
        seen = signal;
        return Promise.reject(new Error("boom"));
      }),
    ).rejects.toThrow("boom");
    runTenantCleanups();
    expect((seen as unknown as AbortSignal).aborted).toBe(false);
  });
});
