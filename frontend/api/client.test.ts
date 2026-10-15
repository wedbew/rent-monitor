import { describe, expect, it, vi } from "vitest";

import { fx } from "../test/fixtures";
import { unmatched, useScenario } from "../test/handlers";
import { ApiError } from "./errors";
import { createApi, unwrap } from "./client";
import { RESPONSE_DOCUMENT, RESPONSES } from "./responses.generated";
import { unsupportedKeywords } from "./schema-check";

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
      const me = fx("GET /api/me", "with_credits_and_flags").body;
      const ok = () => Promise.resolve(new Response(JSON.stringify(me), { status: 200, headers: json }));
      const result = await createApi({ baseUrl: BASE, fetch: ok, timeoutMs: 5000 }).GET("/api/me");
      expect(result.data).toEqual(me);
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

/**
 * Audit F11 / #325: every success body is checked against its OpenAPI schema before anyone reads it. Each
 * malformed body below used to reach a component typed as if it were valid.
 */
describe("success bodies are checked against the OpenAPI schema", () => {
  const json = { "content-type": "application/json" };
  const answering =
    (body: unknown, status = 200) =>
    () =>
      Promise.resolve(new Response(JSON.stringify(body), { status, headers: json }));
  const me = () =>
    structuredClone(fx("GET /api/me", "with_credits_and_flags").body) as Record<string, unknown>;

  it.each([
    [
      "a required field is missing",
      () => {
        const body = me();
        delete body["credit_balance"];
        return body;
      },
    ],
    ["a number arrives as text", () => ({ ...me(), credit_balance: "7" })],
    ["the body is a list", () => [me()]],
    ["the body is null", () => null],
  ])("%s: invalid-response, never a typed value", async (_, make) => {
    await expect(createApi({ baseUrl: BASE, fetch: answering(make()) }).GET("/api/me")).rejects.toMatchObject(
      { name: "TransportError", kind: "invalid-response" },
    );
  });

  it("the checker understands every keyword of every documented success body", () => {
    expect(unsupportedKeywords({ $defs: RESPONSE_DOCUMENT.components.schemas })).toEqual([]);
    for (const byStatus of Object.values(RESPONSES))
      for (const schema of Object.values(byStatus)) expect(unsupportedKeywords(schema)).toEqual([]);
    expect(Object.keys(RESPONSES)).toContain("GET /api/me");
  });

  it("an audit id that is not a UUID is refused", async () => {
    const page = structuredClone(fx("GET /api/audits", "heavy_user_default_page").body) as {
      items: Record<string, unknown>[];
    };
    const first = page.items[0];
    if (first !== undefined) first["audit_id"] = "../../admin";
    await expect(
      createApi({ baseUrl: BASE, fetch: answering(page) }).GET("/api/audits"),
    ).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("an unknown enum value in a list is refused", async () => {
    const page = structuredClone(fx("GET /api/audits", "heavy_user_default_page").body) as {
      items: Record<string, unknown>[];
    };
    const first = page.items[0];
    if (first !== undefined) first["status"] = "teleported";
    await expect(
      createApi({ baseUrl: BASE, fetch: answering(page) }).GET("/api/audits"),
    ).rejects.toMatchObject({ kind: "invalid-response" });
  });

  it("a field the SPA does not know yet is allowed (the server may add one first)", async () => {
    const body = { ...me(), added_later: true };
    const result = await createApi({ baseUrl: BASE, fetch: answering(body) }).GET("/api/me");
    expect(result.data).toMatchObject({ added_later: true });
  });

  it("the diagnostics name paths and reasons, not values", async () => {
    const error: unknown = await createApi({
      baseUrl: BASE,
      fetch: answering({ ...me(), email: 42 }),
    })
      .GET("/api/me")
      .catch((e: unknown) => e);
    expect(String((error as { cause?: unknown }).cause)).toMatch(/GET \/api\/me 200: \/email: expected/);
    expect(String((error as { cause?: unknown }).cause)).not.toContain("42");
  });
});
