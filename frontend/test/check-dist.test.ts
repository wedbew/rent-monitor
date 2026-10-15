// @vitest-environment node
import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/** Audit F17: the bundle budget is a failing check, not a README number. */
function distWith(files: Record<string, string | Buffer>): string {
  const dir = mkdtempSync(join(tmpdir(), "rm-dist-"));
  mkdirSync(join(dir, "assets"));
  for (const [name, content] of Object.entries(files)) writeFileSync(join(dir, name), content);
  return dir;
}

const run = (dir: string) =>
  spawnSync(process.execPath, ["check-dist.mjs"], {
    env: { ...process.env, DIST_DIR: dir },
    encoding: "utf8",
  });

/** About `kb` kB after gzip: base64 of random bytes carries 6 bits per character, which gzip cannot beat. */
const incompressible = (kb: number) => randomBytes(kb * 1024).toString("base64");

describe("check-dist budget", () => {
  const html = '<script type="module" src="/assets/index-a.js"></script>';

  it("passes a build inside the budget and prints the sizes", () => {
    const result = run(distWith({ "index.html": html, "assets/index-a.js": "console.log(1)" }));
    expect(result.status).toBe(0);
    expect(result.stdout).toMatch(/initial JS .* of 200\.0 kB/);
  });

  it("fails when the initial JS is over budget", () => {
    const result = run(distWith({ "index.html": html, "assets/index-a.js": incompressible(210) }));
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/initial JS .* > 200\.0 kB/);
  });

  it("fails when one lazy chunk is over its budget", () => {
    const result = run(
      distWith({ "index.html": html, "assets/index-a.js": "x", "assets/Report-b.js": incompressible(130) }),
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/lazy chunk .*Report-b\.js/);
  });

  it("still refuses test tooling in the build", () => {
    const result = run(distWith({ "index.html": html, "assets/index-a.js": "import 'msw'" }));
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/test or mock code/);
  });
});
