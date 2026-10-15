// `pnpm check:dist`: the production build must not contain mock or test tooling (issue #267 acceptance 4).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

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
})("dist");

const hits = files.flatMap((path) => {
  const text = readFileSync(path, "utf8");
  return FORBIDDEN.filter((pattern) => pattern.test(text)).map((pattern) => `${path}: ${pattern}`);
});
if (files.length === 0) {
  console.error("dist/ is empty: run `pnpm build` first");
  process.exit(1);
}
if (hits.length > 0) {
  console.error("production build contains test or mock code:\n" + hits.join("\n"));
  process.exit(1);
}
console.log(`dist/: ${files.length} files, no mock or test code`);
