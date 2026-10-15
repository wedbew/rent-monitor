import type { DealAnalysis } from "./report.generated";
import { REPORT_SCHEMA } from "./report-schema.generated";
import { schemaErrors } from "./schema-check";

export type { DealAnalysis } from "./report.generated";

/** The `schema_version` this build can render (docs/REPORT-SCHEMA.md). A bump needs an adapter and new fixtures. */
export const SUPPORTED_REPORT_VERSION = 1;

/** Top-level keys the schema requires; a test compares this list with docs/deal-analysis.schema.json. */
export const REPORT_REQUIRED_KEYS = [
  "assumptions_version",
  "capex",
  "capex_used_pln",
  "cash_flow",
  "confidence",
  "engine_version",
  "legal",
  "listing",
  "ownership",
  "rent",
  "schema_version",
  "valuation",
  "vision",
  "warnings",
] as const;

export type ParsedReport =
  | { readonly kind: "ready"; readonly report: DealAnalysis }
  | { readonly kind: "unsupported"; readonly version: number | null }
  /** `problems` are JSON pointers with a reason (no values), for diagnostics only; never shown as copy. */
  | { readonly kind: "invalid"; readonly problems: readonly string[] };

/**
 * `AuditOut.result` is opaque in OpenAPI on purpose (an old audit keeps the shape it was made with). The page
 * renders only a version it knows and says so otherwise; it never guesses at an unknown shape. A known version is
 * checked against the whole committed schema (every nested block, type, enum and null the view reads) before it
 * is typed as `DealAnalysis`: a malformed report is "invalid", never a render exception (audit F11).
 */
export function parseReport(result: unknown): ParsedReport {
  if (typeof result !== "object" || result === null || Array.isArray(result))
    return { kind: "invalid", problems: ["/: not an object"] };
  const record = result as Record<string, unknown>;
  const version = record["schema_version"];
  if (typeof version !== "number") return { kind: "unsupported", version: null };
  if (version !== SUPPORTED_REPORT_VERSION) return { kind: "unsupported", version };
  const problems = schemaErrors(REPORT_SCHEMA, result);
  if (problems.length > 0) return { kind: "invalid", problems };
  return { kind: "ready", report: result as DealAnalysis };
}
