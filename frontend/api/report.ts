import type { DealAnalysis } from "./report.generated";

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
  | { readonly kind: "invalid" };

/**
 * `AuditOut.result` is opaque in OpenAPI on purpose (an old audit keeps the shape it was made with). The page
 * renders only a version it knows and says so otherwise; it never guesses at an unknown shape.
 */
export function parseReport(result: unknown): ParsedReport {
  if (typeof result !== "object" || result === null) return { kind: "invalid" };
  const record = result as Record<string, unknown>;
  const version = record["schema_version"];
  if (typeof version !== "number") return { kind: "unsupported", version: null };
  if (version !== SUPPORTED_REPORT_VERSION) return { kind: "unsupported", version };
  if (REPORT_REQUIRED_KEYS.some((key) => !(key in record))) return { kind: "invalid" };
  return { kind: "ready", report: result as DealAnalysis };
}
