import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { collect, PAGES, PROJECTS, summarise } from "../perf-aggregate.mjs";

/** The aggregator refuses a thinner table than the lane promised (#286 review: workers used to overwrite each other). */
let dir = "";
beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), "perf-"));
});
afterEach(() => rmSync(dir, { recursive: true, force: true }));

const artifact = (project: string, page: string, extra: Record<string, unknown> = {}) => ({
  page,
  project,
  browserVersion: "148.0",
  lcpMs: 120,
  cls: 0,
  slowestInteractionMs: 40,
  ...extra,
});
function write(
  project: string,
  page: string,
  value: unknown = artifact(project, page),
  name = `${page}.json`,
) {
  mkdirSync(join(dir, project), { recursive: true });
  writeFileSync(join(dir, project, name), typeof value === "string" ? value : JSON.stringify(value));
}
const writeAll = () => PROJECTS.forEach((project) => PAGES.forEach((page) => write(project, page)));

describe("perf aggregation", () => {
  it("accepts exactly four pages in both projects, in a fixed order", () => {
    writeAll();
    const rows = collect(dir);
    expect(rows).toHaveLength(8);
    expect(rows.map((r) => `${r.project}/${r.page}`)).toEqual(
      PROJECTS.flatMap((project) => PAGES.map((page) => `${project}/${page}`)),
    );
  });

  it("rejects a missing page, a missing project and an unknown artifact", () => {
    writeAll();
    rmSync(join(dir, "perf-mobile", "report.json"));
    expect(() => collect(dir)).toThrow(/perf-mobile\/report: expected one artifact, found 0/);
    rmSync(join(dir, "perf-desktop"), { recursive: true });
    expect(() => collect(dir)).toThrow(/perf-desktop: no results at all/);
    writeAll();
    write("perf-desktop", "extra", artifact("perf-desktop", "extra"));
    expect(() => collect(dir)).toThrow(/unknown artifact extra.json/);
  });

  it("rejects an artifact that names another page or project, or holds nonsense", () => {
    writeAll();
    write("perf-desktop", "dashboard", artifact("perf-desktop", "analyses"));
    expect(() => collect(dir)).toThrow(/perf-desktop\/dashboard: malformed/);
    write("perf-desktop", "dashboard", artifact("perf-desktop", "dashboard", { cls: -1 }));
    expect(() => collect(dir)).toThrow(/malformed/);
    write("perf-desktop", "dashboard", artifact("perf-desktop", "dashboard", { lcpMs: "fast" }));
    expect(() => collect(dir)).toThrow(/malformed/);
    write("perf-desktop", "dashboard", "{not json");
    expect(() => collect(dir)).toThrow(/not valid JSON/);
  });

  it("rejects results from different browser versions and unknown project directories", () => {
    writeAll();
    write("perf-mobile", "report", artifact("perf-mobile", "report", { browserVersion: "149.0" }));
    expect(() => collect(dir)).toThrow(/mixed browser versions/);
    writeAll();
    mkdirSync(join(dir, "perf-tablet"));
    expect(() => collect(dir)).toThrow(/unknown project directory perf-tablet/);
  });

  it("the summary carries the run's metadata and the rows, nothing invented", () => {
    writeAll();
    const summary = summarise(collect(dir), new Date("2026-10-16T12:00:00Z"));
    expect(summary.measuredAt).toBe("2026-10-16T12:00:00.000Z");
    expect(summary.browserVersion).toBe("148.0");
    expect(summary.rows).toHaveLength(8);
  });
});
