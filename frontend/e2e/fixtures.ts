import AxeBuilder from "@axe-core/playwright";
import { expect, test as base, type Page } from "@playwright/test";

import type { Scenario, ScenarioName } from "../test/scenarios";
import { installFakeGis } from "./gis";
import { mockApi, type MockApi } from "./mock";
import { installFakePaddle, type FakePaddleHandle } from "./paddle";

interface Fixtures {
  /** The Paddle.js stand-in every mocked test gets (and the proof that Paddle's hosts were never contacted). */
  paddle: FakePaddleHandle;
  /** Serve a registry scenario for the page; returns the recorded requests. */
  serve: (which: ScenarioName | Scenario) => Promise<MockApi>;
  /**
   * Declare a browser error this test provokes on purpose (a chunk that fails to load, for example). Each pattern
   * must match at least one error, so an allowance cannot outlive what it was for; anything else still fails.
   */
  allowErrors: (...patterns: RegExp[]) => void;
}

/**
 * `test` for the mocked lane. After every test: no uncaught page error, no console error (a failed `/api` request
 * that the scenario meant to fail is the browser's own message and is allowed), and no request that the scenario
 * had no route for.
 */
const allowances = new WeakMap<Page, RegExp[]>();

export const test = base.extend<Fixtures>({
  paddle: [
    async ({ page }, provide) => {
      const handle = await installFakePaddle(page);
      await provide(handle);
      expect(handle.hostRequests, "a mocked test must never reach Paddle's hosts").toEqual([]);
    },
    { auto: true },
  ],
  allowErrors: async ({ page }, provide) => {
    await provide((...patterns) => {
      allowances.set(page, [...(allowances.get(page) ?? []), ...patterns]);
    });
  },
  serve: async ({ page }, provide) => {
    await installFakeGis(page);
    const apis: MockApi[] = [];
    const problems: string[] = [];
    page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() !== "error") return;
      // The browser's own report of an `/api` request the scenario made fail on purpose: Chromium and WebKit
      // say "Failed to load resource" (located at the request); Firefox says it cannot establish a connection
      // to the `/api` URL (the stream lanes). Anything else, including those words for another URL, still fails.
      const text = message.text();
      const isMockedApiFailure =
        (message.location().url.includes("/api/") && text.startsWith("Failed to load resource")) ||
        /can.t establish a connection to the server at \S+\/api\//.test(text);
      if (!isMockedApiFailure) problems.push(`console.error: ${message.text()}`);
    });
    await provide(async (which) => {
      const api = await mockApi(page, which);
      apis.push(api);
      return api;
    });
    const allowed = allowances.get(page) ?? [];
    for (const pattern of allowed)
      expect(
        problems.some((p) => pattern.test(p)),
        `allowed error ${String(pattern)} never happened`,
      ).toBe(true);
    expect(
      problems.filter((p) => !allowed.some((pattern) => pattern.test(p))),
      "browser errors during the test",
    ).toEqual([]);
    expect(
      apis.flatMap((a) => a.unmatched),
      "API requests the scenario had no route for",
    ).toEqual([]);
  },
});

export { expect };

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** axe-core on the current page state (or a part of it); fails with the rule ids and the offending nodes. */
export async function expectNoA11yViolations(page: Page, include?: string): Promise<void> {
  const builder = new AxeBuilder({ page }).withTags(WCAG);
  const result = await (include === undefined ? builder : builder.include(include)).analyze();
  expect(
    result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
    "axe violations",
  ).toEqual([]);
}
