import { Component, lazy, Suspense, type ReactNode } from "react";

import { t } from "../i18n";
import type { TrendChartProps } from "./TrendChartImpl";

export type { TrendPoint } from "./TrendChartImpl";

// The chart library is the heaviest dependency: it loads when a chart is first shown (README "Bundle budget").
const Impl = lazy(() => import("./TrendChartImpl"));

class ChartBoundary extends Component<{ readonly children: ReactNode }, { readonly failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override render() {
    return this.state.failed ? <p role="status">{t.rynek.stats.chartFailed}</p> : this.props.children;
  }
}

/** The lazily loaded trend chart. While it loads, and if it fails, the text says so and the table still has the data. */
export function TrendChart(props: TrendChartProps) {
  return (
    <ChartBoundary>
      <Suspense
        fallback={
          <p role="status" style={{ minHeight: props.height ?? 320 }}>
            {t.rynek.stats.chartLoading}
          </p>
        }
      >
        <Impl {...props} />
      </Suspense>
    </ChartBoundary>
  );
}
