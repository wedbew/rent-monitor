/**
 * Collect the per-test artifacts of `pnpm perf` (`e2e/perf.spec.ts`) into one validated summary (#286).
 * Every page must be measured exactly once in both projects; a missing, duplicate, unknown or malformed artifact is
 * an error, never a silently thinner table. The summary carries the run's metadata so a recorded number can be
 * traced to the machine and browser that produced it. These are lab proxies, not thresholds and not field data.
 */
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { arch, cpus, platform, release } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const PROJECTS = ["perf-desktop", "perf-mobile"];
export const PAGES = ["dashboard", "analyses", "new-analysis", "report"];

const isNumberOrNull = (value) =>
  value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0);

/** Read and validate `<dir>/<project>/<page>.json`; returns the rows in project, page order. */
export function collect(dir) {
  const problems = [];
  const rows = [];
  const projectsOnDisk = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);
  for (const unknown of projectsOnDisk.filter((name) => !PROJECTS.includes(name)))
    problems.push(`unknown project directory ${unknown}`);
  for (const project of PROJECTS) {
    let files;
    try {
      files = readdirSync(join(dir, project)).filter((name) => name.endsWith(".json"));
    } catch {
      problems.push(`${project}: no results at all`);
      continue;
    }
    for (const unknown of files.filter((name) => !PAGES.includes(name.replace(/\.json$/, ""))))
      problems.push(`${project}: unknown artifact ${unknown}`);
    for (const page of PAGES) {
      const matching = files.filter((name) => name === `${page}.json`);
      if (matching.length !== 1) {
        problems.push(`${project}/${page}: expected one artifact, found ${matching.length}`);
        continue;
      }
      let artifact;
      try {
        artifact = JSON.parse(readFileSync(join(dir, project, `${page}.json`), "utf8"));
      } catch {
        problems.push(`${project}/${page}: not valid JSON`);
        continue;
      }
      const ok =
        artifact !== null &&
        typeof artifact === "object" &&
        artifact.page === page &&
        artifact.project === project &&
        typeof artifact.browserVersion === "string" &&
        artifact.browserVersion !== "" &&
        isNumberOrNull(artifact.lcpMs) &&
        isNumberOrNull(artifact.slowestInteractionMs) &&
        typeof artifact.cls === "number" &&
        Number.isFinite(artifact.cls) &&
        artifact.cls >= 0;
      if (!ok) problems.push(`${project}/${page}: malformed artifact`);
      else rows.push(artifact);
    }
  }
  const versions = new Set(rows.map((row) => row.browserVersion));
  if (versions.size > 1) problems.push(`mixed browser versions: ${[...versions].join(", ")}`);
  if (problems.length > 0) throw new Error(`perf results are not usable:\n  ${problems.join("\n  ")}`);
  return rows;
}

function git(args) {
  try {
    return execFileSync("git", args, { encoding: "utf8" }).trim();
  } catch {
    return null;
  }
}

/** The summary: validated rows plus where and when they were measured. */
export function summarise(rows, now = new Date()) {
  return {
    measuredAt: now.toISOString(),
    commit: git(["rev-parse", "HEAD"]),
    dirtyTree: (git(["status", "--porcelain", "--untracked-files=no"]) ?? "") !== "",
    node: process.versions.node,
    browserVersion: rows[0].browserVersion,
    machine: {
      platform: platform(),
      release: release(),
      arch: arch(),
      cpu: cpus()[0]?.model ?? "unknown",
      cores: cpus().length,
    },
    note: "lab proxies on one machine with a mocked API; diagnostics, not thresholds, not field data",
    rows: rows.map(({ page, project, lcpMs, cls, slowestInteractionMs }) => ({
      page,
      project,
      lcpMs,
      cls,
      slowestInteractionMs,
    })),
  };
}

if (resolve(process.argv[1] ?? "") === fileURLToPath(import.meta.url)) {
  const dir = join(process.env.PERF_OUT ?? "test-results", "perf");
  const summary = summarise(collect(dir));
  writeFileSync(join(dir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(
    `perf summary: ${summary.rows.length} measurements (${PROJECTS.length} projects x ${PAGES.length} pages) in ${join(dir, "summary.json")}`,
  );
}
