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
const visualJob = workflow.slice(
  workflow.indexOf("\n  frontend-visual:"),
  workflow.indexOf("\n  frontend-journey:"),
);
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

  it("the committed baselines were made with exactly these pins", () => {
    expect(recordedBaseline()).toEqual(currentPins());
    expect(currentPins().node).toBe(nodeVersion());
  });
});
