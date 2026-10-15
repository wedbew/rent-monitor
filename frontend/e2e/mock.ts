/**
 * Serve a registry scenario to a Playwright page (the mocked lane). Same data as the Vitest/MSW adapter
 * (test/scenarios.ts); a request no route matches answers 599 and fails the test (see e2e/fixtures.ts).
 */
import type { Page, Route } from "@playwright/test";

import type { HttpMethod } from "../test/fixtures";
import { matchRoute, resolveReply, SCENARIOS, type Scenario, type ScenarioName } from "../test/scenarios";

export interface RecordedRequest {
  readonly method: string;
  readonly path: string;
  readonly query: string;
  readonly body: unknown;
}

export interface MockApi {
  readonly scenario: string;
  readonly requests: RecordedRequest[];
  readonly unmatched: string[];
}

function parseBody(text: string | null): unknown {
  if (text === null || text === "") return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function mockApi(page: Page, which: ScenarioName | Scenario): Promise<MockApi> {
  const scenario = typeof which === "string" ? SCENARIOS[which] : which;
  const api: MockApi = { scenario: scenario.name, requests: [], unmatched: [] };
  await page.route(/\/api\//, async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method() as HttpMethod;
    const body = parseBody(request.postData());
    api.requests.push({ method, path: url.pathname, query: url.search, body });
    const matched = matchRoute(scenario, method, url.pathname);
    if (matched === null) {
      api.unmatched.push(`${method} ${url.pathname} (scenario ${scenario.name})`);
      await route.fulfill({
        status: 599,
        contentType: "application/json",
        body: '{"error":"no route in this scenario"}',
      });
      return;
    }
    const reply = resolveReply(matched, { method, url, params: matched.params, body });
    if (reply.networkError === true) {
      await route.abort("failed");
      return;
    }
    const headers = { ...reply.headers };
    delete headers["content-type"];
    await route.fulfill({
      status: reply.status,
      headers,
      contentType: reply.contentType ?? "application/json",
      body: reply.text ?? (reply.status === 204 ? "" : JSON.stringify(reply.body ?? null)),
    });
  });
  return api;
}
