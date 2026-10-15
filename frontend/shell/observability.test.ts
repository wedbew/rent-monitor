import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/errors";
import {
  initObservability,
  REDACTED,
  redactText,
  reportError,
  resetObservability,
  safeScrub,
  scrubEvent,
  scrubUrl,
} from "./observability";

/**
 * Audit F15 / #280: an error event leaves the browser only after scrubbing, and only when a DSN is configured. The
 * sample values below are synthetic.
 */
afterEach(() => {
  resetObservability();
});

const sampleEvent = () => ({
  message: "Failed for anna@example.test on https://www.otodom.pl/pl/oferta/mieszkanie-ID4abcd",
  request: {
    url: "https://renti.tech/login/email?next=%2Fapp#t=SecretLinkToken123",
    headers: { cookie: "rm_session=abc", "user-agent": "x" },
    cookies: { rm_session: "abc" },
    data: { password: "hunter22", listing_ref: "ID4abcd" },
    query_string: "token=abc",
  },
  user: { id: "u1", email: "anna@example.test", ip_address: "203.0.113.7" },
  exception: {
    values: [
      {
        type: "TypeError",
        value: "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig broke on ID4abcd",
        stacktrace: { frames: [{ filename: "app.js", vars: { password: "hunter22" } }] },
      },
    ],
  },
  breadcrumbs: [
    { category: "navigation", data: { from: "/password/reset#t=Tok", to: "/app" }, message: "nav" },
    { category: "console", message: "token=abc123 for anna@example.test" },
  ],
  extra: { note: "call anna@example.test", nested: { deep: "credential=xyz" } },
  tags: { route: "/app/analyses/ID4abcd" },
});

describe("scrubbing", () => {
  it("removes the person, the request and every secret or listing from the event", () => {
    const event = scrubEvent(sampleEvent());
    const text = JSON.stringify(event);
    for (const secret of [
      "anna@example.test",
      "SecretLinkToken123",
      "hunter22",
      "rm_session",
      "203.0.113.7",
      "eyJhbGciOiJIUzI1NiJ9",
      "ID4abcd",
      "otodom.pl",
      "abc123",
      "credential=xyz",
      "Tok",
    ])
      expect(text, secret).not.toContain(secret);
    expect(event).not.toHaveProperty("user");
    expect(event.request).toEqual({ url: "https://renti.tech/login/email" });
    expect(event.exception.values[0]?.stacktrace.frames[0]).not.toHaveProperty("vars");
    expect(event.breadcrumbs[0]).toEqual({ category: "navigation", message: "nav" });
    expect(event.exception.values[0]?.type).toBe("TypeError"); // what failed stays readable
  });

  it("keeps a URL's path and drops its query and fragment", () => {
    expect(scrubUrl("https://renti.tech/app/analyses/00000000-0000-4000-8000-000000000001?x=1#y")).toBe(
      "https://renti.tech/app/analyses/00000000-0000-4000-8000-000000000001",
    );
    expect(redactText("see #t=abc and ?token=def")).toBe(`see #t=${REDACTED} and ?token=${REDACTED}`);
  });

  it("drops an event it cannot scrub instead of sending it as it was", () => {
    const hostile = {
      get request(): never {
        throw new Error("boom");
      },
    };
    expect(safeScrub(hostile)).toBeNull();
  });
});

describe("starting error reporting", () => {
  it("does nothing without a DSN: no SDK is loaded", async () => {
    const load = vi.fn();
    expect(await initObservability({ dsn: "", load })).toBe(false);
    expect(load).not.toHaveBeenCalled();
    expect(() => reportError(new Error("x"))).not.toThrow();
  });

  it("with a DSN: no tracing, no personal data collected, and every event scrubbed before sending", async () => {
    const init = vi.fn();
    const captureException = vi.fn();
    const ok = await initObservability({
      dsn: "https://public@errors.example.test/1",
      release: "abc123",
      load: () => Promise.resolve({ init, captureException } as never),
    });
    expect(ok).toBe(true);
    const options = init.mock.calls[0]?.[0] as Record<string, unknown> & {
      beforeSend: (event: unknown) => unknown;
      beforeBreadcrumb: (crumb: unknown) => unknown;
    };
    expect(options).toMatchObject({
      dsn: "https://public@errors.example.test/1",
      release: "abc123",
      tracesSampleRate: 0,
      dataCollection: {
        userInfo: false,
        cookies: false,
        httpHeaders: false,
        httpBodies: [],
        urlQueryParams: false,
      },
    });
    expect(options).not.toHaveProperty("integrations"); // no replay or extra integrations added
    expect(JSON.stringify(options.beforeSend(sampleEvent()))).not.toContain("anna@example.test");
    expect(options.beforeBreadcrumb({ data: { url: "/x?token=1" }, message: "m" })).toEqual({ message: "m" });
  });

  it("an API failure is reported with its request id and code, not its body", async () => {
    const captureException = vi.fn();
    await initObservability({
      dsn: "https://public@errors.example.test/1",
      load: () => Promise.resolve({ init: vi.fn(), captureException } as never),
    });
    const problem = {
      type: "urn:rentmonitor:problem:INTERNAL",
      title: "Internal error",
      status: 500,
      code: "INTERNAL" as const,
      instance: "/api/audits",
      detail: null,
      errors: null,
      request_id: "req_42",
    };
    const error = new ApiError(500, problem);
    reportError(error);
    expect(captureException).toHaveBeenCalledWith(error, {
      tags: { http_status: "500", problem_code: "INTERNAL", request_id: "req_42" },
    });
  });
});
