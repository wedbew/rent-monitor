import type { components } from "../../api/schema.generated";
import { t } from "../../i18n";

export type AuditState = components["schemas"]["AuditState"];
export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export interface StatusCopy {
  readonly label: string;
  readonly tone: Tone;
  /** One line that says what happened to the person's report credit, when that is knowable from the state. */
  readonly credit: string | null;
}

const REJECTIONS: Readonly<Record<string, string>> = t.analyses.status.rejections;
const FAILURES: Readonly<Record<string, string>> = t.analyses.status.failures;
const label = t.analyses.status;
const credit = t.analyses.status.credit;
/** Own keys only: an error code is server data and must not reach the prototype. */
const own = (table: Readonly<Record<string, string>>, code: string | null) =>
  code !== null && Object.hasOwn(table, code) ? table[code] : undefined;

/**
 * What an analysis's state means in words, in one place for the dashboard, the collection and the report. The
 * `switch` is exhaustive: a new state in the API is a compile error here, not a silent blank.
 */
export function statusCopy(status: AuditState, errorCode: string | null): StatusCopy {
  switch (status) {
    case "queued":
      return { label: label.queued, tone: "neutral", credit: credit.reserved };
    case "running":
      return { label: label.running, tone: "info", credit: credit.reserved };
    case "succeeded":
      return { label: label.succeeded, tone: "success", credit: credit.captured };
    case "succeeded_degraded":
      return { label: label.succeeded_degraded, tone: "warning", credit: credit.captured };
    case "rejected":
      return {
        label: own(REJECTIONS, errorCode) ?? label.rejected,
        tone: "warning",
        credit: credit.notCharged,
      };
    case "failed_input":
    case "failed_upstream":
    case "failed_internal":
      return {
        label: own(FAILURES, errorCode) ?? label.failed,
        tone: "danger",
        credit: credit.notCharged,
      };
    case "cancelled":
      return { label: label.cancelled, tone: "neutral", credit: credit.notCharged };
  }
}

/** Finished with a usable report. */
export function hasReport(status: AuditState): boolean {
  return status === "succeeded" || status === "succeeded_degraded";
}

export function isActive(status: AuditState): boolean {
  return status === "queued" || status === "running";
}
