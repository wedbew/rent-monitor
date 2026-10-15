/**
 * The API's emails link to `/login/email#t=<token>`, `/signup/verify#t=<token>` and `/password/reset#t=<token>`.
 * A fragment is never sent to a server, so proxies, mail scanners and logs do not see the token; this module keeps
 * it that way on the client: it is read ONCE when the app boots, removed from the address bar with
 * `history.replaceState` (so it is not in history, a screenshot, a shared URL or `document.referrer`), and held in
 * memory only. It is never written to storage, never put in a query key, and never passed to analytics or error
 * tracking (the redaction in #280 drops fragments too).
 */
const FRAGMENT = /^#t=([A-Za-z0-9_-]{20,128})$/;

let captured: string | null = null;

/** Call once, before React renders. Safe to call again: a missing fragment leaves the captured token alone. */
export function captureFragmentToken(): void {
  const match = FRAGMENT.exec(window.location.hash);
  if (window.location.hash === "") return;
  captured = match?.[1] ?? null;
  window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
}

/** The token from the link, if the page was opened from one. Reading does not consume it (React may render twice). */
export function readCapturedToken(): string | null {
  return captured;
}

/** Forget it once it has been used, or when the page goes away. */
export function clearCapturedToken(): void {
  captured = null;
}
