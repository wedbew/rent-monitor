import type { ReactNode } from "react";

import styles from "./charts.module.css";

export interface Column {
  readonly key: string;
  readonly header: string;
  readonly numeric?: boolean;
}

interface Props {
  readonly caption: string;
  readonly columns: readonly Column[];
  /** Cells by column key. The first column is the row header. */
  readonly rows: readonly { readonly id: string; readonly cells: Readonly<Record<string, ReactNode>> }[];
}

/** The table equivalent of a chart: the same numbers, with units already in the cells (`ChartFigure` offers it). */
export function DataTable({ caption, columns, rows }: Props) {
  return (
    <table className={styles["table"]}>
      <caption>{caption}</caption>
      <thead>
        <tr>
          {columns.map((c) => (
            <th scope="col" key={c.key} className={c.numeric ? styles["num"] : undefined}>
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            {columns.map((c, i) =>
              i === 0 ? (
                <th scope="row" key={c.key}>
                  {row.cells[c.key]}
                </th>
              ) : (
                <td key={c.key} className={c.numeric ? styles["num"] : undefined}>
                  {row.cells[c.key]}
                </td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
