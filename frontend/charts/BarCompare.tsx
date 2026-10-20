import { t } from "../i18n";
import styles from "./charts.module.css";

export interface BarItem {
  readonly id: string;
  readonly name: string;
  /** Position of the bar's end on the shared scale, or null when there is no value (a withheld sample). */
  readonly value: number | null;
  /** The value as text, with its unit, already formatted. */
  readonly valueText: string;
  /** The sample or any second fact, as text ("n = 12"). */
  readonly meta?: string | undefined;
  /** A quartile band to draw over the track, in the same coordinates as `value`. */
  readonly low?: number | null;
  readonly high?: number | null;
  /** Why there is no value, in words. */
  readonly withheldText?: string;
  /** The place the row refers to as a link or button, when the name should be actionable. */
  readonly nameNode?: React.ReactNode;
  /** A second kind of bar (for example the city beside a district) drawn with a hatch instead of a fill. */
  readonly alt?: boolean;
}

interface BarCompareProps {
  readonly items: readonly BarItem[];
  /** The shared maximum of the scale. Defaults to the largest value present. */
  readonly max?: number;
  readonly label: string;
}

/**
 * Horizontal bars on one scale, each with its value, unit and sample written beside it, so the number is never
 * only a length. A row without a value (a sample too small to give a median) shows a dashed empty track and says
 * why in words: an unknown is not a short bar and never a zero. Bars differ by fill pattern as well as colour.
 */
export function BarCompare({ items, max, label }: BarCompareProps) {
  // The quartile band is drawn on the same scale, so its upper end counts: a band past the track would run under the value.
  const scale = max ?? Math.max(...items.flatMap((i) => [i.value ?? 0, i.high ?? 0]), 1e-9);
  return (
    <ul className={styles["bars"]} aria-label={label}>
      {items.map((item) => {
        const pct = item.value === null ? 0 : Math.max(0, Math.min(100, (item.value / scale) * 100));
        const withheld = item.value === null;
        const low = item.low ?? null;
        const high = item.high ?? null;
        return (
          <li key={item.id} className={styles["barRow"]}>
            <span className={styles["barName"]}>{item.nameNode ?? item.name}</span>
            <span className={styles["barTrack"]} aria-hidden="true">
              {withheld ? (
                <span
                  className={`${styles["barFill"]} ${styles["barFillWithheld"]}`}
                  style={{ width: "100%" }}
                />
              ) : (
                <span
                  className={`${styles["barFill"]} ${item.alt ? styles["barFillAlt"] : ""}`}
                  style={{ width: `${pct}%` }}
                />
              )}
              {low !== null && high !== null && !withheld ? (
                <span
                  className={styles["barRange"]}
                  style={{
                    left: `${Math.max(0, (low / scale) * 100)}%`,
                    width: `${Math.max(1, Math.min(100 - Math.max(0, (low / scale) * 100), ((high - low) / scale) * 100))}%`,
                  }}
                />
              ) : null}
            </span>
            <span className={styles["barValue"]}>
              {withheld ? (item.withheldText ?? t.rynek.stats.withheldBar) : item.valueText}
              {item.meta === undefined ? null : <span className={styles["barMeta"]}>{item.meta}</span>}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
