// @vitest-environment node
import { createServer as createHttpServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { createServer, type ViteDevServer } from "vite";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import { server as mockApi } from "./test/handlers";

// Regression (#341): in development Vite serves the SPA's own `api/*.ts` modules at `/api/<file>.ts`, the same
// prefix the dev proxy sends to the backend. The built-preview and Caddy tests cannot see this collision.
const MARKER = "backend-answered";
let backend: Server;
let vite: ViteDevServer;
let base: string;
let backendPaths: string[];

beforeAll(async () => {
  // The global setup refuses every unmocked request. This file talks only to two loopback servers it starts
  // itself (the dev server and a stub backend), so it pauses the mock for its own duration and restores it.
  mockApi.close();
  backendPaths = [];
  backend = createHttpServer((req, res) => {
    backendPaths.push(req.url ?? "");
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({ who: MARKER }));
  });
  await new Promise<void>((done) => backend.listen(0, "127.0.0.1", done));
  process.env["API_ORIGIN"] = `http://127.0.0.1:${String((backend.address() as AddressInfo).port)}`;
  vite = await createServer({
    configFile: new URL("./vite.config.ts", import.meta.url).pathname,
    server: { port: 0, host: "127.0.0.1", hmr: false, watch: null },
    optimizeDeps: { noDiscovery: true, include: [] },
    logLevel: "silent",
  });
  await vite.listen();
  base = `http://127.0.0.1:${String((vite.httpServer?.address() as AddressInfo).port)}`;
});

afterAll(async () => {
  await vite.close();
  await new Promise((done) => backend.close(done));
  delete process.env["API_ORIGIN"];
  mockApi.listen({ onUnhandledFrame: "error" });
});

describe("dev server /api prefix", () => {
  it("serves the SPA's own api/*.ts modules instead of proxying them", async () => {
    for (const file of ["client.ts", "format.ts", "query.ts"]) {
      const res = await fetch(`${base}/api/${file}`);
      const body = await res.text();
      expect(res.status, file).toBe(200);
      expect(res.headers.get("content-type"), file).toContain("javascript");
      expect(body, file).not.toContain(MARKER);
    }
    // Vite appends a query for cache busting and HMR; that form must not be proxied either.
    const stamped = await fetch(`${base}/api/query.ts?t=123`);
    expect(stamped.status).toBe(200);
    expect(backendPaths.filter((p) => p.endsWith(".ts") || p.includes(".ts?"))).toEqual([]);
  });

  it("still proxies real API requests to the backend, query strings included", async () => {
    const res = await fetch(`${base}/api/audits?limit=5`);
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ who: MARKER });
    expect(backendPaths).toContain("/api/audits?limit=5");
  });
});
