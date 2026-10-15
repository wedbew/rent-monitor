import type { AuditSummary } from "../queries";
import { statusCopy } from "../status";
import styles from "./AuditBadge.module.css";

/** The run's state in words; the tinted pill is a second cue, never the only one. */
export function AuditBadge({ audit }: { readonly audit: AuditSummary }) {
  const copy = statusCopy(audit.status, audit.error_code);
  return <span className={`${styles["badge"]} ${styles[copy.tone]}`}>{copy.label}</span>;
}
