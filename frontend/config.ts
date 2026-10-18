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
  /** Better Stack Errors DSN for the browser (a public ingest key, ADR 0009). Empty: no error reporting at all. */
  sentryDsn: clean(import.meta.env["VITE_SENTRY_DSN"]),
  /**
   * Paddle.js client-side token (public by design: it can only open a checkout; test_/live_ prefix). Empty: the SPA
   * offers no purchase and `/pay` says so. Never an API key or the webhook secret.
   */
  paddleClientToken: clean(import.meta.env["VITE_PADDLE_CLIENT_TOKEN"]),
  /** `sandbox` (default) or `production`: which Paddle environment the client token belongs to. */
  paddleEnvironment:
    clean(import.meta.env["VITE_PADDLE_ENVIRONMENT"]) === "production" ? "production" : "sandbox",
  /** The deployed release (the image tag / commit), so errors group per release. */
  release: clean(import.meta.env["VITE_RELEASE"]) || "local",
  environment: clean(import.meta.env["VITE_ENVIRONMENT"]) || "development",
} as const;
