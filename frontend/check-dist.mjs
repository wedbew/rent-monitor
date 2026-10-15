// `pnpm check:dist`: the production build must not contain mock or test tooling (issue #267 acceptance 4), and it
// must stay within the bundle budget (README "Bundle budget", audit F17, #312). Sizes are gzip level 9, what a
// visitor downloads. A budget is raised only in a PR that says why, never to make this pass.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

/** Bytes, gzip. Initial = the entry script plus every chunk index.html preloads: what the first page needs. */
const DIST = process.env["DIST_DIR"] ?? "dist";

export const BUDGET = {
  initialJs: 200 * 1024,
  anyLazyChunk: 120 * 1024,
  totalJs: 450 * 1024,
  css: 40 * 1024,
};

const FORBIDDEN = [
  /mockServiceWorker/i,
  /\bmsw\b/,
  /setupWorker/,
  /@testing-library/,
  /vitest/,
  /fixtures\//,
];
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (/\.(js|css|html|map|json|webmanifest)$/.test(name)) files.push(path);
  }
})(DIST);

// Source maps are never published (audit F15: errors are readable from the release tag, not from a public `.map`).
const maps = files.filter((path) => path.endsWith(".map"));
if (maps.length > 0) {
  console.error("production build publishes source maps:\n" + maps.join("\n"));
  process.exit(1);
}

const hits = files.flatMap((path) => {
  const text = readFileSync(path, "utf8");
  return FORBIDDEN.filter((pattern) => pattern.test(text)).map((pattern) => `${path}: ${pattern}`);
});
if (files.length === 0) {
  console.error(`${DIST}/ is empty: run \`pnpm build\` first`);
  process.exit(1);
}
if (hits.length > 0) {
  console.error("production build contains test or mock code:\n" + hits.join("\n"));
  process.exit(1);
}

const gz = (path) => gzipSync(readFileSync(path), { level: 9 }).length;
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} kB`;
const html = readFileSync(join(DIST, "index.html"), "utf8");
const initial = new Set(
  [...html.matchAll(/<(?:script|link)[^>]+(?:src|href)="\/?(assets\/[^"]+\.js)"/g)].map((m) =>
    join(DIST, m[1]),
  ),
);
const js = files.filter((path) => path.endsWith(".js"));
const css = files.filter((path) => path.endsWith(".css"));
const sizes = new Map(js.map((path) => [path, gz(path)]));
const initialJs = [...initial].reduce((sum, path) => sum + (sizes.get(path) ?? 0), 0);
const totalJs = [...sizes.values()].reduce((a, b) => a + b, 0);
const cssTotal = css.reduce((sum, path) => sum + gz(path), 0);
const over = [];
if (initial.size === 0) over.push("no entry script found in dist/index.html");
if (initialJs > BUDGET.initialJs) over.push(`initial JS ${kb(initialJs)} > ${kb(BUDGET.initialJs)}`);
if (totalJs > BUDGET.totalJs) over.push(`total JS ${kb(totalJs)} > ${kb(BUDGET.totalJs)}`);
if (cssTotal > BUDGET.css) over.push(`CSS ${kb(cssTotal)} > ${kb(BUDGET.css)}`);
for (const [path, size] of sizes)
  if (!initial.has(path) && size > BUDGET.anyLazyChunk)
    over.push(`lazy chunk ${path} ${kb(size)} > ${kb(BUDGET.anyLazyChunk)}`);
console.log(
  `bundle (gzip): initial JS ${kb(initialJs)} of ${kb(BUDGET.initialJs)} · total JS ${kb(totalJs)} of ` +
    `${kb(BUDGET.totalJs)} in ${sizes.size} chunks · CSS ${kb(cssTotal)} of ${kb(BUDGET.css)}`,
);
if (over.length > 0) {
  console.error("bundle over budget:\n" + over.join("\n"));
  process.exit(1);
}
console.log(`dist/: ${files.length} files, no mock or test code`);
