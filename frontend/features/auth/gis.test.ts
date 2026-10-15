import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { GisId } from "./gis";

const fakeGis = (): GisId => ({ initialize: vi.fn(), renderButton: vi.fn(), cancel: vi.fn() });

async function freshLoader() {
  vi.resetModules();
  return (await import("./gis")).loadGis;
}

beforeEach(() => {
  delete window.google;
  document.head.querySelectorAll("script[src*=gsi]").forEach((s) => s.remove());
});
afterEach(() => {
  vi.useRealTimers();
  delete window.google;
});

describe("loadGis", () => {
  it("uses the API that is already on the page without loading anything", async () => {
    const gis = fakeGis();
    window.google = { accounts: { id: gis } };
    const loadGis = await freshLoader();
    await expect(loadGis()).resolves.toBe(gis);
    expect(document.head.querySelector("script[src*=gsi]")).toBeNull();
  });

  it("loads Google's script once and resolves when it brings the API", async () => {
    const loadGis = await freshLoader();
    const first = loadGis();
    const second = loadGis();
    const scripts = document.head.querySelectorAll<HTMLScriptElement>("script[src*=gsi]");
    expect(scripts).toHaveLength(1);
    expect(scripts[0]?.src).toBe("https://accounts.google.com/gsi/client");
    const gis = fakeGis();
    window.google = { accounts: { id: gis } };
    scripts[0]?.onload?.(new Event("load"));
    await expect(first).resolves.toBe(gis);
    await expect(second).resolves.toBe(gis);
  });

  it("rejects, and can be tried again, when the script is blocked", async () => {
    const loadGis = await freshLoader();
    const attempt = loadGis();
    document.head.querySelector<HTMLScriptElement>("script[src*=gsi]")?.onerror?.(new Event("error"));
    await expect(attempt).rejects.toThrow("failed to load");
    expect(document.head.querySelector("script[src*=gsi]")).toBeNull();
    const again = loadGis();
    expect(document.head.querySelector("script[src*=gsi]")).not.toBeNull();
    document.head.querySelector<HTMLScriptElement>("script[src*=gsi]")?.onerror?.(new Event("error"));
    await expect(again).rejects.toThrow();
  });

  it("rejects when the script loads without the API", async () => {
    const loadGis = await freshLoader();
    const attempt = loadGis();
    document.head.querySelector<HTMLScriptElement>("script[src*=gsi]")?.onload?.(new Event("load"));
    await expect(attempt).rejects.toThrow("without the API");
  });

  it("never hangs: it gives up after ten seconds", async () => {
    vi.useFakeTimers();
    const loadGis = await freshLoader();
    const attempt = loadGis();
    const assertion = expect(attempt).rejects.toThrow("timed out");
    await vi.advanceTimersByTimeAsync(10_001);
    await assertion;
  });
});
