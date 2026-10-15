/**
 * Tells the other tabs of this browser that the session changed. BroadcastChannel where it exists; a `storage`
 * event otherwise. Only a signal travels ("signed-out" and a time): no token, no session id, no personal data, and
 * nothing that identifies the person is ever written to storage.
 */
export type SessionSignal = "signed-in" | "signed-out";

const CHANNEL = "renti-session";
const STORAGE_KEY = "renti-session-signal";

export function sendSessionSignal(signal: SessionSignal): void {
  try {
    if ("BroadcastChannel" in window) {
      const channel = new BroadcastChannel(CHANNEL);
      channel.postMessage(signal);
      channel.close();
      return;
    }
    localStorage.setItem(STORAGE_KEY, `${signal}:${Date.now()}`);
  } catch {
    // No broadcast possible (storage blocked): other tabs learn on their next request (a 401).
  }
}

export function onSessionSignal(listener: (signal: SessionSignal) => void): () => void {
  const parse = (value: unknown): SessionSignal | null =>
    value === "signed-in" || value === "signed-out" ? value : null;
  let channel: BroadcastChannel | null = null;
  if ("BroadcastChannel" in window) {
    channel = new BroadcastChannel(CHANNEL);
    channel.onmessage = (event: MessageEvent<unknown>) => {
      const signal = parse(event.data);
      if (signal !== null) listener(signal);
    };
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY || event.newValue === null) return;
    const signal = parse(event.newValue.split(":")[0]);
    if (signal !== null) listener(signal);
  };
  window.addEventListener("storage", onStorage);
  return () => {
    channel?.close();
    window.removeEventListener("storage", onStorage);
  };
}
