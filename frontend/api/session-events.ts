/**
 * The API answered 401 `UNAUTHENTICATED` to a request that needed a session: it ended (expired, revoked, signed
 * out elsewhere). `unwrap` announces it here; the session boundary (shell/session.tsx) reacts once for the whole
 * app: tenant caches are cleared, streams closed, and the person is sent to sign in.
 */
type Listener = () => void;
const listeners = new Set<Listener>();

export function onSessionExpired(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function emitSessionExpired(): void {
  for (const listener of [...listeners]) listener();
}
