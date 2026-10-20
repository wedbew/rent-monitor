import { useState } from "react";

import { formatCount, formatDecimal, formatPercent } from "../../api/format";
import { DataTable } from "../../charts/DataTable";
import { MetricCard } from "../../charts/MetricCard";
import { plotValue, type StatMeta } from "../../charts/meta";
import { YearChart } from "../../charts/YearChart";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { failureOf } from "./failure";
import { type LocationContext, type MetricView, useLocationContext } from "./queries";
import styles from "./gus.module.css";

// LEGAL[third-party-data]: GUS BDL statistics shown with source, year and level (B-012) (RM-282, RM-439)
// LEGAL[republication]: aggregates only (RM-282)

const unitOf = (m: MetricView): string => (m.unit === "-" ? "" : m.unit);
const show = (m: MetricView, value: string | null): string =>
  value === null ? t.format.notComputed : `${formatDecimal(value, 2)} ${unitOf(m)}`.trim();

const directionText = (m: MetricView): string =>
  m.direction === "higher_is_favorable"
    ? t.rynek.stats.directionHigher
    : m.direction === "lower_is_favorable"
      ? t.rynek.stats.directionLower
      : t.rynek.gus.profile.neutral;

function metaOf(m: MetricView, placeName: string): StatMeta {
  const level = m.measured === null ? "" : t.rynek.gus.profile.level[m.measured.level];
  const rank = m.national;
  return {
    measure: m.name_pl,
    unit: unitOf(m) === "" ? m.family_pl : unitOf(m),
    area:
      m.measured === null
        ? placeName
        : m.state === "proxy"
          ? t.rynek.gus.profile.proxyArea({ unit: m.measured.name, level, place: placeName })
          : t.rynek.gus.profile.directArea({ unit: m.measured.name, level }),
    period:
      m.year === null ? t.rynek.sources.gusFacts.period : t.rynek.gus.profile.year({ year: String(m.year) }),
    source: t.rynek.sources.gusFacts.source,
    sample:
      rank !== null && rank !== undefined && rank.state === "ok" && rank.rank !== null && rank.of !== null
        ? t.rynek.gus.profile.rankSample({
            rank: formatCount(rank.rank),
            of: formatCount(rank.of),
            scope: rank.scope,
          })
        : t.rynek.gus.profile.noRank,
    interpretation: `${directionText(m)}. ${m.note_pl}`.trim(),
  };
}

function Series({ metric }: { readonly metric: MetricView }) {
  const [open, setOpen] = useState(false);
  const rows = metric.series;
  if (rows.length === 0) return null;
  const points = rows.map((p) => ({
    year: p.year,
    value: p.status === "measured" ? plotValue(p.value) : null,
    valueText: show(metric, p.value),
    note: (t.rynek.gus.profile.statuses as Record<string, string | undefined>)[p.status] ?? null,
  }));
  const values = points.filter((p) => p.value !== null).length;
  return (
    <details onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>{t.rynek.gus.profile.seriesToggle}</summary>
      {open ? (
        <>
          {values <= 1 ? <p className={styles["muted"]}>{t.rynek.stats.singlePoint}</p> : null}
          <YearChart
            points={points}
            ariaLabel={t.rynek.gus.profile.seriesLabel({ name: metric.name_pl })}
            yLabel={`${metric.name_pl}${unitOf(metric) === "" ? "" : ` (${unitOf(metric)})`}`}
            xLabel={t.rynek.stats.xAxisYear}
          />
          <DataTable
            caption={t.rynek.gus.profile.seriesLabel({ name: metric.name_pl })}
            columns={[
              { key: "year", header: t.rynek.gus.profile.year0 },
              { key: "value", header: t.rynek.stats.tooltipValue, numeric: true },
              { key: "note", header: t.rynek.gus.profile.status },
            ]}
            rows={points.map((p) => ({
              id: String(p.year),
              cells: { year: String(p.year), value: p.valueText, note: p.note ?? "" },
            }))}
          />
        </>
      ) : null}
    </details>
  );
}

function Card({ metric, placeName }: { readonly metric: MetricView; readonly placeName: string }) {
  const unavailable = metric.state === "unavailable" || metric.measured === null || metric.year === null;
  const tr = metric.trend;
  const trend =
    tr === null || tr === undefined
      ? null
      : tr.state !== "ok" || tr.movement === null || tr.from_year === null || tr.to_year === null
        ? t.rynek.gus.profile.trendSuppressed
        : t.rynek.gus.profile.trendSpan({
            from: String(tr.from_year),
            to: String(tr.to_year),
            movement: `${{ up: t.rynek.gus.profile.trendUp, down: t.rynek.gus.profile.trendDown, flat: t.rynek.gus.profile.trendFlat }[tr.movement]}${tr.percent_change === null ? "" : ` (${formatPercent(Number(tr.percent_change))})`}`,
          });
  return (
    <div id={`metric-${metric.key}`} className={styles["metric"]}>
      <MetricCard
        meta={metaOf(metric, placeName)}
        value={show(metric, metric.value)}
        {...(unavailable ? { unavailable: metric.reason ?? t.rynek.gus.profile.unavailable } : {})}
        context={
          <>
            {trend}
            {metric.parents.length === 0 ? null : (
              <span className={styles["context2"]}>
                {t.rynek.gus.profile.parents}:{" "}
                {metric.parents.map((p) => `${p.territory.name}: ${show(metric, p.value)}`).join("; ")}
              </span>
            )}
          </>
        }
        headingLevel={4}
      />
      {unavailable ? null : <Series metric={metric} />}
    </div>
  );
}

function Body({ context, placeName }: { readonly context: LocationContext; readonly placeName: string }) {
  const m = context.mapping;
  if (context.chain.length === 0)
    return (
      <InlineNotice tone="warning" title={t.rynek.gus.profile.unmappedTitle}>
        {t.rynek.gus.profile.unmappedBody}
      </InlineNotice>
    );
  const families = [...new Set(context.metrics.map((x) => x.family))];
  return (
    <>
      {m.status === "ambiguous" ? (
        <InlineNotice tone="warning" title={t.rynek.gus.profile.ambiguousTitle}>
          {t.rynek.gus.profile.ambiguousBody({ names: m.candidates.map((c) => c.name).join(", ") })}
        </InlineNotice>
      ) : null}
      {m.relation === "within_gmina" ? (
        <p className={styles["muted"]}>{t.rynek.gus.profile.withinNote}</p>
      ) : null}
      {context.published_metrics === 0 ? <p>{t.rynek.gus.profile.noMetrics}</p> : null}
      {families.map((family) => {
        const name = context.metrics.find((x) => x.family === family)?.family_pl ?? family;
        return (
          <section key={family} aria-label={name} className={styles["section"]}>
            <h3>{t.rynek.gus.profile.family({ name })}</h3>
            <div className={styles["grid"]}>
              {context.metrics
                .filter((x) => x.family === family)
                .map((x) => (
                  <Card key={x.key} metric={x} placeName={placeName} />
                ))}
            </div>
          </section>
        );
      })}
      <p className={styles["muted"]}>
        {t.rynek.gus.profile.sourceHeading}: {context.source.attribution_pl}
      </p>
    </>
  );
}

/** The GUS profile of the gmina a place belongs to: every published indicator as a card with its five answers. */
export function GusProfile({
  locationId,
  placeName,
}: {
  readonly locationId: string;
  readonly placeName: string;
}) {
  const q = useLocationContext(locationId);
  return (
    <section aria-labelledby="gus-profile" className={styles["section"]}>
      <h2 id="gus-profile">{t.rynek.gus.profile.heading}</h2>
      <p className={styles["muted"]}>{t.rynek.gus.profile.lead}</p>
      {q.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.rynek.gus.profile.loading}>
          <Skeleton height="160px" />
        </div>
      ) : q.isError ? (
        <InlineNotice
          tone="danger"
          title={t.rynek.gus.profile.failed}
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
        <Body context={q.data} placeName={placeName} />
      )}
    </section>
  );
}
