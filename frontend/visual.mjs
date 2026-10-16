#!/usr/bin/env node
/**
 * Run the visual lane (#334) inside the pinned Playwright Linux image, so pictures are always made and compared on the
 * same rendering stack (fonts, hinting). Usage (from `frontend/`):
 *   pnpm visual           compare against the committed baselines
 *   pnpm visual:update    rewrite the baselines (then review every changed picture before committing)
 * The image is the one pinned BY DIGEST in the `frontend-visual` job of `.github/workflows/ci.yml` (`visual-image.mjs`
 * reads it from there), the Node is `.node-version` (`e2e/visual-prepare.sh`, the same script CI runs), and
 * `e2e/__screenshots__/BASELINE.json` records both for the committed pictures: a comparison refuses to run when they
 * differ, and `test/visual-image.test.ts` checks the same in `pnpm test`. Dependencies install into a Docker volume,
 * never into the host's node_modules (those hold macOS binaries). Needs Docker; on Apple silicon it runs under emulation.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { BASELINE_FILE, currentPins, pinnedImage, recordedBaseline } from "./visual-image.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..");
const update = process.argv.includes("--update");
const pins = currentPins();
const { image } = pinnedImage();

if (!update) {
  const recorded = recordedBaseline();
  const differs = recorded === null || Object.keys(pins).some((key) => recorded[key] !== pins[key]);
  if (differs) {
    console.error(
      "The committed baselines were not made with the pinned image, Playwright and Node.\n" +
        `  pinned:   ${JSON.stringify(pins)}\n  recorded: ${JSON.stringify(recorded)}\n` +
        "Run `pnpm visual:update` and review every changed picture.",
    );
    process.exit(3);
  }
}

try {
  execFileSync("docker", ["info"], { stdio: "ignore" });
} catch {
  console.error("Docker is not running: the visual lane only runs inside the pinned image.");
  process.exit(2);
}

const inside = [
  "set -e",
  ". e2e/visual-prepare.sh",
  `E2E_LANE=visual E2E_PORT=4311 pnpm exec playwright test ${update ? "--update-snapshots" : ""} --reporter=list`,
].join(" && ");

const result = spawnSync(
  "docker",
  [
    "run",
    "--rm",
    "--platform",
    "linux/amd64",
    "--ipc=host",
    "-v",
    `${repo}:/work`,
    "-v",
    "renti-frontend-node-modules:/work/frontend/node_modules",
    "-v",
    "renti-pnpm-store:/pnpm-store",
    "-w",
    "/work/frontend",
    "-e",
    "CI=",
    "-e",
    "PNPM_STORE_DIR=/pnpm-store",
    image,
    "bash",
    "-c",
    inside,
  ],
  { stdio: "inherit" },
);
if (update && result.status === 0) {
  writeFileSync(BASELINE_FILE, `${JSON.stringify(pins, null, 2)}\n`);
  console.log(`recorded ${BASELINE_FILE}`);
}
process.exit(result.status ?? 1);
