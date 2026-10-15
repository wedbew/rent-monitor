/**
 * A small JSON Schema check for data the server sends but OpenAPI keeps opaque (the report in `AuditOut.result`).
 * It understands exactly the keywords the committed schema uses and refuses any other (`SUPPORTED_KEYWORDS`, with
 * a test over the generated schema), so a new keyword can never be skipped silently. Not a general validator:
 * no network refs, no `oneOf`/`allOf`, no `if`/`then`. Errors are returned, never thrown, so a malformed answer
 * becomes a controlled "invalid" state instead of a render exception (audit F11).
 */

type Schema = { readonly [keyword: string]: unknown };

export const SUPPORTED_KEYWORDS = new Set([
  "type",
  "properties",
  "required",
  "additionalProperties",
  "enum",
  "const",
  "anyOf",
  "$ref",
  "$defs",
  "items",
  "minimum",
  "maximum",
  "minLength",
  "maxLength",
  "maxItems",
  "pattern",
  "format",
]);

/** At most this many problems are collected: enough to diagnose, bounded for a hostile answer. */
const MAX_ERRORS = 20;

function typeOf(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  if (typeof value === "number") return Number.isInteger(value) ? "integer" : "number";
  return typeof value;
}

function matchesType(value: unknown, type: unknown): boolean {
  const actual = typeOf(value);
  const one = (t: unknown) => t === actual || (t === "number" && actual === "integer");
  return Array.isArray(type) ? type.some(one) : one(type);
}

function resolve(root: Schema, ref: string): Schema {
  const prefix = "#/$defs/";
  if (!ref.startsWith(prefix)) throw new Error(`unsupported $ref ${ref}`);
  const defs = root["$defs"] as Record<string, Schema> | undefined;
  const target = defs?.[ref.slice(prefix.length)];
  if (target === undefined) throw new Error(`unknown $ref ${ref}`);
  return target;
}

const patterns = new Map<string, RegExp>();
function regex(source: string): RegExp {
  let compiled = patterns.get(source);
  if (compiled === undefined) {
    compiled = new RegExp(source, "u");
    patterns.set(source, compiled);
  }
  return compiled;
}

function check(root: Schema, schema: Schema, value: unknown, path: string, errors: string[]): void {
  if (errors.length >= MAX_ERRORS) return;
  const fail = (message: string) => {
    if (errors.length < MAX_ERRORS) errors.push(`${path || "/"}: ${message}`);
  };

  if (typeof schema["$ref"] === "string") {
    check(root, resolve(root, schema["$ref"]), value, path, errors);
    return;
  }
  if (Array.isArray(schema["anyOf"])) {
    const options = schema["anyOf"] as Schema[];
    if (!options.some((option) => validate(root, option, value).length === 0))
      fail("matches no allowed shape");
    return;
  }
  if ("const" in schema && value !== schema["const"]) fail(`must be ${JSON.stringify(schema["const"])}`);
  if (Array.isArray(schema["enum"]) && !(schema["enum"] as unknown[]).includes(value))
    fail("not an allowed value");
  if (schema["type"] !== undefined && !matchesType(value, schema["type"])) {
    fail(`expected ${JSON.stringify(schema["type"])}, got ${typeOf(value)}`);
    return;
  }

  if (typeof value === "number") {
    if (typeof schema["minimum"] === "number" && value < schema["minimum"]) fail("below the minimum");
    if (typeof schema["maximum"] === "number" && value > schema["maximum"]) fail("above the maximum");
  }
  if (typeof value === "string") {
    if (typeof schema["minLength"] === "number" && value.length < schema["minLength"]) fail("too short");
    if (typeof schema["maxLength"] === "number" && value.length > schema["maxLength"]) fail("too long");
    if (typeof schema["pattern"] === "string" && !regex(schema["pattern"]).test(value)) fail("wrong format");
    if (schema["format"] === "date-time" && Number.isNaN(Date.parse(value))) fail("not a date-time");
  }
  if (Array.isArray(value)) {
    if (typeof schema["maxItems"] === "number" && value.length > schema["maxItems"]) fail("too many items");
    const items = schema["items"] as Schema | undefined;
    if (items !== undefined) value.forEach((item, i) => check(root, items, item, `${path}/${i}`, errors));
  }
  if (typeOf(value) === "object") {
    const record = value as Record<string, unknown>;
    const properties = (schema["properties"] ?? {}) as Record<string, Schema>;
    for (const key of (schema["required"] ?? []) as string[]) {
      if (!(key in record)) fail(`missing ${key}`);
    }
    for (const [key, item] of Object.entries(record)) {
      const sub = properties[key];
      if (sub !== undefined) check(root, sub, item, `${path}/${key}`, errors);
      else if (schema["additionalProperties"] === false) fail(`unexpected ${key}`);
      else if (typeof schema["additionalProperties"] === "object" && schema["additionalProperties"] !== null)
        check(root, schema["additionalProperties"] as Schema, item, `${path}/${key}`, errors);
    }
  }
}

function validate(root: Schema, schema: Schema, value: unknown): string[] {
  const errors: string[] = [];
  check(root, schema, value, "", errors);
  return errors;
}

/** The problems with `value` against `schema` (JSON pointers with a reason); empty when it conforms. */
export function schemaErrors(schema: Schema, value: unknown): string[] {
  return validate(schema, schema, value);
}

/** Every keyword the schema uses that this checker does not understand (a test keeps this empty). */
export function unsupportedKeywords(schema: unknown): string[] {
  const found = new Set<string>();
  const walk = (node: unknown, named: boolean) => {
    if (Array.isArray(node)) return node.forEach((item) => walk(item, false));
    if (node === null || typeof node !== "object") return;
    for (const [key, value] of Object.entries(node)) {
      if (named) {
        walk(value, false); // a property or $defs name, not a keyword
        continue;
      }
      if (!SUPPORTED_KEYWORDS.has(key)) found.add(key);
      if (key === "enum" || key === "const" || key === "required") continue; // values, not schemas
      walk(value, key === "properties" || key === "$defs");
    }
  };
  walk(schema, false);
  return [...found].sort();
}
