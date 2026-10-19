import { t } from "../../i18n";
import styles from "./market.module.css";

export type DataStatus = "fresh" | "delayed" | "stale" | "unavailable";

const TONE: Record<DataStatus, string> = {
  fresh: "success",
  delayed: "warning",
  stale: "danger",
  unavailable: "neutral",
};

/** The state is in the words; the colour only repeats it. */
export function StatusBadge({ status }: { readonly status: DataStatus }) {
  return <span className={`${styles["badge"]} ${styles[TONE[status]]}`}>{t.market.status[status]}</span>;
}
