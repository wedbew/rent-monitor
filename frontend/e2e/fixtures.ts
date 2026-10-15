import AxeBuilder from "@axe-core/playwright";
import { expect, test as base, type Page } from "@playwright/test";

import type { Scenario, ScenarioName } from "../test/scenarios";
import { installFakeGis } from "./gis";
import { mockApi, type MockApi } from "./mock";

interface Fixtures {
  /** Serve a registry scenario for the page; returns the recorded requests. */
  serve: (which: ScenarioName | Scenario) => Promise<MockApi>;
}

/**
 * `test` for the mocked lane. After every test: no uncaught page error, no console error (a failed `/api` request
 * that the scenario meant to fail is the browser's own message and is allowed), and no request that the scenario
 * had no route for.
 */
export const test = base.extend<Fixtures>({
  serve: async ({ page }, provide) => {
    await installFakeGis(page);
    const apis: MockApi[] = [];
    const problems: string[] = [];
    page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
    page.on("console", (message) => {
      if (message.type() !== "error") return;
      const isMockedApiFailure =
        message.location().url.includes("/api/") && message.text().startsWith("Failed to load resource");
      if (!isMockedApiFailure) problems.push(`console.error: ${message.text()}`);
    });
    await provide(async (which) => {
      const api = await mockApi(page, which);
      apis.push(api);
      return api;
    });
    expect(problems, "browser errors during the test").toEqual([]);
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
