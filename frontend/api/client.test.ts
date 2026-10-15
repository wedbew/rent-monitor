import { describe, expect, it } from "vitest";

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
