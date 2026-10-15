import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runTenantCleanups } from "../../../shell/tenant";
import type { Frame } from "./frames";
import { type Connection, openStreamCount, watch } from "./streams";

/** The parts of EventSource the app uses, driven by hand. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CLOSED = 2;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  private readonly listeners = new Map<string, ((event: Event) => void)[]>();

  constructor(
    readonly url: string,
    readonly init?: EventSourceInit,
  ) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: Event) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  emit(type: string, id: string, data: object) {
    const event = new MessageEvent(type, { data: JSON.stringify(data), lastEventId: id });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }

  /** The connection's own `error` event: a plain Event, not a message. */
  drop(readyState: number) {
    this.readyState = readyState;
    this.onerror?.();
    for (const listener of this.listeners.get("error") ?? []) listener(new Event("error"));
  }
}

function latest(): FakeEventSource {
  const source = FakeEventSource.instances.at(0);
  if (source === undefined) throw new Error("no EventSource was opened");
  return source;
}

const URL = "/api/audits/a/events";

function collect() {
  const frames: Frame[] = [];
  const states: Connection[] = [];
  return {
    frames,
    states,
    watcher: { frame: (f: Frame) => frames.push(f), connection: (c: Connection) => states.push(c) },
  };
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.useFakeTimers();
});

afterEach(() => {
  runTenantCleanups();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("shared progress streams", () => {
  it("opens one connection for one analysis, with credentials, however many watch it", () => {
    const a = collect();
    const b = collect();
    watch(URL, a.watcher);
    watch(URL, b.watcher);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.init).toEqual({ withCredentials: true });
  });

  it("a strict-mode remount (unwatch, watch again in the same tick) reuses the connection", async () => {
    const first = collect();
    const stop = watch(URL, first.watcher);
    stop();
    watch(URL, collect().watcher);
    await vi.runAllTimersAsync();
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(FakeEventSource.instances[0]?.closed).toBe(false);
  });

  it("closes the connection once nobody watches", async () => {
    const stop = watch(URL, collect().watcher);
    stop();
    await vi.runAllTimersAsync();
    expect(FakeEventSource.instances[0]?.closed).toBe(true);
    expect(openStreamCount()).toBe(0);
  });

  it("delivers frames in order and drops a replayed id", () => {
    const { frames, watcher } = collect();
    watch(URL, watcher);
    const source = latest();
    source.emit("progress", "1", { stage: "fetch", pct: 5 });
    source.emit("progress", "2", { stage: "extract", pct: 15 });
    source.emit("progress", "2", { stage: "extract", pct: 15 }); // the same id again after a reconnect
    source.emit("progress", "1", { stage: "fetch", pct: 5 });
    expect(frames.map((f) => f.id)).toEqual([1, 2]);
  });

  it("replays what it has seen to a watcher that arrives late", () => {
    watch(URL, collect().watcher);
    const source = latest();
    source.emit("progress", "1", { stage: "fetch", pct: 5 });
    source.emit("progress", "2", { stage: "extract", pct: 15 });
    const late = collect();
    watch(URL, late.watcher);
    expect(late.frames.map((f) => f.stage)).toEqual(["fetch", "extract"]);
  });

  it("closes itself after the terminal frame and reports it once", () => {
    const { frames, watcher } = collect();
    watch(URL, watcher);
    const source = latest();
    source.emit("progress", "1", { stage: "fetch", pct: 5 });
    source.emit("done", "2", { status: "succeeded", pct: 100, stage: "persist" });
    expect(source.closed).toBe(true);
    expect(frames.filter((f) => f.kind === "done")).toHaveLength(1);
    source.drop(FakeEventSource.CLOSED); // closing is not an error once the outcome is known
  });

  it("a server `error` event is a frame; the connection's own error event is not", () => {
    const { frames, states, watcher } = collect();
    watch(URL, watcher);
    const source = latest();
    source.drop(0);
    expect(frames).toEqual([]);
    expect(states.at(-1)).toBe("reconnecting");
    source.emit("error", "7", { code: "RENT_NOT_DEAL", status: "rejected" });
    expect(frames).toHaveLength(1);
    expect(frames[0]).toMatchObject({ kind: "error", code: "RENT_NOT_DEAL" });
  });

  it("tells reconnecting (the browser is retrying) from failed (it gave up)", () => {
    const { states, watcher } = collect();
    watch(URL, watcher);
    const source = latest();
    source.onopen?.();
    expect(states.at(-1)).toBe("live");
    source.drop(0);
    expect(states.at(-1)).toBe("reconnecting");
    source.drop(FakeEventSource.CLOSED);
    expect(states.at(-1)).toBe("failed");
  });

  it("ignores frames it cannot read", () => {
    const { frames, watcher } = collect();
    watch(URL, watcher);
    const source = latest();
    source.emit("progress", "1", { pct: 500 });
    expect(frames[0]?.pct).toBeNull();
    source.emit("message", "2", { stage: "fetch" });
    expect(frames).toHaveLength(1);
  });

  it("a session ending closes every stream", () => {
    watch(URL, collect().watcher);
    watch("/api/audits/b/events", collect().watcher);
    expect(openStreamCount()).toBe(2);
    runTenantCleanups();
    expect(openStreamCount()).toBe(0);
    expect(FakeEventSource.instances.every((s) => s.closed)).toBe(true);
  });
});
