/**
 * The one definition of the visual lane's rendering stack (#334): the Playwright image, pinned by digest in the
 * `frontend-visual` job of `.github/workflows/ci.yml`. `pnpm visual` reads it from there (so local runs and CI use the
 * same bytes), and `test/visual-image.test.ts` fails when the image, the Playwright version in package.json, the
 * Node version and the recorded baseline metadata (`e2e/__screenshots__/BASELINE.json`) disagree.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const IMAGE_LINE =
  /^\s*image:\s*(mcr\.microsoft\.com\/playwright:v([\d.]+)-noble@sha256:([0-9a-f]{64}))\s*$/m;

/** `{ image, version, digest }` of the pinned image, read from the workflow's `frontend-visual` job. */
export function pinnedImage() {
  const workflow = readFileSync(resolve(here, "..", ".github", "workflows", "ci.yml"), "utf8");
  const job = workflow.slice(workflow.indexOf("\n  frontend-visual:"));
  const match = IMAGE_LINE.exec(job);
  if (match === null)
    throw new Error("the frontend-visual job of ci.yml must pin its Playwright image by digest");
  return { image: match[1], version: match[2], digest: match[3] };
}

export function playwrightVersion() {
  const pkg = JSON.parse(readFileSync(resolve(here, "package.json"), "utf8"));
  return String(pkg.devDependencies["@playwright/test"]).replace(/^[^\d]*/, "");
}

export function nodeVersion() {
  return readFileSync(resolve(here, ".node-version"), "utf8").trim();
}

export const BASELINE_FILE = resolve(here, "e2e", "__screenshots__", "BASELINE.json");

/** What the committed pictures were made with, or `null` when none is recorded. */
export function recordedBaseline() {
  try {
    return JSON.parse(readFileSync(BASELINE_FILE, "utf8"));
  } catch {
    return null;
  }
}

/** The metadata a run with the current pins would record. */
export function currentPins() {
  const { image, version, digest } = pinnedImage();
  return { image, digest: `sha256:${digest}`, playwright: version, node: nodeVersion() };
}
