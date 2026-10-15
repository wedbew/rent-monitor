import { act, renderHook } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runTenantCleanups } from "../../../shell/tenant";
import { useAuditProgress } from "./useAuditProgress";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CLOSED = 2;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  private readonly listeners = new Map<string, ((event: Event) => void)[]>();
  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {
    this.closed = true;
  }
  emit(type: string, id: string, data: object) {
    const event = new MessageEvent(type, { data: JSON.stringify(data), lastEventId: id });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

const URL = "/api/audits/a/events";

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
});

afterEach(() => {
  runTenantCleanups();
  vi.unstubAllGlobals();
});

describe("useAuditProgress", () => {
  it("opens one stream under strict mode's double mount", () => {
    renderHook(() => useAuditProgress(URL, { onTerminal: () => undefined }), { wrapper: StrictMode });
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("opens nothing until there is a stream to watch (the audit is still being read)", () => {
    renderHook(() => useAuditProgress(null, { onTerminal: () => undefined }));
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("copies stage and percentage from the frames, lists each stage once in the order seen", () => {
    const { result } = renderHook(() => useAuditProgress(URL, { onTerminal: () => undefined }));
    const source = FakeEventSource.instances[0];
    act(() => {
      source?.emit("progress", "1", { stage: "fetch", pct: 5 });
      source?.emit("progress", "2", { stage: "extract", pct: 15 });
      source?.emit("progress", "3", { stage: "extract", pct: 20 });
    });
    expect(result.current.stages).toEqual(["fetch", "extract"]);
    expect(result.current.stage).toBe("extract");
    expect(result.current.pct).toBe(20);
    expect(result.current.terminal).toBeNull();
  });

  it("reports the terminal frame once, and nothing after it changes the state", () => {
    const onTerminal = vi.fn();
    const { result } = renderHook(() => useAuditProgress(URL, { onTerminal }));
    const source = FakeEventSource.instances[0];
    act(() => {
      source?.emit("progress", "1", { stage: "fetch", pct: 5 });
      source?.emit("done", "2", { status: "succeeded", pct: 100, stage: "persist" });
      source?.emit("progress", "3", { stage: "vision", pct: 35 });
    });
    expect(onTerminal).toHaveBeenCalledTimes(1);
    expect(result.current.terminal?.kind).toBe("done");
    expect(result.current.stages).toEqual(["fetch"]);
  });

  it("tells the caller about connection changes", () => {
    const onConnection = vi.fn();
    renderHook(() => useAuditProgress(URL, { onTerminal: () => undefined, onConnection }));
    const source = FakeEventSource.instances[0];
    act(() => {
      source?.onopen?.();
    });
    expect(onConnection).toHaveBeenCalledWith("live");
  });
});
