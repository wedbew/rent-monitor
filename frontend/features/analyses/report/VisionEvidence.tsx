import { formatCount, formatRatio } from "../../../api/format";
import { t } from "../../../i18n";
import {
  readVisionEvidence,
  type EquipmentRow,
  type EvidenceProvenance,
  type EvidenceSaleStatus,
} from "./vision";
import styles from "./VisionEvidence.module.css";

const V = t.analyses.report.vision;
const M = t.analyses.report.text;

const SALE: Readonly<Record<EvidenceSaleStatus, string>> = {
  included: V.saleIncluded,
  visible_only: V.saleVisibleOnly,
  unknown: V.saleUnknown,
};

/** Where the item was seen, in words; the number is the position in the media list, shown one-based. */
function sourceOf(row: EquipmentRow): string {
  const n = row.mediaOrdinal === null ? null : formatCount(row.mediaOrdinal + 1);
  const provenance: EvidenceProvenance = row.provenance;
  if (provenance === "photo" && n !== null) return V.sourcePhoto({ n });
  if (provenance === "floor_plan" && n !== null) return V.sourceFloorPlan({ n });
  return V.sourceUnattributed;
}

function EquipmentList({ rows }: { readonly rows: readonly EquipmentRow[] }) {
  return (
    <ul className={styles["list"]} aria-label={V.equipmentHeading}>
      {rows.map((row, index) => (
        <li key={`${index}-${row.item}`} className={styles["item"]}>
          <strong className={styles["itemName"]}>{row.item}</strong>
          <span className={styles["meta"]}>
            <span>{V.source({ source: sourceOf(row) })}</span>
            <span>{SALE[row.saleStatus]}</span>
            {row.confidence === null ? null : (
              <span>{V.confidence({ value: formatRatio(row.confidence, 0) })}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

// LEGAL[republication]: shows model-derived equipment, floor-plan text and notes from listing photos back to the person who ran the analysis (RM-403)
// GDPR[processor]: the text was produced by a vision model behind OpenRouter; nothing is sent from this view (RM-403)
/**
 * The persisted vision evidence of a report (RM-387), each state said in its own words. Every string is rendered as
 * text by React; nothing here is HTML and nothing is computed (the model's answers are shown, never used for a figure).
 */
export function VisionEvidence({
  vision,
  degraded,
}: {
  /** The report's `vision` value exactly as received; it is checked here, not trusted. */
  readonly vision: unknown;
  readonly degraded: boolean;
}) {
  const evidence = readVisionEvidence(vision, degraded);
  switch (evidence.kind) {
    case "not-run":
      return <p className={styles["muted"]}>{M.zdjecOcenionoWiecStanMieszkania}</p>;
    case "failed":
      return <p className={styles["notice"]}>{V.failed}</p>;
    case "older":
      return <p className={styles["muted"]}>{V.older}</p>;
    case "unreadable":
      return <p className={styles["notice"]}>{V.unreadable}</p>;
    case "empty":
      return <p className={styles["muted"]}>{V.empty}</p>;
    case "ready":
      return (
        <div className={styles["block"]}>
          {evidence.equipment.length > 0 ? (
            <>
              <h4 className={styles["heading"]}>{V.equipmentHeading}</h4>
              <p className={styles["muted"]}>{V.equipmentHint}</p>
              <EquipmentList rows={evidence.equipment} />
            </>
          ) : null}
          {evidence.skipped > 0 ? (
            <p className={styles["muted"]}>{V.skipped({ count: formatCount(evidence.skipped) })}</p>
          ) : null}
          {evidence.floorPlanText === null ? null : (
            <>
              <h4 className={styles["heading"]}>{V.floorPlanHeading}</h4>
              <p className={styles["text"]}>{evidence.floorPlanText}</p>
            </>
          )}
          {evidence.notes === null ? null : (
            <>
              <h4 className={styles["heading"]}>{V.notesHeading}</h4>
              <p className={styles["muted"]}>{V.notesHint}</p>
              <p className={styles["text"]}>{evidence.notes}</p>
            </>
          )}
        </div>
      );
  }
}
