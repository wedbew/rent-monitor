#!/usr/bin/env node
/**
 * Run the visual lane (#334) inside the pinned Playwright Linux image, so pictures are always made and compared on the
 * same rendering stack (fonts, hinting). Usage (from `frontend/`):
 *   pnpm visual           compare against the committed baselines
 *   pnpm visual:update    rewrite the baselines (then review every changed picture before committing)
 * The image tag follows the Playwright version in package.json; CI pins the same image by digest (`.github/workflows/ci.yml`, job `frontend-visual`). Dependencies install into a Docker volume, never
 * into the host's node_modules (those hold macOS binaries). Needs Docker; on Apple silicon it runs under emulation.
 */
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..");
const pkg = JSON.parse(readFileSync(resolve(here, "package.json"), "utf8"));
const version = String(pkg.devDependencies["@playwright/test"]).replace(/^[^\d]*/, "");
const image = `mcr.microsoft.com/playwright:v${version}-noble`;
const update = process.argv.includes("--update");

try {
  execFileSync("docker", ["info"], { stdio: "ignore" });
} catch {
  console.error("Docker is not running: the visual lane only runs inside the pinned image.");
  process.exit(2);
}

const inside = [
  "set -e",
  "corepack enable",
  "pnpm install --frozen-lockfile --config.engine-strict=false --config.store-dir=/pnpm-store",
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
    image,
    "bash",
    "-c",
    inside,
  ],
  { stdio: "inherit" },
);
process.exit(result.status ?? 1);
