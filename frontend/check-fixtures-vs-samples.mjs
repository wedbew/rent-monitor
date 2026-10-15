// `pnpm check:fixtures-vs-samples` (local only): every JSON key path seen in a captured response exists in at least
// one fixture of the same operation. It proves the fixtures kept the shapes the screens depend on. CI has no `data/`
// directory, so there it prints SKIPPED and exits 0 (the OpenAPI validation test still runs).
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const SAMPLES = new URL("../data/api-samples/", import.meta.url).pathname;
const FIXTURES = new URL("./test/fixtures/", import.meta.url).pathname;

if (!existsSync(SAMPLES)) {
  console.log("SKIPPED: no data/api-samples/ here (captures are local; run `make api-samples`)");
  process.exit(0);
}
const runs = readdirSync(SAMPLES)
  .filter((name) => existsSync(join(SAMPLES, name, "manifest.json")))
  .sort();
const latest = runs.at(-1);
if (latest === undefined) {
  console.log("SKIPPED: data/api-samples/ holds no capture");
  process.exit(0);
}

/** key paths with array indexes folded: `a.b[].c` */
function paths(value, prefix = "", out = new Set()) {
  if (Array.isArray(value)) {
    for (const item of value) paths(item, `${prefix}[]`, out);
  } else if (value !== null && typeof value === "object") {
    for (const [key, child] of Object.entries(value))
      paths(child, prefix === "" ? key : `${prefix}.${key}`, out);
  } else {
    out.add(prefix);
  }
  return out;
}
const json = (file) => JSON.parse(readFileSync(file, "utf8"));

const missing = [];
const bodyPaths = (fixtureOrSample, out) => {
  // Event streams are stored as frames in fixtures and as text in the sample; compare their data payloads.
  if (Array.isArray(fixtureOrSample.events)) {
    for (const frame of fixtureOrSample.events) paths(frame.data, "event", out);
  } else if (typeof fixtureOrSample.body !== "string") {
    paths(fixtureOrSample.body ?? {}, "", out);
  }
  return out;
};

for (const operation of readdirSync(join(SAMPLES, latest), { withFileTypes: true }).filter((d) =>
  d.isDirectory(),
)) {
  const fixtureSeen = new Set();
  for (const file of readdirSync(join(FIXTURES, operation.name)).filter((f) => f.endsWith(".json"))) {
    bodyPaths(json(join(FIXTURES, operation.name, file)), fixtureSeen);
  }
  for (const file of readdirSync(join(SAMPLES, latest, operation.name))) {
    const full = join(SAMPLES, latest, operation.name, file);
    const seen = new Set();
    if (file.endsWith(".events.ndjson")) {
      const frames = readFileSync(full, "utf8")
        .trim()
        .split("\n")
        .map((line) => JSON.parse(line));
      bodyPaths({ events: frames }, seen);
    } else if (file.endsWith(".json")) {
      bodyPaths(json(full), seen);
    }
    for (const path of seen) {
      if (!fixtureSeen.has(path)) missing.push(`${operation.name}/${file}: ${path}`);
    }
  }
}
if (missing.length > 0) {
  console.error(`fixtures lack key paths seen in ${latest}:\n${missing.slice(0, 40).join("\n")}`);
  process.exit(1);
}
console.log(`every key path in ${latest} exists in a fixture`);
