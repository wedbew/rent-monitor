import {
  CartesianGrid,
  ComposedChart,
  Label,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatAxisNumber } from "../api/format";
import { t } from "../i18n";
import styles from "./charts.module.css";

/** One statistical year. A year without a published value is a gap (`value` null), never a zero. */
export interface YearPoint {
  readonly year: number;
  readonly value: number | null;
  readonly valueText: string;
  readonly note: string | null;
}

export interface YearChartProps {
  readonly points: readonly YearPoint[];
  readonly ariaLabel: string;
  readonly yLabel: string;
  readonly xLabel: string;
  readonly height?: number;
}

function TooltipBody({
  active,
  payload,
}: {
  readonly active?: boolean;
  readonly payload?: readonly { payload?: YearPoint }[];
}) {
  const p = payload?.[0]?.payload;
  if (active !== true || p === undefined) return null;
  return (
    <div className={styles["tooltip"]}>
      <strong>
        {t.rynek.stats.tooltipYear}: {p.year}
      </strong>
      <span>
        {t.rynek.stats.tooltipValue}: {p.valueText}
      </span>
      {p.note === null ? null : <span>{p.note}</span>}
    </div>
  );
}

/** An annual series with labelled axes and a keyboard-reachable tooltip; a single year is one point and no line. */
export default function YearChartImpl({ points, ariaLabel, yLabel, xLabel, height = 240 }: YearChartProps) {
  const values = points.flatMap((p) => (p.value === null ? [] : [p.value]));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.1, Math.abs(max) * 0.01, 0.5);
  const single = values.length === 1;
  return (
    <div role="group" aria-label={ariaLabel} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 560, height }}>
        <ComposedChart
          data={[...points]}
          margin={{ top: 12, right: 16, bottom: 28, left: 8 }}
          accessibilityLayer
        >
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="year"
            type="number"
            domain={["dataMin", "dataMax"]}
            allowDecimals={false}
            tickFormatter={(v: number) => String(v)}
            tick={{ fill: "var(--chart-text)", fontSize: 12 }}
            stroke="var(--chart-grid)"
          >
            <Label
              value={xLabel}
              position="insideBottom"
              offset={-18}
              fill="var(--chart-text)"
              fontSize={12}
            />
          </XAxis>
          <YAxis
            width={72}
            domain={[min - pad, max + pad]}
            tickFormatter={(v: number) => formatAxisNumber(v, Math.abs(max) < 10 ? 1 : 0)}
            tick={{ fill: "var(--chart-text)", fontSize: 12 }}
            stroke="var(--chart-grid)"
          >
            <Label
              value={yLabel}
              angle={-90}
              position="insideLeft"
              offset={0}
              fill="var(--chart-text)"
              fontSize={12}
              style={{ textAnchor: "middle" }}
            />
          </YAxis>
          <Tooltip
            content={<TooltipBody />}
            cursor={{ stroke: "var(--chart-text)", strokeDasharray: "4 3" }}
          />
          <Line
            dataKey="value"
            type="linear"
            stroke="var(--chart-line)"
            strokeWidth={single ? 0 : 2.5}
            dot={{ r: 4, fill: "var(--chart-line)", stroke: "var(--surface)", strokeWidth: 1 }}
            activeDot={{ r: 7, fill: "var(--chart-line)", stroke: "var(--surface)", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
