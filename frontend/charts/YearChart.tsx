import { Component, lazy, Suspense, type ReactNode } from "react";

import { t } from "../i18n";
import type { YearChartProps } from "./YearChartImpl";

export type { YearPoint } from "./YearChartImpl";

const Impl = lazy(() => import("./YearChartImpl"));

class Boundary extends Component<{ readonly children: ReactNode }, { readonly failed: boolean }> {
  override state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  override render() {
    return this.state.failed ? <p role="status">{t.rynek.stats.chartFailed}</p> : this.props.children;
  }
}

/** The lazily loaded annual chart (same chart library as `TrendChart`, one shared chunk). */
export function YearChart(props: YearChartProps) {
  return (
    <Boundary>
      <Suspense
        fallback={
          <p role="status" style={{ minHeight: props.height ?? 240 }}>
            {t.rynek.stats.chartLoading}
          </p>
        }
      >
        <Impl {...props} />
      </Suspense>
    </Boundary>
  );
}
