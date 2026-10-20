import { Link, useParams, useSearchParams } from "react-router";

import {
  formatCount,
  formatDate,
  formatDateTime,
  formatMoney,
  formatPricePerArea,
  NOT_COMPUTED,
} from "../../api/format";
import { BarCompare, type BarItem } from "../../charts/BarCompare";
import { ChartFigure, LegendItem, swatchClass } from "../../charts/ChartFigure";
import { DataTable } from "../../charts/DataTable";
import { MetricCard } from "../../charts/MetricCard";
import { plotValue } from "../../charts/meta";
import { TrendChart, type TrendPoint } from "../../charts/TrendChart";
import { t } from "../../i18n";
import { Button, LinkButton } from "../../ui/Button";
import { Segmented } from "../../ui/Segmented";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { districtAddress, districtKey, gusPlaceAddress, otodomAddress, OTODOM } from "./addresses";
import { CohortFilters } from "./CohortFilters";
import { cohortLabel, ROOMS_KEYS, SIZE_KEYS } from "./cohorts";
import { failureOf, isClosed, isNotFound } from "./failure";
import {
  type CohortKey,
  PERIOD_LABELS,
  PERIODS,
  readSelection,
  type Selection,
  SERIES,
  writeSelection,
} from "./filters";
import { useMarketTitle } from "./MarketLayout";
import {
  type AskingRent,
  type LocationDetail,
  useDistricts,
  useLocationDetail,
  useLocationHistory,
} from "./queries";
import { rangeMeta, ppm2Meta, rentMeta, sampleMeta, trendMeta, type AskingContext } from "./statMeta";
import { StatusBadge } from "./StatusBadge";
import styles from "./place.module.css";

// LEGAL[republication]: aggregates of Otodom asking rents for a place, never an offer or listing text (RM-422, RM-439)

const SERIES_LABELS = {
  cohort: t.rynek.place.trend.seriesCohort,
  additions: t.rynek.place.trend.seriesAdditions,
} as const;
const CAVEAT_TEXT: Readonly<Record<string, string | undefined>> = t.rynek.place.caveats;

const DAY_MS = 86_400_000;
const money = (value: string | null) => formatMoney(value, { decimals: 0 });

function Crumbs({ name }: { readonly name: string }) {
  return (
    <nav aria-label={t.rynek.place.crumbs} className={styles["crumbs"]}>
      <ol>
        <li>{t.rynek.place.crumbRynek}</li>
        <li>
          <Link to={OTODOM}>{t.rynek.place.crumbOtodom}</Link>
        </li>
        <li aria-current="page">{name}</li>
      </ol>
    </nav>
  );
}

function toTrend(points: readonly AskingRent[]): TrendPoint[] {
  return points.map((p) => ({
    iso: p.summary_date,
    t: Date.parse(`${p.summary_date}T00:00:00Z`),
    median: p.sufficient ? plotValue(p.median_ppm2) : null,
    low: p.sufficient ? plotValue(p.p25_ppm2) : null,
    high: p.sufficient ? plotValue(p.p75_ppm2) : null,
    dayText: formatDate(p.summary_date),
    medianText: formatPricePerArea(p.median_ppm2),
    bandText:
      p.p25_ppm2 === null || p.p75_ppm2 === null
        ? NOT_COMPUTED
        : t.rynek.range({
            low: formatPricePerArea(p.p25_ppm2),
            high: formatPricePerArea(p.p75_ppm2),
          }),
    sampleText: formatCount(p.priced_count),
    withheld: !p.sufficient,
  }));
}

function Trend({
  locationId,
  selection,
  choose,
  ctx,
  ready,
}: {
  readonly locationId: string;
  readonly selection: Selection;
  readonly choose: (patch: Partial<Selection>) => void;
  readonly ctx: AskingContext;
  readonly ready: boolean;
}) {
  const history = useLocationHistory(locationId, selection, ready);
  const points = history.data?.points ?? [];
  const trend = toTrend(points);
  const withValue = trend.filter((p) => p.median !== null);
  const first = points[0]?.summary_date ?? null;
  const last = points.at(-1)?.summary_date ?? null;
  const gaps = points.some((p, i) => {
    const prev = points[i - 1];
    return prev !== undefined && Date.parse(p.summary_date) - Date.parse(prev.summary_date) > DAY_MS;
  });
  return (
    <section aria-labelledby="place-trend" className={styles["section"]}>
      <h2 id="place-trend">{t.rynek.place.trend.heading}</h2>
      <div className={styles["controls"]}>
        <Segmented
          label={t.rynek.place.trend.seriesLabel}
          value={selection.series}
          options={SERIES.map((value) => ({ value, label: SERIES_LABELS[value] }))}
          onValueChange={(series) => choose({ series })}
        />
        <Segmented
          label={t.rynek.place.trend.periodLabel}
          value={String(selection.days)}
          options={PERIODS.map((days) => ({ value: String(days), label: PERIOD_LABELS[days] }))}
          onValueChange={(days) =>
            choose({ days: PERIODS.find((p) => String(p) === days) ?? selection.days })
          }
        />
      </div>
      <p className={styles["muted"]}>
        {selection.series === "cohort" ? t.rynek.place.trend.cohortNote : t.rynek.place.trend.additionsNote}
      </p>
      {history.isPending && ready ? (
        <div role="status" aria-busy="true" aria-label={t.rynek.place.trend.loading}>
          <Skeleton height="320px" />
        </div>
      ) : history.isError ? (
        <InlineNotice
          tone="danger"
          title={t.rynek.place.trend.failed}
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={history.isFetching}
              onClick={() => void history.refetch()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {failureOf(history.error).detail}
        </InlineNotice>
      ) : points.length === 0 ? (
        <InlineNotice tone="info" title={t.rynek.place.trend.noPoints}>
          {t.rynek.place.trend.noPointsBody}
        </InlineNotice>
      ) : (
        <ChartFigure
          title={t.rynek.place.trend.heading}
          meta={trendMeta(ctx, first, last)}
          legend={
            <>
              <LegendItem swatch={<span className={swatchClass.line} aria-hidden="true" />}>
                {t.rynek.stats.legendMedian}: {t.rynek.stats.legendMedianLine}
              </LegendItem>
              <LegendItem swatch={<span className={swatchClass.band} aria-hidden="true" />}>
                {t.rynek.stats.legendBand}: {t.rynek.stats.legendBandShade}
              </LegendItem>
            </>
          }
          note={
            withValue.length <= 1
              ? t.rynek.stats.singlePoint
              : withValue.length <= 3
                ? t.rynek.stats.fewPoints({ count: formatCount(withValue.length) })
                : gaps || withValue.length < trend.length
                  ? t.rynek.stats.gapNote
                  : undefined
          }
          table={
            <DataTable
              caption={t.rynek.place.trend.heading}
              columns={[
                { key: "day", header: t.rynek.stats.tooltipDate },
                { key: "median", header: t.rynek.stats.tooltipMedian, numeric: true },
                { key: "band", header: t.rynek.stats.tooltipBand, numeric: true },
                { key: "sample", header: t.rynek.stats.tooltipSample, numeric: true },
              ]}
              rows={[...trend].reverse().map((p) => ({
                id: p.iso,
                cells: {
                  day: p.dayText,
                  median: p.withheld ? t.rynek.stats.withheldBar : p.medianText,
                  band: p.withheld ? NOT_COMPUTED : p.bandText,
                  sample: p.sampleText,
                },
              }))}
            />
          }
        >
          <TrendChart
            points={trend}
            ariaLabel={t.rynek.place.trend.heading}
            yLabel={t.rynek.stats.yAxisPpm2}
            xLabel={t.rynek.stats.xAxis}
          />
        </ChartFigure>
      )}
    </section>
  );
}

function Structure({
  detail,
  cohort,
  ctx,
  onPick,
}: {
  readonly detail: LocationDetail;
  readonly cohort: CohortKey;
  readonly ctx: AskingContext;
  readonly onPick: (key: CohortKey) => void;
}) {
  const row = (key: CohortKey) => detail.cohort.find((c) => c.cohort_key === key);
  const make = (keys: readonly CohortKey[]): BarItem[] =>
    keys.flatMap((key) => {
      const r = row(key);
      if (r === undefined) return [];
      return [
        {
          id: key,
          name: cohortLabel(key),
          value: r.priced_count,
          valueText: formatCount(r.priced_count),
          meta: r.sufficient ? formatPricePerArea(r.median_ppm2) : t.rynek.stats.withheldBar,
          nameNode: (
            <button
              type="button"
              className={styles["groupButton"]}
              aria-pressed={cohort === key}
              aria-label={t.rynek.place.structure.pick({ name: cohortLabel(key) })}
              onClick={() => onPick(key)}
            >
              {cohortLabel(key)}
            </button>
          ),
        },
      ];
    });
  const sizes = make(SIZE_KEYS);
  const rooms = make(ROOMS_KEYS);
  if (sizes.length === 0 && rooms.length === 0) return null;
  const max = Math.max(1, ...[...sizes, ...rooms].map((b) => b.value ?? 0));
  const meta = {
    ...sampleMeta({ ...ctx, group: cohortLabel("all") }),
    measure: t.rynek.place.structure.heading,
    interpretation: t.rynek.place.structure.lead,
  };
  return (
    <section aria-labelledby="place-structure" className={styles["section"]}>
      <h2 id="place-structure">{t.rynek.place.structure.heading}</h2>
      <div className={styles["pair"]}>
        <ChartFigure
          title={t.rynek.place.structure.sizeTitle}
          meta={{ ...meta, measure: t.rynek.place.structure.sizeTitle }}
          table={
            <DataTable
              caption={t.rynek.place.structure.sizeTitle}
              columns={[
                { key: "group", header: t.rynek.filters.area },
                { key: "sample", header: t.rynek.place.cards.sample, numeric: true },
                { key: "ppm2", header: t.rynek.compare.ppm2, numeric: true },
              ]}
              rows={sizes.map((b) => ({
                id: b.id,
                cells: { group: b.name, sample: b.valueText, ppm2: b.meta ?? NOT_COMPUTED },
              }))}
            />
          }
        >
          <BarCompare items={sizes} max={max} label={t.rynek.place.structure.sizeTitle} />
        </ChartFigure>
        <ChartFigure
          title={t.rynek.place.structure.roomsTitle}
          meta={{ ...meta, measure: t.rynek.place.structure.roomsTitle }}
          table={
            <DataTable
              caption={t.rynek.place.structure.roomsTitle}
              columns={[
                { key: "group", header: t.rynek.filters.rooms },
                { key: "sample", header: t.rynek.place.cards.sample, numeric: true },
                { key: "ppm2", header: t.rynek.compare.ppm2, numeric: true },
              ]}
              rows={rooms.map((b) => ({
                id: b.id,
                cells: { group: b.name, sample: b.valueText, ppm2: b.meta ?? NOT_COMPUTED },
              }))}
            />
          }
        >
          <BarCompare items={rooms} max={max} label={t.rynek.place.structure.roomsTitle} />
        </ChartFigure>
      </div>
    </section>
  );
}

function Districts({
  locationId,
  cohort,
  ctx,
}: {
  readonly locationId: string;
  readonly cohort: CohortKey;
  readonly ctx: AskingContext;
}) {
  const districts = useDistricts(locationId, cohort);
  const data = districts.data;
  return (
    <section aria-labelledby="place-districts" className={styles["section"]}>
      <h2 id="place-districts">{t.rynek.place.districts.heading}</h2>
      <p className={styles["muted"]}>{t.rynek.place.districts.lead}</p>
      {districts.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.rynek.place.districts.loading}>
          <Skeleton height="160px" />
        </div>
      ) : districts.isError && data === undefined ? (
        <InlineNotice
          tone="danger"
          title={t.rynek.place.districts.failed}
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={districts.isFetching}
              onClick={() => void districts.refetch()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {failureOf(districts.error).detail}
        </InlineNotice>
      ) : data === undefined ? null : data.coverage === "none" ? (
        <InlineNotice tone="info" title={t.rynek.place.districts.noneTitle}>
          {t.rynek.place.districts.noneBody}
        </InlineNotice>
      ) : (
        <>
          <p className={styles["muted"]}>
            {t.rynek.place.districts.coverage({
              with: formatCount(data.offers_with_district),
              total: formatCount(data.offers_in_cohort),
            })}
          </p>
          {data.districts.every((d) => d.priced_count === 0) ? (
            <InlineNotice tone="warning" title={t.rynek.place.districts.emptyGroup} live="status" />
          ) : null}
          <ChartFigure
            title={t.rynek.place.districts.chartTitle}
            meta={{
              ...ppm2Meta({
                ...ctx,
                area: `${ctx.area}: ${t.rynek.place.districts.heading.toLowerCase()} wg Otodom`,
                pricedCount: data.offers_in_cohort,
              }),
              measure: t.rynek.place.districts.chartTitle,
            }}
            table={
              <DataTable
                caption={t.rynek.place.districts.tableCaption}
                columns={[
                  { key: "district", header: t.rynek.place.districts.columns.district },
                  { key: "ppm2", header: t.rynek.place.districts.columns.ppm2, numeric: true },
                  { key: "range", header: t.rynek.place.districts.columns.range, numeric: true },
                  { key: "sample", header: t.rynek.place.districts.columns.sample, numeric: true },
                  { key: "note", header: t.rynek.place.districts.columns.note },
                ]}
                rows={data.districts.map((d) => ({
                  id: d.district_id,
                  cells: {
                    district: (
                      <Link
                        to={districtAddress(locationId, districtKey(d.district_id), cohort)}
                        aria-label={t.rynek.place.districts.open({ name: d.name })}
                      >
                        {d.name}
                      </Link>
                    ),
                    ppm2: d.sufficient ? formatPricePerArea(d.median_ppm2) : NOT_COMPUTED,
                    range:
                      d.p25_ppm2 === null || d.p75_ppm2 === null
                        ? NOT_COMPUTED
                        : t.rynek.range({
                            low: formatPricePerArea(d.p25_ppm2),
                            high: formatPricePerArea(d.p75_ppm2),
                          }),
                    sample: formatCount(d.priced_count),
                    note:
                      d.priced_count === 0
                        ? t.rynek.place.districts.noOffers
                        : d.sufficient
                          ? ""
                          : t.rynek.place.districts.withheld,
                  },
                }))}
              />
            }
          >
            <BarCompare
              label={t.rynek.place.districts.chartTitle}
              items={data.districts.map((d) => ({
                id: d.district_id,
                name: d.name,
                value: d.sufficient ? plotValue(d.median_ppm2) : null,
                valueText: formatPricePerArea(d.median_ppm2),
                meta: t.rynek.stats.sampleLabel({ count: formatCount(d.priced_count) }),
                low: plotValue(d.p25_ppm2),
                high: plotValue(d.p75_ppm2),
                withheldText:
                  d.priced_count === 0 ? t.rynek.place.districts.noOffers : t.rynek.place.districts.withheld,
                nameNode: (
                  <Link to={districtAddress(locationId, districtKey(d.district_id), cohort)}>{d.name}</Link>
                ),
              }))}
            />
          </ChartFigure>
        </>
      )}
    </section>
  );
}

/**
 * One place of the Otodom tab: its status, the figures for the chosen group of flats as cards that each carry their
 * five answers, the median over time with its middle half, what the offers are made of (by area and by rooms), and the
 * districts the source names, each leading to its own page. Everything chosen is in the address.
 */
export function PlacePage() {
  const { locationId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const selection = readSelection(params);
  const detail = useLocationDetail(locationId);
  const place = detail.data;
  const readable = place !== undefined && place.data_status !== "unavailable";
  useMarketTitle(place?.name ?? null);

  const choose = (patch: Partial<Selection>) => setParams(writeSelection({ ...selection, ...patch }, ""));
  const back = (
    <LinkButton to={otodomAddress({ cohort: selection.cohort, sel: locationId })} icon="arrow" small>
      {t.rynek.place.back}
    </LinkButton>
  );

  if (detail.isPending)
    return (
      <div role="status" aria-busy="true" aria-label={t.rynek.place.loading}>
        <Skeleton height="64px" />
        <Skeleton height="200px" />
      </div>
    );
  if (place === undefined && isClosed(detail.error))
    return (
      <InlineNotice
        tone="info"
        title={t.rynek.place.closedTitle}
        live="alert"
        actions={
          <>
            {back}
            <LinkButton to="/app/credits" small>
              {t.rynek.access.buy}
            </LinkButton>
          </>
        }
      >
        {t.rynek.place.closedBody}
      </InlineNotice>
    );
  if (place === undefined)
    return isNotFound(detail.error) ? (
      <InlineNotice tone="warning" title={t.rynek.place.notFoundTitle} live="alert" actions={back}>
        {t.rynek.place.notFoundBody}
      </InlineNotice>
    ) : (
      <InlineNotice
        tone="danger"
        title={t.rynek.place.failed}
        live="alert"
        actions={
          <Button
            type="button"
            variant="primary"
            icon="refresh"
            busy={detail.isFetching}
            onClick={() => void detail.refetch()}
          >
            {t.common.retry}
          </Button>
        }
      >
        {failureOf(detail.error).detail}
      </InlineNotice>
    );

  const group = cohortLabel(selection.cohort);
  const reading = place.cohort.find((c) => c.cohort_key === selection.cohort);
  const ctx: AskingContext = {
    area: `${place.name}, ${t.rynek.place.areaKind}`,
    group,
    day: reading?.summary_date ?? null,
    pricedCount: reading?.priced_count ?? null,
  };
  const caveats = reading?.caveats ?? place.cohort[0]?.caveats ?? [];

  return (
    <div className={styles["page"]}>
      <Crumbs name={place.name} />
      <div>{back}</div>
      <section className={styles["status"]} aria-label={t.rynek.place.status[place.data_status]}>
        <StatusBadge status={place.data_status} />
        <span>{t.rynek.place.statusNote[place.data_status]}</span>
        <span className={styles["muted"]}>
          {place.last_successful_refresh_at === null
            ? t.rynek.sources.noRefresh
            : t.rynek.sources.freshness({ when: formatDateTime(place.last_successful_refresh_at) })}
        </span>
        {place.unresolved_gap_since === null ? null : (
          <span className={styles["muted"]}>
            {t.rynek.place.gap({ since: formatDate(place.unresolved_gap_since) })}
          </span>
        )}
      </section>

      {readable ? (
        <>
          <CohortFilters value={selection.cohort} onChange={(cohort) => choose({ cohort })} />

          <section aria-labelledby="place-summary" className={styles["section"]}>
            <h2 id="place-summary">{t.rynek.place.summary}</h2>
            <p className={styles["muted"]}>
              {reading === undefined
                ? t.rynek.filters.noPlacesInGroup
                : t.rynek.place.summaryLead({ filter: group, day: formatDate(reading.summary_date) })}
            </p>
            {reading === undefined ? null : (
              <div className={styles["cards"]}>
                <MetricCard
                  meta={ppm2Meta(ctx)}
                  value={formatPricePerArea(reading.median_ppm2)}
                  {...(reading.sufficient ? {} : { unavailable: t.rynek.place.withheldCard })}
                  headingLevel={3}
                />
                <MetricCard
                  meta={rentMeta(ctx)}
                  value={money(reading.median_rent_pln)}
                  {...(reading.sufficient ? {} : { unavailable: t.rynek.place.withheldCard })}
                  headingLevel={3}
                />
                <MetricCard
                  meta={rangeMeta(ctx)}
                  value={
                    reading.p25_ppm2 === null || reading.p75_ppm2 === null
                      ? NOT_COMPUTED
                      : t.rynek.range({
                          low: formatPricePerArea(reading.p25_ppm2),
                          high: formatPricePerArea(reading.p75_ppm2),
                        })
                  }
                  {...(reading.sufficient ? {} : { unavailable: t.rynek.place.withheldCard })}
                  headingLevel={3}
                />
                <MetricCard
                  meta={sampleMeta(ctx)}
                  value={formatCount(reading.priced_count)}
                  headingLevel={3}
                />
              </div>
            )}
          </section>

          <Trend locationId={locationId} selection={selection} choose={choose} ctx={ctx} ready={readable} />
          <Structure
            detail={place}
            cohort={selection.cohort}
            ctx={ctx}
            onPick={(cohort) => choose({ cohort })}
          />
          <Districts locationId={locationId} cohort={selection.cohort} ctx={ctx} />

          <section aria-labelledby="place-gus" className={styles["section"]}>
            <h2 id="place-gus">{t.rynek.place.context.heading}</h2>
            <p>{t.rynek.place.context.body}</p>
            <div>
              <LinkButton to={gusPlaceAddress(locationId)} icon="arrow">
                {t.rynek.place.context.action}
              </LinkButton>
            </div>
          </section>

          <section aria-labelledby="place-caveats" className={styles["section"]}>
            <h2 id="place-caveats">{t.rynek.place.caveatsHeading}</h2>
            <ul className={styles["caveats"]}>
              {caveats.map((code) => {
                const known = CAVEAT_TEXT[code];
                return known === undefined ? null : <li key={code}>{known}</li>;
              })}
              <li>{t.rynek.stats.median}</li>
              <li>{t.rynek.stats.quartiles}</li>
            </ul>
          </section>
        </>
      ) : (
        <InlineNotice tone="info" title={t.rynek.place.unavailableTitle}>
          {t.rynek.place.unavailableBody}
        </InlineNotice>
      )}
    </div>
  );
}
