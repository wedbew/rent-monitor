import { describe, expect, it } from "vitest";

import { apiProxy } from "./vite.config";

// `vite dev` serves source modules such as /api/query.ts under the same prefix as the real API. The proxy must
// leave those to Vite and still forward real API paths (#341).
describe("dev proxy for /api", () => {
  const bypass = apiProxy("http://127.0.0.1:8000")["/api"]?.bypass;

  const servedByVite = (url: string): boolean => {
    expect(bypass).toBeTypeOf("function");
    return bypass?.({ url } as never, undefined as never, undefined as never) === url;
  };

  it.each(["/api/query.ts", "/api/client.ts?t=1700000000", "/api/report.generated.ts", "/api/view.tsx", "/api/x.ts?import"])(
    "serves source module %s from Vite",
    (url) => {
      expect(servedByVite(url)).toBe(true);
    },
  );

  it.each(["/api/health", "/api/audits/123/events", "/api/audits?cursor=a.ts", "/api/me"])(
    "still proxies %s to the backend",
    (url) => {
      expect(servedByVite(url)).toBe(false);
    },
  );

  it("targets the given backend", () => {
    expect(apiProxy("http://example.test:9000")["/api"]?.target).toBe("http://example.test:9000");
  });
});
