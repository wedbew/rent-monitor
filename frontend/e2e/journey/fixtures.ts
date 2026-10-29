/**
 * `test` for the journey lane (real stack). The mocked lane's `fixtures.ts` guards every test; this gives the journey
 * lane the same floor plus QA evidence:
 *  - after every test: no uncaught page error and no console error (a failed `/api` request that the test meant to
 *    provoke, a 401 on a wrong password for example, is the browser's own message and is allowed);
 *  - `allowErrors(...)`: declare a browser error a test provokes on purpose; each pattern must match at least one;
 *  - `shot(name)`: a numbered, named full-page picture in the test's output directory (`test-results/<test>/`), to be
 *    LOOKED AT (a picture proves nothing until a person or the QA agent has read it);
 *  - `a11y(include?)`: axe on the current state (same rules as the mocked lane).
 * Every picture and the trace/video config (`playwright.config.ts`) land in `test-results/`, which CI uploads.
 */
import { test as base, expect } from "@playwright/test";

import { expectNoA11yViolations } from "../fixtures";

interface Fixtures {
  allowErrors: (...patterns: RegExp[]) => void;
  shot: (name: string) => Promise<string>;
  a11y: (include?: string) => Promise<void>;
}

export const test = base.extend<Fixtures>({
  allowErrors: [
    async ({ page }, provide) => {
      const problems: string[] = [];
      const allowed: RegExp[] = [];
      page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
      page.on("console", (message) => {
        if (message.type() !== "error") return;
        const text = message.text();
        const isApiFailure =
          message.location().url.includes("/api/") && text.startsWith("Failed to load resource");
        if (!isApiFailure) problems.push(`console.error: ${text}`);
      });
      await provide((...patterns) => {
        allowed.push(...patterns);
      });
      for (const pattern of allowed)
        expect(
          problems.some((p) => pattern.test(p)),
          `allowed error ${String(pattern)} never happened`,
        ).toBe(true);
      expect(
        problems.filter((p) => !allowed.some((pattern) => pattern.test(p))),
        "browser errors during the journey",
      ).toEqual([]);
    },
    { auto: true },
  ],
  shot: async ({ page }, provide, testInfo) => {
    let step = 0;
    await provide(async (name) => {
      step += 1;
      const file = testInfo.outputPath(
        `${String(step).padStart(2, "0")}-${name.replace(/[^a-z0-9-]+/gi, "-")}.png`,
      );
      await page.screenshot({ path: file, fullPage: true });
      await testInfo.attach(name, { path: file, contentType: "image/png" });
      return file;
    });
  },
  a11y: async ({ page }, provide) => {
    await provide((include) => expectNoA11yViolations(page, include));
  },
});

export { expect };
