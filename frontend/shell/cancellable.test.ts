import { describe, expect, it } from "vitest";

import { whileSignedIn } from "./cancellable";
import { TransportError } from "../api/errors";
import { advanceSessionGeneration, runTenantCleanups } from "./tenant";

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

describe("whileSignedIn: an operation that ignores the abort signal", () => {
  const never = () => new Promise<never>(() => undefined);

  it("rejects with a typed cancellation when the session ends, without waiting for the operation", async () => {
    const pending = whileSignedIn(never);
    runTenantCleanups();
    await expect(pending).rejects.toMatchObject({ name: "TransportError", kind: "aborted" });
  });

  it("never delivers a late success of the previous session", async () => {
    let finish: (value: string) => void = () => undefined;
    const pending = whileSignedIn(() => new Promise<string>((resolve) => (finish = resolve)));
    runTenantCleanups();
    finish("late result");
    await expect(pending).rejects.toMatchObject({ kind: "aborted" });
  });

  it("never delivers a late failure of the previous session, and leaves no unhandled rejection", async () => {
    let fail: (error: Error) => void = () => undefined;
    const pending = whileSignedIn(() => new Promise<string>((_resolve, reject) => (fail = reject)));
    runTenantCleanups();
    await expect(pending).rejects.toMatchObject({ kind: "aborted" });
    fail(new Error("late boom")); // must not surface anywhere
    await Promise.resolve();
  });

  it("rejects a result that arrives after the session generation moved, even with no cleanup run", async () => {
    let finish: (value: string) => void = () => undefined;
    let seen: AbortSignal | null = null;
    const pending = whileSignedIn((signal) => {
      seen = signal;
      return new Promise<string>((resolve) => (finish = resolve));
    });
    advanceSessionGeneration(); // A -> B without the cleanup having reached this request
    finish("A's result");
    await expect(pending).rejects.toMatchObject({ kind: "aborted" });
    expect((seen as unknown as AbortSignal).aborted).toBe(true); // the previous session's request is stopped too
  });

  it("runs the work with a live signal while the session is current", async () => {
    const controllerless = whileSignedIn((signal) => Promise.resolve(signal.aborted));
    expect(await controllerless).toBe(false);
  });

  // A released cleanup no longer aborts the finished request's signal: that is how a leak would show.
  it("repeated cleanups are harmless, and the cleanup is released on success and on failure", async () => {
    let seen: AbortSignal | null = null;
    await whileSignedIn((signal) => {
      seen = signal;
      return Promise.resolve(1);
    });
    runTenantCleanups();
    runTenantCleanups();
    expect((seen as unknown as AbortSignal).aborted).toBe(false);
    let failed: AbortSignal | null = null;
    const failing = whileSignedIn((signal) => {
      failed = signal;
      return Promise.reject(new Error("x"));
    });
    await expect(failing).rejects.toThrow("x");
    runTenantCleanups();
    expect((failed as unknown as AbortSignal).aborted).toBe(false);
  });

  it("an operation that throws before returning a promise is rejected and its cleanup released", async () => {
    let seen: AbortSignal | null = null;
    const throwing = whileSignedIn((signal): Promise<number> => {
      seen = signal;
      throw new Error("sync");
    });
    await expect(throwing).rejects.toThrow("sync");
    runTenantCleanups();
    expect((seen as unknown as AbortSignal).aborted).toBe(false);
  });

  it("passes a real failure through while the session is current", async () => {
    await expect(whileSignedIn(() => Promise.reject(new TransportError("timeout")))).rejects.toMatchObject({
      kind: "timeout",
    });
  });
});
