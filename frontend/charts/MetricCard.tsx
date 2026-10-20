import type { ReactNode } from "react";

import { t } from "../i18n";
import styles from "./charts.module.css";
import type { StatMeta } from "./meta";

interface MetricCardProps {
  readonly meta: StatMeta;
  /** The value, already formatted with its unit ("45,50 zł/m²"). Replaced by `unavailable` when there is none. */
  readonly value: string;
  /** Why there is no value ("Za mało ofert z ceną"): shown in place of the value, never a zero. */
  readonly unavailable?: string;
  /** Extra context under the value (a comparison, a rank). */
  readonly context?: ReactNode;
  readonly headingLevel?: 2 | 3 | 4;
}

/**
 * One statistic with its five answers, top to bottom: the name of the measure, the value with its unit, the
 * context (area and period), how to read it, then the source and sample as small print. Without a value it says
 * why, in words. `StatMeta` is required: a bare number cannot be rendered (`.agent/rules/statistics.md`).
 */
export function MetricCard({ meta, value, unavailable, context, headingLevel = 3 }: MetricCardProps) {
  const Heading = `h${headingLevel}` as const;
  return (
    <article className={styles["card"]}>
      <Heading className={styles["cardTitle"]}>{meta.measure}</Heading>
      <p className={styles["value"]}>{unavailable === undefined ? value : unavailable}</p>
      <p className={styles["context"]}>
        {meta.area}. {meta.period}.
      </p>
      {context === undefined ? null : <p className={styles["context"]}>{context}</p>}
      <p className={styles["interpretation"]}>{meta.interpretation}</p>
      <dl className={styles["facts"]}>
        <div>
          <dt>{t.rynek.stats.factsUnit}</dt>
          <dd>{meta.unit}</dd>
        </div>
        <div>
          <dt>{t.rynek.stats.factsSource}</dt>
          <dd>{meta.source}</dd>
        </div>
        <div>
          <dt>{t.rynek.stats.factsSample}</dt>
          <dd>{meta.sample}</dd>
        </div>
      </dl>
    </article>
  );
}
