import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  currentPins,
  nodeVersion,
  pinnedImage,
  playwrightVersion,
  recordedBaseline,
} from "../visual-image.mjs";

/**
 * One rendering stack for the visual lane (#334, review 2026-10-16): the Playwright image is pinned by digest in the
 * workflow, `pnpm visual` uses that same image, the Node is `.node-version`, and the committed baselines record what
 * they were made with. Bumping any one of them without the others fails here, before a picture is compared.
 */
const root = resolve(__dirname, "..", "..");
const workflow = readFileSync(resolve(root, ".github", "workflows", "ci.yml"), "utf8");
/** The `frontend-visual` job's text, up to the next job key: independent of where the job sits in the file. */
const visualJob = (() => {
  const start = workflow.indexOf("\n  frontend-visual:");
  if (start < 0) throw new Error("ci.yml has no frontend-visual job");
  const rest = workflow.slice(start + 1);
  const next = rest.slice(1).search(/\n {2}[A-Za-z0-9_-]+:\s*\n/);
  return next < 0 ? rest : rest.slice(0, next + 1);
})();
const runner = readFileSync(resolve(root, "frontend", "visual.mjs"), "utf8");

describe("the visual lane's rendering stack", () => {
  it("pins the image by digest and its tag names the Playwright version in package.json", () => {
    const { version, digest } = pinnedImage();
    expect(digest).toMatch(/^[0-9a-f]{64}$/);
    expect(version).toBe(playwrightVersion());
  });

  it("the local runner uses the workflow's image and never builds a mutable tag", () => {
    expect(runner).toContain("pinnedImage");
    expect(runner).not.toMatch(/mcr\.microsoft\.com\/playwright:v\$\{/);
  });

  it("runs Node from .node-version through the shared script, with engine enforcement on", () => {
    expect(visualJob).toContain("e2e/visual-prepare.sh");
    expect(runner).toContain("e2e/visual-prepare.sh");
    expect(visualJob).not.toMatch(/engine[_-]strict/i);
    expect(runner).not.toMatch(/engine[_-]strict/i);
    const script = readFileSync(resolve(root, "frontend", "e2e", "visual-prepare.sh"), "utf8");
    expect(script).toContain(".node-version");
    expect(script).not.toMatch(/engine[_-]strict/i);
  });

  it("the job is cut out of the workflow on its own, with its image and steps", () => {
    expect(visualJob.startsWith("  frontend-visual:")).toBe(true);
    expect(visualJob).toContain("mcr.microsoft.com/playwright:");
    expect(visualJob).not.toMatch(/\n {2}frontend-journey:/);
  });

  it("the Node tarball is pinned by checksum for the .node-version release, with no npm wrapper", () => {
    const pinned = readFileSync(resolve(root, "frontend", "e2e", "node-linux-x64.sha256"), "utf8").trim();
    expect(pinned).toMatch(
      new RegExp(`^[0-9a-f]{64}  node-v${nodeVersion().replace(/\./g, "\\.")}-linux-x64\\.tar\\.gz$`),
    );
    const script = readFileSync(resolve(root, "frontend", "e2e", "visual-prepare.sh"), "utf8");
    expect(script).toContain("sha256sum -c");
    expect(script).not.toMatch(/npm install[^\n]*node@/);
  });

  it("the committed baselines were made with exactly these pins", () => {
    expect(recordedBaseline()).toEqual(currentPins());
    expect(currentPins().node).toBe(nodeVersion());
  });
});
