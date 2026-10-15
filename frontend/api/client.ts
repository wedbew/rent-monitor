import createClient from "openapi-fetch";

import { ApiError, asProblem, TransportError } from "./errors";
import { emitSessionExpired } from "./session-events";
import type { paths } from "./schema.generated";

/** Every request has a deadline; a caller's own signal (route change, unmount) still wins. */
export const REQUEST_TIMEOUT_MS = 15_000;

type FetchImpl = (request: Request) => Promise<Response>;

export interface ApiOptions {
  readonly fetch?: FetchImpl;
  readonly timeoutMs?: number;
  readonly baseUrl?: string;
}

/**
 * The browser always calls relative `/api` URLs on its own origin: the session is an HttpOnly cookie the page
 * cannot read, and the server checks `Origin` on unsafe methods. Nothing here stores or sends a token.
 */
export function createApi({
  fetch: impl = (request) => fetch(request),
  timeoutMs = REQUEST_TIMEOUT_MS,
  baseUrl = window.location.origin,
}: ApiOptions = {}) {
  const timed: FetchImpl = async (request) => {
    // Own controller and timer instead of AbortSignal.timeout/any: they behave differently across realms (jsdom and
    // undici) and a composite signal can be collected before it fires. The deadline covers the headers AND the
    // body: the body is read here, inside the same race, so a server that sends headers and then stalls is a
    // timeout like any other, and openapi-fetch only ever parses a body that is already complete.
    // Cancelled before it started (a route already left): nothing is sent.
    if (request.signal.aborted) throw new TransportError("aborted", { cause: request.signal.reason });
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onCallerAbort = () => controller.abort();
    request.signal.addEventListener("abort", onCallerAbort, { once: true });
    // The race makes the deadline and a caller's abort hold whatever `impl` (or the body stream) does with the signal.
    const stopped = new Promise<never>((_, reject) => {
      const stop = () => reject(new DOMException("aborted", "AbortError"));
      if (controller.signal.aborted) stop();
      else controller.signal.addEventListener("abort", stop, { once: true });
    });
    stopped.catch(() => undefined); // settled by the race; never an unhandled rejection on the success path
    let response: Response;
    let text: string;
    try {
      response = await Promise.race([impl(new Request(request, { signal: controller.signal })), stopped]);
      text = await Promise.race([response.text(), stopped]);
    } catch (error) {
      if (request.signal.aborted) throw new TransportError("aborted", { cause: error });
      if (timedOut) throw new TransportError("timeout", { cause: error });
      throw new TransportError("network", { cause: error });
    } finally {
      clearTimeout(timer);
      request.signal.removeEventListener("abort", onCallerAbort);
    }
    return buffered(response, text);
  };
  return createClient<paths>({ baseUrl, fetch: timed });
}

/** Statuses whose response may not carry a body (the Response constructor rejects one). */
const NO_BODY = new Set([101, 103, 204, 205, 304]);

/**
 * The complete answer, re-wrapped for openapi-fetch. A success that is not JSON is not an API answer (a captive
 * portal, a truncated proxy reply): it fails here as `invalid-response` instead of a raw `SyntaxError` later. An
 * error status keeps any body, HTML included: `unwrap` turns it into an ApiError without a problem.
 */
function buffered(response: Response, text: string): Response {
  if (response.ok && text !== "" && !NO_BODY.has(response.status)) {
    try {
      JSON.parse(text);
    } catch (error) {
      throw new TransportError("invalid-response", { cause: error });
    }
  }
  return new Response(NO_BODY.has(response.status) ? null : text, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
}

export type Api = ReturnType<typeof createApi>;

export const api: Api = createApi();

interface Result<T> {
  readonly data?: T | undefined;
  readonly error?: unknown;
  readonly response: Response;
}

function retryAfter(response: Response): number | null {
  const raw = response.headers.get("retry-after");
  const seconds = raw === null ? Number.NaN : Number.parseInt(raw, 10);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

/**
 * Turn an openapi-fetch result into the success value or a thrown `ApiError`. An error status without a problem
 * body (a proxy's HTML page, for example) is still an `ApiError`, with `problem: null`.
 */
export function unwrap<T>(result: Result<T>): T {
  const { response } = result;
  if (!response.ok) {
    const problem = asProblem(result.error);
    if (response.status === 401 && problem?.code === "UNAUTHENTICATED") emitSessionExpired();
    throw new ApiError(response.status, problem, retryAfter(response));
  }
  return result.data as T;
}

/** The same, for operations whose success carries no body (204). */
export function unwrapEmpty(result: Result<unknown>): void {
  unwrap(result);
}
