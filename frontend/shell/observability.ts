/**
 * Unexpected browser errors to Better Stack Errors through the Sentry SDK (ADR 0009, audit F15, #280).
 *
 * Off unless a DSN is configured at build time (`VITE_SENTRY_DSN`, a public ingest key by design): then nothing is
 * loaded, nothing is sent. When on, the SDK is loaded lazily (it is not in the first page's bundle), session replay
 * and tracing are off, and every event and breadcrumb passes `scrubEvent` / `scrubBreadcrumb` first. If scrubbing
 * itself fails the event is dropped, never sent as it was. This mirrors the backend's `rm_core.observability`
 * (L-013): no request data, no query strings or URL fragments, no user, no breadcrumb data, and no emails, tokens
 * or Otodom listing addresses inside text.
 */
// GDPR[processor]: unexpected errors go to Better Stack (Sentry SDK) only after scrubbing; no personal data (RM-280)
import type * as SentryApi from "./sentry";

import { ApiError } from "../api/errors";
import { config } from "../config";

export const REDACTED = "[redacted]";

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/g;
const JWT = /\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*/g;
const BEARER = /\bbearer\s+[A-Za-z0-9._~+/=-]+/gi;
/** `#t=<link token>`, `token=…`, `credential=…`, `code=…` and the like, in URLs or messages. */
const PARAM =
  /((?:^|[#?&;\s])(?:t|token|id_token|credential|code|session|key|secret|password)=)[^&\s"'#]+/gim;
/** A listing address or its Otodom id is what the person analysed: not error context. */
const OTODOM_URL = /https?:\/\/(?:www\.)?otodom\.pl\/[^\s"']*/gi;
const OTODOM_ID = /\bID[0-9A-Za-z]{3,20}\b/g;

export function redactText(text: string): string {
  return text
    .replace(JWT, REDACTED)
    .replace(BEARER, `Bearer ${REDACTED}`)
    .replace(PARAM, `$1${REDACTED}`)
    .replace(OTODOM_URL, "[listing]")
    .replace(OTODOM_ID, "[listing]")
    .replace(EMAIL, "[email]");
}

/** A page URL without its query string and fragment (both can carry tokens or what was typed). */
export function scrubUrl(url: string): string {
  const cut = url.search(/[?#]/);
  return redactText(cut === -1 ? url : url.slice(0, cut));
}

type Json = Record<string, unknown>;
const isRecord = (value: unknown): value is Json =>
  typeof value === "object" && value !== null && !Array.isArray(value);

function scrubValue(value: unknown, depth = 0): unknown {
  if (depth > 6) return REDACTED;
  if (typeof value === "string") return redactText(value);
  if (Array.isArray(value)) return value.map((item) => scrubValue(item, depth + 1));
  if (isRecord(value))
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, scrubValue(item, depth + 1)]));
  return value;
}

/** Mutates and returns the event; throws on anything it cannot handle (the caller then drops the event). */
export function scrubEvent<E extends Json>(event: E): E {
  const record: Json = event;
  // The page and request: path only; no headers, cookies, query or body.
  const request = record["request"];
  if (isRecord(request)) {
    record["request"] = typeof request["url"] === "string" ? { url: scrubUrl(request["url"]) } : {};
  }
  // Nobody: the SPA never identifies the person to the error tracker.
  delete record["user"];
  if (typeof record["message"] === "string") record["message"] = redactText(record["message"]);
  const exception = record["exception"];
  const values = isRecord(exception) ? exception["values"] : undefined;
  if (Array.isArray(values)) {
    for (const item of values) {
      if (!isRecord(item)) continue;
      if (typeof item["value"] === "string") item["value"] = redactText(item["value"]);
      const frames = isRecord(item["stacktrace"]) ? item["stacktrace"]["frames"] : undefined;
      if (Array.isArray(frames)) for (const frame of frames) if (isRecord(frame)) delete frame["vars"];
    }
  }
  const breadcrumbs = record["breadcrumbs"];
  if (Array.isArray(breadcrumbs))
    record["breadcrumbs"] = (breadcrumbs as unknown[]).map((b) => (isRecord(b) ? scrubBreadcrumb(b) : b));
  for (const key of ["extra", "contexts", "tags"])
    if (isRecord(record[key])) record[key] = scrubValue(record[key]);
  return event;
}

/** A breadcrumb keeps its category and level; its data (URLs, bodies, elements) is dropped, its message redacted. */
export function scrubBreadcrumb<B extends Json>(breadcrumb: B): B {
  const record: Json = breadcrumb;
  delete record["data"];
  if (typeof record["message"] === "string") record["message"] = redactText(record["message"]);
  return breadcrumb;
}

/** Scrub, or drop the event if scrubbing fails: an unscrubbed event never leaves the browser. */
export function safeScrub<E extends Json>(event: E): E | null {
  try {
    return scrubEvent(event);
  } catch {
    return null;
  }
}

interface Reporter {
  captureException(error: unknown, context?: { tags?: Record<string, string> }): unknown;
}

let reporter: Reporter | null = null;

/** Start error reporting if a DSN is configured; a no-op (nothing loaded) otherwise. Call once, at startup. */
export async function initObservability(
  options: {
    readonly dsn?: string;
    readonly release?: string;
    readonly load?: () => Promise<SentryModule>;
  } = {},
): Promise<boolean> {
  const dsn = options.dsn ?? config.sentryDsn;
  if (dsn === "") return false;
  const Sentry = await (options.load ?? loadSentry)();
  Sentry.init({
    dsn,
    release: options.release ?? config.release,
    environment: config.environment,
    tracesSampleRate: 0,
    // Collected at the source: nothing about the person or the request. The scrubber below is the second layer.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
    },
    beforeSend: (event) => safeScrub(event as unknown as Json) as unknown as typeof event | null,
    beforeBreadcrumb: (breadcrumb) => {
      scrubBreadcrumb(breadcrumb as unknown as Json);
      return breadcrumb;
    },
  });
  reporter = Sentry;
  return true;
}

type SentryModule = Pick<typeof SentryApi, "init" | "captureException">;
const loadSentry = (): Promise<SentryModule> => import("./sentry");

/**
 * Report an unexpected error (a route that failed to render). An API answer carries its request id as a tag, so
 * support can find it in the server logs; the problem body itself is not sent.
 */
export function reportError(error: unknown): void {
  if (reporter === null) return;
  const tags: Record<string, string> = {};
  if (error instanceof ApiError) {
    tags["http_status"] = String(error.status);
    if (error.code !== null) tags["problem_code"] = error.code;
    if (error.requestId !== null) tags["request_id"] = error.requestId;
  }
  reporter.captureException(error, { tags });
}

/** Test support: forget the reporter. */
export function resetObservability(): void {
  reporter = null;
}
