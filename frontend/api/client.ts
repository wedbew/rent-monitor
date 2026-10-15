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
    // undici) and a composite signal can be collected before it fires. The timer also bounds a slow response body;
    // it is cleared only when the request fails first.
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    const onCallerAbort = () => controller.abort();
    if (request.signal.aborted) controller.abort();
    else request.signal.addEventListener("abort", onCallerAbort, { once: true });
    // The race makes the deadline and a caller's abort hold whatever `impl` does with the signal.
    const stopped = new Promise<never>((_, reject) => {
      controller.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), {
        once: true,
      });
    });
    try {
      return await Promise.race([impl(new Request(request, { signal: controller.signal })), stopped]);
    } catch (error) {
      clearTimeout(timer);
      request.signal.removeEventListener("abort", onCallerAbort);
      if (request.signal.aborted) throw new TransportError("aborted", { cause: error });
      if (timedOut) throw new TransportError("timeout", { cause: error });
      throw new TransportError("network", { cause: error });
    }
  };
  return createClient<paths>({ baseUrl, fetch: timed });
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
