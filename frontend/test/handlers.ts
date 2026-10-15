import { delay, http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { type HttpMethod } from "./fixtures";
import { matchRoute, resolveReply, SCENARIOS, type Scenario, type ScenarioName } from "./scenarios";

/** Requests a scenario had no route for. Every test run ends by asserting this is empty (test/setup.ts). */
export const unmatched: string[] = [];

function parseBody(text: string): unknown {
  if (text === "") return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function handlerFor(scenario: Scenario) {
  return http.all("*/api/*", async ({ request }) => {
    const url = new URL(request.url);
    const method = request.method as HttpMethod;
    const matched = matchRoute(scenario, method, url.pathname);
    if (matched === null) {
      unmatched.push(`${method} ${url.pathname} (scenario ${scenario.name})`);
      return HttpResponse.json({ error: "no route in this scenario" }, { status: 599 });
    }
    const text = await request.clone().text();
    const body = parseBody(text);
    const reply = resolveReply(matched, { method, url, params: matched.params, body });
    if (reply.delayMs !== undefined) await delay(reply.delayMs);
    if (reply.networkError === true) return HttpResponse.error();
    const headers = { ...reply.headers, "content-type": reply.contentType ?? "application/json" };
    if (reply.text !== undefined) return new HttpResponse(reply.text, { status: reply.status, headers });
    if (reply.status === 204) return new HttpResponse(null, { status: 204, headers });
    return new HttpResponse(JSON.stringify(reply.body ?? null), { status: reply.status, headers });
  });
}

export const server = setupServer();

/** Serve a registry scenario (or a custom one) for the rest of the test. */
export function useScenario(scenario: ScenarioName | Scenario): void {
  server.use(handlerFor(typeof scenario === "string" ? SCENARIOS[scenario] : scenario));
}
