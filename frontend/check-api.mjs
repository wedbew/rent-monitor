// `pnpm check:api`: regenerate the API types in memory and fail when they differ from the committed file.
// CI never rewrites the baseline; run `pnpm generate:api` and commit the result.
import { readFileSync } from "node:fs";

import openapiTS, { astToString } from "openapi-typescript";

const SPEC = new URL("../docs/openapi.json", import.meta.url);
const COMMITTED = new URL("./api/schema.generated.ts", import.meta.url);

const ast = await openapiTS(SPEC);
const fresh = astToString(ast);
const committed = readFileSync(COMMITTED, "utf8");
if (!committed.endsWith(fresh) && committed !== fresh) {
  console.error(
    "api/schema.generated.ts is out of date with docs/openapi.json: run `pnpm generate:api` and commit.",
  );
  process.exit(1);
}
console.log("api/schema.generated.ts matches docs/openapi.json");
