import { useId, type ReactNode } from "react";

import { t } from "../i18n";
import styles from "./charts.module.css";
import type { StatMeta } from "./meta";

interface ChartFigureProps {
  readonly title: string;
  readonly meta: StatMeta;
  /** The chart itself (or its fallback). */
  readonly children: ReactNode;
  /** The legend: what each line, band or bar means, by more than colour. */
  readonly legend?: ReactNode;
  /** The data as a table: always offered next to the chart. */
  readonly table: ReactNode;
  /** A sentence about the chart that is not part of the five answers (a gap, a single reading). */
  readonly note?: ReactNode;
  readonly headingLevel?: 2 | 3 | 4;
  /** Rows of bars size themselves; only a lazily loaded chart reserves height. */
  readonly compact?: boolean;
}

/**
 * A chart with everything a reader needs to interpret it: a title, the five answers as a caption, a legend, the
 * data as a table and any note about gaps. The chart is `aria-describedby` the caption, so a screen reader hears
 * what is measured, in what unit, where, when, from what source and how to read it before any value.
 */
export function ChartFigure({
  title,
  meta,
  children,
  legend,
  table,
  note,
  headingLevel = 3,
  compact = false,
}: ChartFigureProps) {
  const id = useId();
  const Heading = `h${headingLevel}` as const;
  return (
    <figure className={styles["figure"]} aria-labelledby={`${id}-title`} aria-describedby={`${id}-caption`}>
      <Heading id={`${id}-title`} className={styles["figureTitle"]}>
        {title}
      </Heading>
      <p className={styles["figureLead"]}>{meta.interpretation}</p>
      {note === undefined ? null : <p className={styles["note"]}>{note}</p>}
      {legend === undefined ? null : <ul className={styles["legend"]}>{legend}</ul>}
      <div className={compact ? styles["chartBoxCompact"] : styles["chartBox"]}>{children}</div>
      <figcaption id={`${id}-caption`} className={styles["caption"]}>
        <p>
          {meta.measure}, {meta.unit}. {meta.area}. {meta.period}.
        </p>
        <p>
          {meta.source}. {meta.sample}.
        </p>
      </figcaption>
      <details className={styles["details"]}>
        <summary>{t.rynek.stats.tableToggle}</summary>
        <div className={styles["tableWrap"]}>{table}</div>
      </details>
    </figure>
  );
}

export function LegendItem({
  swatch,
  children,
}: {
  readonly swatch: ReactNode;
  readonly children: ReactNode;
}) {
  return (
    <li>
      {swatch}
      <span>{children}</span>
    </li>
  );
}

export const swatchClass = {
  line: styles["swatchLine"],
  band: styles["swatchBand"],
  dash: styles["swatchDash"],
} as const;
