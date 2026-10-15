/**
 * The only parts of the Sentry SDK the app uses, imported by name so the bundler leaves the rest out (the whole
 * package is ~136 kB gzip, over the lazy-chunk budget). Loaded lazily by shell/observability.ts, and only when a
 * DSN is configured. The default integrations are replaced by the four that capture errors: no replay, no
 * tracing, no console or fetch instrumentation beyond what the error itself carries.
 */
import {
  browserApiErrorsIntegration,
  captureException,
  dedupeIntegration,
  globalHandlersIntegration,
  init as sentryInit,
  linkedErrorsIntegration,
} from "@sentry/browser";

type InitOptions = Parameters<typeof sentryInit>[0];

export function init(options: InitOptions): void {
  sentryInit({
    ...options,
    defaultIntegrations: false,
    integrations: [
      globalHandlersIntegration(),
      browserApiErrorsIntegration(),
      linkedErrorsIntegration(),
      dedupeIntegration(),
    ],
  });
}

export { captureException };
