import { describe, expect, it, vi } from "vitest";

import { fx } from "../test/fixtures";
import { unmatched, useScenario } from "../test/handlers";
import { ApiError } from "./errors";
import { createApi, unwrap } from "./client";

const BASE = window.location.origin;

describe("api client", () => {
  it("returns the typed body of a success", async () => {
    useScenario("loaded");
    const me = unwrap(await createApi({ baseUrl: BASE }).GET("/api/me"));
    expect(me.credit_balance).toBe(7);
  });

  it("turns an error status into an ApiError with the problem and request id", async () => {
    useScenario("firstVisit");
    const result = await createApi({ baseUrl: BASE }).GET("/api/me");
    expect(() => unwrap(result)).toThrowError(ApiError);
    try {
      unwrap(result);
    } catch (error) {
      expect(error).toMatchObject({ status: 401, code: "UNAUTHENTICATED" });
      expect((error as ApiError).requestId).toBe("req_fixture");
    }
  });

  it("reads Retry-After from a 429", async () => {
    useScenario({
      name: "limited",
      description: "",
      routes: [
        {
          operation: "GET /api/me",
          reply: {
            status: 429,
            body: fx("POST /api/auth/login", "rate_limited").body,
            contentType: "application/problem+json",
            headers: { "retry-after": "42" },
          },
        },
      ],
    });
    const result = await createApi({ baseUrl: BASE }).GET("/api/me");
    expect(() => unwrap(result)).toThrowError(
      expect.objectContaining({ status: 429, code: "RATE_LIMITED", retryAfterS: 42 }),
    );
  });

  it("keeps an error without a problem body (a proxy's HTML) as an ApiError with no problem", async () => {
    useScenario({
      name: "html",
      description: "",
      routes: [
        {
          operation: "GET /api/me",
          reply: { status: 502, text: "<html>Bad gateway</html>", contentType: "text/html" },
        },
      ],
    });
    const result = await createApi({ baseUrl: BASE }).GET("/api/me");
    expect(() => unwrap(result)).toThrowError(expect.objectContaining({ status: 502, problem: null }));
  });

  it("reports a dropped connection as a network TransportError", async () => {
    useScenario("offline");
    await expect(createApi({ baseUrl: BASE }).GET("/api/me")).rejects.toMatchObject({ kind: "network" });
  });

  // A fetch that never answers on its own: only the client's deadline or the caller's abort ends it.
  const hang = (request: Request) =>
    new Promise<Response>((_, reject) => {
      const abort = () => reject(new DOMException(`aborted ${request.method}`, "AbortError"));
      if (request.signal.aborted) abort();
      else request.signal.addEventListener("abort", abort);
    });

  it("reports a deadline as a timeout", async () => {
    await expect(
      createApi({ baseUrl: BASE, fetch: hang, timeoutMs: 20 }).GET("/api/me"),
    ).rejects.toMatchObject({ kind: "timeout" });
  });

  it("reports a caller's abort as aborted, not as a timeout", async () => {
    const controller = new AbortController();
    const pending = createApi({ baseUrl: BASE, fetch: hang, timeoutMs: 5000 }).GET("/api/me", {
      signal: controller.signal,
    });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ kind: "aborted" });
  });

  it("never hits a route a scenario did not define", async () => {
    useScenario("empty");
    const response = await createApi({ baseUrl: BASE }).GET("/api/admin/jobs");
    expect(response.response.status).toBe(599);
    expect(unmatched.splice(0)).toHaveLength(1);
  });
});

/**
 * Audit F08: the deadline and the error kinds cover the whole response, not only its headers. Each case below
 * escaped as a raw AbortError or SyntaxError, or outlived the deadline, before the body was read inside the race.
 */
describe("the response body is inside the deadline and the error kinds", () => {
  const encoder = new TextEncoder();
  const json = { "content-type": "application/json" };

  /** Headers at once; the body sends `first` and then whatever `rest` does with the stream. */
  const answering =
    (first: string, rest: (controller: ReadableStreamDefaultController<Uint8Array>) => void) =>
    (request: Request) => {
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode(first));
          rest(controller);
          request.signal.addEventListener("abort", () => controller.error(request.signal.reason));
        },
      });
      return Promise.resolve(new Response(body, { status: 200, headers: json }));
    };

  it("headers in time but a body that stalls is a timeout", async () => {
    const stall = answering('{"id":', () => undefined);
    await expect(
      createApi({ baseUrl: BASE, fetch: stall, timeoutMs: 20 }).GET("/api/me"),
    ).rejects.toMatchObject({ name: "TransportError", kind: "timeout" });
  });

  it("a body that ignores the abort still ends at the deadline", async () => {
    const deaf = () =>
      Promise.resolve(
        new Response(new ReadableStream<Uint8Array>({ start: () => undefined }), {
          status: 200,
          headers: json,
        }),
      );
    await expect(
      createApi({ baseUrl: BASE, fetch: deaf, timeoutMs: 20 }).GET("/api/me"),
    ).rejects.toMatchObject({ kind: "timeout" });
  });

  it("a connection dropped in the middle of the body is a network failure", async () => {
    const drop = answering('{"id":', (controller) => controller.error(new TypeError("terminated")));
    await expect(createApi({ baseUrl: BASE, fetch: drop }).GET("/api/me")).rejects.toMatchObject({
      kind: "network",
    });
  });

  it("a success whose body is not JSON is an invalid response", async () => {
    const portal = () =>
      Promise.resolve(new Response("<html>Wi-Fi login</html>", { status: 200, headers: json }));
    await expect(createApi({ baseUrl: BASE, fetch: portal }).GET("/api/me")).rejects.toMatchObject({
      kind: "invalid-response",
    });
  });

  it("a caller's signal that is already aborted never sends the request", async () => {
    const impl = vi.fn(() => Promise.resolve(new Response("{}", { status: 200, headers: json })));
    const controller = new AbortController();
    controller.abort();
    await expect(
      createApi({ baseUrl: BASE, fetch: impl }).GET("/api/me", { signal: controller.signal }),
    ).rejects.toMatchObject({ kind: "aborted" });
    expect(impl).not.toHaveBeenCalled();
  });

  it("a caller's abort while the body is arriving is aborted, not a timeout", async () => {
    const controller = new AbortController();
    const slow = answering('{"id":', () => setTimeout(() => controller.abort(), 5));
    await expect(
      createApi({ baseUrl: BASE, fetch: slow, timeoutMs: 5000 }).GET("/api/me", {
        signal: controller.signal,
      }),
    ).rejects.toMatchObject({ kind: "aborted" });
  });

  it("a fast success leaves no timer behind", async () => {
    vi.useFakeTimers();
    try {
      const ok = () => Promise.resolve(new Response('{"id":"x"}', { status: 200, headers: json }));
      const result = await createApi({ baseUrl: BASE, fetch: ok, timeoutMs: 5000 }).GET("/api/me");
      expect(result.data).toEqual({ id: "x" });
      expect(vi.getTimerCount()).toBe(0);
    } finally {
      vi.useRealTimers();
    }
  });

  it("a 204 and an error page still reach openapi-fetch unchanged", async () => {
    const empty = () => Promise.resolve(new Response(null, { status: 204 }));
    const result = await createApi({ baseUrl: BASE, fetch: empty }).POST("/api/auth/signout");
    expect(result.response.status).toBe(204);
    const proxy = () =>
      Promise.resolve(
        new Response("<html>Bad gateway</html>", { status: 502, headers: { "content-type": "text/html" } }),
      );
    const failed = await createApi({ baseUrl: BASE, fetch: proxy }).GET("/api/me");
    expect(() => unwrap(failed)).toThrowError(expect.objectContaining({ status: 502, problem: null }));
  });
});
