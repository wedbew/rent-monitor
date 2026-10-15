import { registerTenantCleanup } from "../../../shell/tenant";
import { type Frame, isTerminal, parseFrame } from "./frames";

/**
 * One `EventSource` per analysis, shared by everyone who watches it. Two reasons it is not created in a component:
 * React's strict mode mounts, unmounts and mounts again (that must be one connection, not two), and a native
 * `EventSource` that is closed cannot resume, so the frames seen so far are kept and replayed to a late watcher.
 * The browser itself reconnects with `Last-Event-ID` after a dropped connection; frames are deduplicated by id.
 */
export type Connection = "connecting" | "live" | "reconnecting" | "failed";

export interface Watcher {
  frame(frame: Frame): void;
  connection(state: Connection): void;
}

interface Stream {
  source: EventSource;
  frames: Frame[];
  lastId: number;
  state: Connection;
  watchers: Set<Watcher>;
  closing: ReturnType<typeof setTimeout> | null;
}

const MAX_FRAMES = 64;
const streams = new Map<string, Stream>();

function close(url: string): void {
  const stream = streams.get(url);
  if (stream === undefined) return;
  if (stream.closing !== null) clearTimeout(stream.closing);
  stream.source.close();
  streams.delete(url);
}

function setState(stream: Stream, state: Connection): void {
  stream.state = state;
  for (const watcher of stream.watchers) watcher.connection(state);
}

function open(url: string): Stream {
  const source = new EventSource(url, { withCredentials: true });
  const stream: Stream = {
    source,
    frames: [],
    lastId: 0,
    state: "connecting",
    watchers: new Set(),
    closing: null,
  };
  const onFrame = (event: Event) => {
    if (!(event instanceof MessageEvent)) return; // the connection's own `error` event is a plain Event
    const frame = parseFrame(event.type, event.lastEventId, event.data);
    if (frame === null) return;
    if (frame.id !== null) {
      if (frame.id <= stream.lastId) return; // a replay after a reconnect
      stream.lastId = frame.id;
    }
    stream.frames = [...stream.frames, frame].slice(-MAX_FRAMES);
    if (stream.state !== "live") setState(stream, "live");
    for (const watcher of stream.watchers) watcher.frame(frame);
    if (isTerminal(frame)) source.close(); // the stream is over; the final state is re-read from the API
  };
  source.addEventListener("progress", onFrame);
  source.addEventListener("done", onFrame);
  source.addEventListener("error", onFrame);
  source.onopen = () => setState(stream, "live");
  source.onerror = () => {
    if (stream.frames.some(isTerminal)) return;
    // CONNECTING: the browser is retrying. CLOSED: it gave up (an HTTP error answer); the caller falls back to polling.
    setState(stream, source.readyState === EventSource.CLOSED ? "failed" : "reconnecting");
  };
  streams.set(url, stream);
  return stream;
}

/**
 * Start watching. Frames already received are replayed first. The returned function stops watching; when nobody is
 * left the connection closes after a tick, so a strict-mode remount (or a quick navigation back) reuses it.
 */
export function watch(url: string, watcher: Watcher): () => void {
  const stream = streams.get(url) ?? open(url);
  if (stream.closing !== null) {
    clearTimeout(stream.closing);
    stream.closing = null;
  }
  stream.watchers.add(watcher);
  watcher.connection(stream.state);
  for (const frame of stream.frames) watcher.frame(frame);
  return () => {
    stream.watchers.delete(watcher);
    if (stream.watchers.size === 0 && stream.closing === null) {
      stream.closing = setTimeout(() => close(url), 0);
    }
  };
}

/** Sign-out, expiry or account deletion: nothing of one person's streams may outlive their session. */
registerTenantCleanup(() => {
  for (const url of [...streams.keys()]) close(url);
});

/** Test support: how many connections are open right now. */
export function openStreamCount(): number {
  return streams.size;
}
