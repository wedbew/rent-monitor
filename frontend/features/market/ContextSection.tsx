import { formatCount, formatDecimal, formatPercent } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { failureOf } from "./failure";
import { type LocationContext, type MetricView, useLocationContext } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import styles from "./context.module.css";

// LEGAL[third-party-data]: GUS BDL statistics shown with source, year and level (B-012) (RM-282)
// LEGAL[republication]: aggregates only (RM-282)

const unitOf = (m: MetricView): string => (m.unit === "-" ? "" : m.unit);
const show = (m: MetricView, value: string | null): string =>
  value === null ? t.format.notComputed : `${formatDecimal(value, 2)} ${unitOf(m)}`.trim();

function Spark({ metric }: { readonly metric: MetricView }) {
  const points = metric.series.filter((p) => p.value !== null);
  if (points.length < 2) return null;
  const nums = points.map((p) => Number(p.value));
  const lo = Math.min(...nums);
  const hi = Math.max(...nums);
  const span = hi - lo || 1;
  const first = points[0]?.year ?? 0;
  const last = points.at(-1)?.year ?? 1;
  const d = points
    .map((p, i) => {
      const x = ((p.year - first) / Math.max(last - first, 1)) * 100;
      const y = 28 - ((Number(p.value) - lo) / span) * 26;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join("");
  return (
    <svg
      className={styles["spark"]}
      viewBox="-2 0 104 30"
      role="img"
      aria-label={t.market.context.seriesLabel({ name: metric.name_pl })}
    >
      <path d={d} />
    </svg>
  );
}

function Trend({ metric }: { readonly metric: MetricView }) {
  const tr = metric.trend;
  if (tr === null || tr === undefined) return null;
  if (tr.state !== "ok" || tr.movement === null || tr.from_year === null || tr.to_year === null)
    return <p className={styles["muted"]}>{t.market.context.trendSuppressed}</p>;
  const word = {
    up: t.market.context.trendUp,
    down: t.market.context.trendDown,
    flat: t.market.context.trendFlat,
  }[tr.movement];
  const pct = tr.percent_change === null ? "" : ` (${formatPercent(Number(tr.percent_change))})`;
  return (
    <p>
      {t.market.context.trendSpan({
        from: String(tr.from_year),
        to: String(tr.to_year),
        movement: `${word}${pct}`,
      })}
    </p>
  );
}

function Rank({ label, rank }: { readonly label: string; readonly rank: MetricView["national"] }) {
  if (rank === null || rank === undefined) return null;
  return (
    <p className={styles["muted"]}>
      {label}:{" "}
      {rank.state === "ok" && rank.rank !== null && rank.of !== null
        ? t.market.context.rank({ rank: formatCount(rank.rank), of: formatCount(rank.of) })
        : t.market.context.suppressed}
    </p>
  );
}

function Card({ metric }: { readonly metric: MetricView }) {
  const unavailable = metric.state === "unavailable";
  return (
    <article className={styles["card"]} aria-label={metric.name_pl}>
      <h4>{metric.name_pl}</h4>
      {unavailable || metric.measured === null || metric.year === null ? (
        <p className={styles["muted"]}>{metric.reason ?? t.market.context.unavailable}</p>
      ) : (
        <>
          <p className={styles["value"]}>{show(metric, metric.value)}</p>
          <p className={styles["muted"]}>
            {t.market.context.measuredAt({ unit: metric.measured.name, year: String(metric.year) })}
            {" · "}
            {metric.state === "proxy" ? t.market.context.proxy : t.market.context.direct}
          </p>
          {metric.reason === null ? null : <p className={styles["muted"]}>{metric.reason}</p>}
          <Trend metric={metric} />
          <Spark metric={metric} />
          {metric.parents.length === 0 ? null : (
            <p className={styles["muted"]}>
              {t.market.context.parentsLabel}:{" "}
              {metric.parents.map((p) => `${p.territory.name}: ${show(metric, p.value)}`).join("; ")}
            </p>
          )}
          <Rank label={t.market.context.national} rank={metric.national} />
          <Rank label={t.market.context.peers} rank={metric.peers} />
        </>
      )}
      {metric.note_pl === "" ? null : <p className={styles["muted"]}>{metric.note_pl}</p>}
      {metric.series.length === 0 ? null : (
        <details>
          <summary>{t.market.context.seriesTable}</summary>
          <ScrollRegion label={t.market.context.seriesTable}>
            <table className={styles["table"]}>
              <thead>
                <tr>
                  <th scope="col">{t.market.context.year}</th>
                  <th scope="col">{t.market.context.value}</th>
                  <th scope="col">{t.market.context.status}</th>
                </tr>
              </thead>
              <tbody>
                {metric.series.map((p) => (
                  <tr key={p.year}>
                    <th scope="row">{p.year}</th>
                    <td>{show(metric, p.value)}</td>
                    <td>
                      {(t.market.context.statuses as Record<string, string | undefined>)[p.status] ?? ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </details>
      )}
    </article>
  );
}

function Body({ context }: { readonly context: LocationContext }) {
  const m = context.mapping;
  if (context.chain.length === 0)
    return (
      <InlineNotice tone="warning" title={t.market.context.unmappedTitle}>
        {t.market.context.unmappedBody}
      </InlineNotice>
    );
  const families = [...new Set(context.metrics.map((x) => x.family))];
  return (
    <>
      {m.status === "ambiguous" ? (
        <InlineNotice tone="warning" title={t.market.context.ambiguousTitle}>
          {t.market.context.ambiguousBody({ names: m.candidates.map((c) => c.name).join(", ") })}
        </InlineNotice>
      ) : null}
      {m.relation === "within_gmina" ? (
        <p className={styles["muted"]}>{t.market.context.withinNote}</p>
      ) : null}
      {context.published_metrics === 0 ? <p>{t.market.context.noMetrics}</p> : null}
      {families.map((family) => (
        <section key={family} aria-label={context.metrics.find((x) => x.family === family)?.family_pl}>
          <h3>{context.metrics.find((x) => x.family === family)?.family_pl}</h3>
          <div className={styles["grid"]}>
            {context.metrics
              .filter((x) => x.family === family)
              .map((x) => (
                <Card key={x.key} metric={x} />
              ))}
          </div>
        </section>
      ))}
      <p className={styles["muted"]}>
        {t.market.context.sourceHeading}: {context.source.attribution_pl}
      </p>
    </>
  );
}

export function ContextSection({ locationId }: { readonly locationId: string }) {
  const q = useLocationContext(locationId);
  return (
    <section aria-labelledby="market-context">
      <h2 id="market-context">{t.market.context.heading}</h2>
      <p className={styles["muted"]}>{t.market.context.lead}</p>
      {q.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.market.context.loading}>
          <Skeleton height="120px" />
        </div>
      ) : q.isError ? (
        <InlineNotice
          tone="danger"
          title={t.market.context.failed}
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={q.isFetching}
              onClick={() => void q.refetch()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {failureOf(q.error).detail}
        </InlineNotice>
      ) : (
        <Body context={q.data} />
      )}
    </section>
  );
}
