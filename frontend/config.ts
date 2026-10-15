/**
 * Public build-time configuration. Every `VITE_*` value is embedded in the bundle and readable by anyone: only
 * values that are public by nature belong here (the Google OAuth *client id* is; no key, secret or token ever is).
 * An empty value means the capability is not configured and the UI does not offer it (no fake button).
 */
function clean(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export const config = {
  /** Google Identity Services client id (callback mode, no redirect URI, no secret). Empty: Google sign-in is hidden. */
  googleClientId: clean(import.meta.env["VITE_GOOGLE_CLIENT_ID"]),
} as const;
