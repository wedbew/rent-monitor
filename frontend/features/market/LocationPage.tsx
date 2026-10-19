import { useParams, useSearchParams } from "react-router";

import {
  formatCount,
  formatDate,
  formatDateTime,
  formatMoney,
  formatPricePerArea,
  NOT_COMPUTED,
} from "../../api/format";
import { t } from "../../i18n";
import { PageHeading } from "../../shell/PageHeading";
import { Button, LinkButton } from "../../ui/Button";
import { Segmented } from "../../ui/Segmented";
import { Select } from "../../ui/Select";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { failureOf, isNotFound } from "./failure";
import {
  type CohortKey,
  cleanSearch,
  cohortOptions,
  listAddress,
  PERIOD_LABELS,
  PERIODS,
  readSelection,
  type Selection,
  SERIES,
  writeSelection,
} from "./filters";
import { type AskingRent, type LocationDetail, useLocationDetail, useLocationHistory } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import { StatusBadge } from "./StatusBadge";
import styles from "./market.module.css";

const SERIES_LABELS = {
  cohort: t.market.detail.seriesCohort,
  additions: t.market.detail.seriesAdditions,
} as const;

/** Codes the server may add later are skipped, not shown raw. */
const CAVEAT_TEXT: Readonly<Record<string, string | undefined>> = t.market.detail.caveats;

const money = (value: string | null) => formatMoney(value, { decimals: 0 });

function Metric({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/** The newest reading, with the numbers withheld (and the reason given) when the sample was too small. */
function Latest({ reading }: { readonly reading: AskingRent }) {
  const withheld = reading.withheld_reason !== null;
  const range =
    reading.p25_ppm2 === null || reading.p75_ppm2 === null
      ? NOT_COMPUTED
      : t.market.detail.range({
          low: formatPricePerArea(reading.p25_ppm2),
          high: formatPricePerArea(reading.p75_ppm2),
        });
  return (
    <section className={styles["latest"]} aria-labelledby="market-latest">
      <h2 id="market-latest">{t.market.detail.latestHeading}</h2>
      <p className={styles["count"]}>
        {t.market.detail.latestDate({ when: formatDate(reading.summary_date) })}
      </p>
      {withheld ? <InlineNotice tone="warning" title={t.market.withheld.insufficient_sample} /> : null}
      <dl className={styles["metrics"]}>
        <Metric label={t.market.detail.metrics.medianRent} value={money(reading.median_rent_pln)} />
        <Metric label={t.market.detail.metrics.medianPpm2} value={formatPricePerArea(reading.median_ppm2)} />
        <Metric label={t.market.detail.metrics.range} value={range} />
        <Metric label={t.market.detail.metrics.sample} value={formatCount(reading.priced_count)} />
        <Metric label={t.market.detail.metrics.observed} value={formatCount(reading.observed_count)} />
        {reading.first_observed_count === null ? null : (
          <Metric
            label={t.market.detail.metrics.firstSeen}
            value={formatCount(reading.first_observed_count)}
          />
        )}
      </dl>
    </section>
  );
}

function History({ points }: { readonly points: readonly AskingRent[] }) {
  const newestFirst = [...points].reverse();
  return (
    <section aria-labelledby="market-history">
      <h2 id="market-history">{t.market.detail.historyHeading}</h2>
      <ScrollRegion label={t.market.detail.historyHeading}>
        <table className={styles["table"]}>
          <caption>{t.market.detail.historyCaption}</caption>
          <thead>
            <tr>
              <th scope="col">{t.market.detail.historyColumns.date}</th>
              <th scope="col" className={styles["num"]}>
                {t.market.detail.historyColumns.medianRent}
              </th>
              <th scope="col" className={styles["num"]}>
                {t.market.detail.historyColumns.medianPpm2}
              </th>
              <th scope="col" className={styles["num"]}>
                {t.market.detail.historyColumns.sample}
              </th>
              <th scope="col">{t.market.detail.historyColumns.note}</th>
            </tr>
          </thead>
          <tbody>
            {newestFirst.map((point) => (
              <tr key={`${point.summary_date}-${point.cohort_key}`}>
                <th scope="row">{formatDate(point.summary_date)}</th>
                <td className={styles["num"]}>{money(point.median_rent_pln)}</td>
                <td className={styles["num"]}>{formatPricePerArea(point.median_ppm2)}</td>
                <td className={styles["num"]}>{formatCount(point.priced_count)}</td>
                <td>
                  {[
                    point.withheld_reason === null ? null : t.market.withheld[point.withheld_reason],
                    point.backfilled ? t.market.detail.backfilled : null,
                  ]
                    .filter((note) => note !== null)
                    .join("; ") || NOT_COMPUTED}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

function Status({ place }: { readonly place: LocationDetail }) {
  return (
    <section className={styles["statusBar"]} aria-label={t.market.status[place.data_status]}>
      <StatusBadge status={place.data_status} />
      <span>{t.market.statusNote[place.data_status]}</span>
      <span className={styles["count"]}>
        {place.last_successful_refresh_at === null
          ? t.market.detail.neverRefreshed
          : t.market.detail.freshness({ when: formatDateTime(place.last_successful_refresh_at) })}
      </span>
      {place.unresolved_gap_since === null ? null : (
        <span className={styles["count"]}>
          {t.market.detail.gap({ since: formatDate(place.unresolved_gap_since) })}
        </span>
      )}
    </section>
  );
}

// LEGAL[republication]: shows aggregates of Otodom asking rents for a place, never an offer or listing text (RM-422)
/**
 * One place. The series, the cohort and the period are in the address and read against a closed vocabulary; the
 * cohorts offered are those the API published for this place. The two series are never drawn together, a day
 * without a reading is absent from the table (never a zero) and an unavailable place shows no numbers at all.
 */
export function LocationPage() {
  const { locationId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const q = cleanSearch(params.get("q"));
  const selection = readSelection(params);
  const detail = useLocationDetail(locationId);
  const place = detail.data;
  const readable = place !== undefined && place.data_status !== "unavailable";
  const history = useLocationHistory(locationId, selection, readable);

  const choose = (patch: Partial<Selection>) => setParams(writeSelection({ ...selection, ...patch }, q));
  const back = (
    <LinkButton to={listAddress(q)} icon="arrow" small>
      {t.market.detail.back}
    </LinkButton>
  );

  if (detail.isPending) {
    return (
      <div className={styles["page"]}>
        <PageHeading title={t.market.title} eyebrow={t.market.eyebrow} />
        <div
          className={styles["skeletons"]}
          role="status"
          aria-busy="true"
          aria-label={t.market.detail.loading}
        >
          <Skeleton height="64px" />
          <Skeleton height="160px" />
        </div>
      </div>
    );
  }
  if (place === undefined) {
    const missing = isNotFound(detail.error);
    return (
      <div className={styles["page"]}>
        <PageHeading title={t.market.title} eyebrow={t.market.eyebrow} />
        {missing ? (
          <InlineNotice tone="warning" title={t.market.detail.notFoundTitle} live="alert" actions={back}>
            {t.market.detail.notFoundBody}
          </InlineNotice>
        ) : (
          <InlineNotice
            tone="danger"
            title={t.market.detail.failed}
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
        )}
      </div>
    );
  }

  const points = history.data?.points ?? [];
  const latest = points.at(-1);
  return (
    <div className={styles["page"]}>
      <PageHeading title={place.name} eyebrow={t.market.eyebrow} />
      <div>{back}</div>
      <Status place={place} />

      {readable ? (
        <>
          <section className={styles["controls"]} aria-label={t.market.detail.controlsLabel}>
            <Segmented
              label={t.market.detail.seriesLabel}
              value={selection.series}
              options={SERIES.map((value) => ({ value, label: SERIES_LABELS[value] }))}
              onValueChange={(series) => choose({ series })}
            />
            <Segmented
              label={t.market.detail.periodLabel}
              value={String(selection.days)}
              options={PERIODS.map((days) => ({ value: String(days), label: PERIOD_LABELS[days] }))}
              onValueChange={(days) =>
                choose({ days: PERIODS.find((p) => String(p) === days) ?? selection.days })
              }
            />
            <Select
              label={t.market.detail.cohortLabel}
              value={selection.cohort}
              options={cohortOptions(
                place.cohort.map((c) => c.cohort_key),
                selection.cohort,
              )}
              onValueChange={(cohort) => choose({ cohort: cohort as CohortKey })}
            />
          </section>
          <p className={styles["count"]}>
            {selection.series === "cohort"
              ? t.market.detail.seriesCohortNote
              : t.market.detail.seriesAdditionsNote}
          </p>

          {history.isPending ? (
            <div
              className={styles["skeletons"]}
              role="status"
              aria-busy="true"
              aria-label={t.market.detail.loading}
            >
              <Skeleton height="120px" />
            </div>
          ) : history.isError ? (
            <InlineNotice
              tone="danger"
              title={t.market.detail.failed}
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
          ) : latest === undefined ? (
            <div className={styles["empty"]}>
              <strong>{t.market.detail.noPoints}</strong>
              <p>{t.market.detail.noPointsBody}</p>
            </div>
          ) : (
            <>
              <Latest reading={latest} />
              <History points={points} />
            </>
          )}

          <section aria-labelledby="market-caveats">
            <h2 id="market-caveats">{t.market.detail.caveatsHeading}</h2>
            <ul className={styles["caveats"]}>
              {(latest?.caveats ?? place.cohort[0]?.caveats ?? []).map((code) => {
                const known = CAVEAT_TEXT[code];
                return known === undefined ? null : <li key={code}>{known}</li>;
              })}
            </ul>
            <p className={styles["count"]}>{t.market.detail.source}</p>
          </section>
        </>
      ) : null}
    </div>
  );
}
