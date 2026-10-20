import {
  Area,
  CartesianGrid,
  ComposedChart,
  Label,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatAxisNumber, formatDayMonth } from "../api/format";
import { t } from "../i18n";
import styles from "./charts.module.css";

/** One day of the series. Numbers place the point; the `*Text` fields are what a person reads (api/format.ts). */
export interface TrendPoint {
  readonly iso: string;
  readonly t: number;
  readonly median: number | null;
  readonly low: number | null;
  readonly high: number | null;
  readonly dayText: string;
  readonly medianText: string;
  readonly bandText: string;
  readonly sampleText: string;
  readonly withheld: boolean;
}

export interface TrendChartProps {
  readonly points: readonly TrendPoint[];
  readonly ariaLabel: string;
  readonly yLabel: string;
  readonly xLabel: string;
  readonly height?: number;
}

const DAY_MS = 86_400_000;

interface Row {
  readonly t: number;
  readonly median: number | null;
  readonly band: readonly [number, number] | null;
  readonly point: TrendPoint | null;
}

/** Every calendar day between the first and last reading; a day without a reading is a gap (null), never a zero. */
function rows(points: readonly TrendPoint[]): Row[] {
  if (points.length === 0) return [];
  const byDay = new Map(points.map((p) => [p.t, p]));
  const first = points[0]?.t ?? 0;
  const last = points.at(-1)?.t ?? first;
  const out: Row[] = [];
  for (let day = first; day <= last; day += DAY_MS) {
    const p = byDay.get(day) ?? null;
    out.push({
      t: day,
      median: p?.median ?? null,
      band: p !== null && p.low !== null && p.high !== null ? [p.low, p.high] : null,
      point: p,
    });
  }
  return out;
}

function ticksOf(first: number, last: number, count: number): number[] {
  if (last <= first) return [first];
  const days = Math.round((last - first) / DAY_MS);
  const steps = Math.min(count, days + 1);
  return Array.from(
    { length: steps },
    (_, i) => first + Math.round((days * i) / Math.max(steps - 1, 1)) * DAY_MS,
  );
}

function TooltipBody({
  active,
  payload,
}: {
  readonly active?: boolean;
  readonly payload?: readonly { payload?: Row }[];
}) {
  const row = payload?.[0]?.payload;
  if (active !== true || row === undefined || row.point === null) return null;
  const p = row.point;
  return (
    <div className={styles["tooltip"]}>
      <strong>
        {t.rynek.stats.tooltipDate}: {p.dayText}
      </strong>
      {p.withheld ? (
        <span>{t.rynek.stats.tooltipWithheld}</span>
      ) : (
        <>
          <span>
            {t.rynek.stats.tooltipMedian}: {p.medianText}
          </span>
          <span>
            {t.rynek.stats.tooltipBand}: {p.bandText}
          </span>
        </>
      )}
      <span>
        {t.rynek.stats.tooltipSample}: {p.sampleText}
      </span>
    </div>
  );
}

/**
 * The median asking rent per m² over time with its middle half (P25 to P75) as a hatched band. Days without a
 * reading are gaps in both; a single reading is one visible point and no line. Axes are labelled with units,
 * ticks are formatted by api/format.ts, and the chart is reachable by keyboard (arrow keys move the active point
 * and show its tooltip). Loaded lazily by `TrendChart`.
 */
export default function TrendChartImpl({ points, ariaLabel, yLabel, xLabel, height = 320 }: TrendChartProps) {
  const data = rows(points);
  const withValue = points.filter((p) => p.median !== null);
  const single = withValue.length === 1;
  const lows = points.flatMap((p) => (p.low === null ? [] : [p.low]));
  const highs = points.flatMap((p) => (p.high === null ? [] : [p.high]));
  const meds = withValue.map((p) => p.median ?? 0);
  const min = Math.min(...lows, ...meds);
  const max = Math.max(...highs, ...meds);
  const pad = Math.max((max - min) * 0.1, 1);
  const first = points[0]?.t ?? 0;
  const last = points.at(-1)?.t ?? first;
  return (
    <div role="group" aria-label={ariaLabel} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 640, height }}>
        <ComposedChart data={data} margin={{ top: 12, right: 16, bottom: 28, left: 8 }} accessibilityLayer>
          <CartesianGrid stroke="var(--chart-grid)" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={[first, last === first ? first + DAY_MS : last]}
            ticks={ticksOf(first, last, 5)}
            tickFormatter={(v: number) => formatDayMonth(new Date(v).toISOString())}
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
            width={64}
            domain={[Math.floor(min - pad), Math.ceil(max + pad)]}
            tickFormatter={(v: number) => formatAxisNumber(v, 0)}
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
          <Area
            dataKey="band"
            type="monotone"
            stroke="var(--chart-line)"
            strokeDasharray="2 3"
            strokeOpacity={0.6}
            fill="var(--chart-band)"
            fillOpacity={0.7}
            connectNulls={false}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            dataKey="median"
            type="linear"
            stroke="var(--chart-line)"
            strokeWidth={single ? 0 : 2.5}
            dot={{
              r: single || withValue.length <= 31 ? 4 : 0,
              fill: "var(--chart-line)",
              stroke: "var(--surface)",
              strokeWidth: 1,
            }}
            activeDot={{ r: 7, fill: "var(--chart-line)", stroke: "var(--surface)", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
