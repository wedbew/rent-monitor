/**
 * Playwright reporter: after a full run, fails the process when a registered interaction or popup was never
 * exercised with an assertion of its outcome (or something was recorded that is not registered).
 * Enforced when E2E_COVERAGE=enforce (the `pnpm test:e2e` script); a filtered local run only prints a summary.
 */
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync } from "node:fs";
import { join } from "node:path";

import type { FullResult, Reporter } from "@playwright/test/reporter";

import { compareCoverage, coverageFailed, type Recorded } from "./gate";
import { INTERACTIONS, POPUPS } from "./interactions";

const DIR = process.env["E2E_COVERAGE_DIR"] ?? "playwright-coverage";

export default class CoverageReporter implements Reporter {
  onBegin(): void {
    rmSync(DIR, { recursive: true, force: true });
    mkdirSync(DIR, { recursive: true });
  }

  // eslint-disable-next-line @typescript-eslint/require-await -- the Reporter interface wants a promise
  async onEnd(result: FullResult): Promise<{ status: FullResult["status"] } | undefined> {
    const recorded: Recorded[] = existsSync(DIR)
      ? readdirSync(DIR)
          .filter((f) => f.endsWith(".ndjson"))
          .flatMap((f) => readFileSync(join(DIR, f), "utf8").trim().split("\n").filter(Boolean))
          .map((line) => JSON.parse(line) as Recorded)
      : [];
    const report = compareCoverage(recorded, INTERACTIONS, POPUPS);
    const total = INTERACTIONS.length + POPUPS.length;
    const enforce = process.env["E2E_COVERAGE"] === "enforce";
    // eslint-disable-next-line no-console -- a reporter's job is to print
    const print = (line: string) => console.log(line);
    print(
      `\ninteraction coverage: ${total - report.missing.length}/${total} registered interactions and popups exercised with an asserted outcome`,
    );
    for (const id of report.missing) print(`  not exercised: ${id}`);
    for (const line of report.wrongOutcome) print(`  ${line}`);
    for (const id of report.unknown) print(`  recorded but not registered: ${id}`);
    if (enforce && result.status === "passed" && coverageFailed(report)) {
      print(
        "interaction coverage gate FAILED: every registered page element and popup needs a test that asserts its outcome",
      );
      return { status: "failed" };
    }
    return undefined;
  }
}
