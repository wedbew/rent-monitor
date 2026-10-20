import { Link, useParams, useSearchParams } from "react-router";

import { formatCount, formatPricePerArea, NOT_COMPUTED } from "../../api/format";
import { BarCompare } from "../../charts/BarCompare";
import { ChartFigure } from "../../charts/ChartFigure";
import { DataTable } from "../../charts/DataTable";
import { MetricCard } from "../../charts/MetricCard";
import { plotValue } from "../../charts/meta";
import { t } from "../../i18n";
import { Button, LinkButton } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { districtAddress, districtKey, OTODOM, placeAddress } from "./addresses";
import { CohortFilters } from "./CohortFilters";
import { cohortLabel } from "./cohorts";
import { failureOf, isClosed, isNotFound } from "./failure";
import { COHORT_KEYS, type CohortKey } from "./filters";
import { useMarketTitle } from "./MarketLayout";
import { useDistricts, useLocationDetail } from "./queries";
import { type AskingContext, ppm2Meta, rangeMeta, sampleMeta } from "./statMeta";
import styles from "./place.module.css";

const MIN_PRICED = 10;

/**
 * One district of one place, as the source names it. It shows only what the district's own offers say: its median and
 * middle half for the chosen group of flats, its sample, and the place's median beside it for scale. When the
 * district has too few priced offers it says so with the count and shows no median; when the place has no districts
 * at the source, or this one is gone, it says that instead. There is no history here, and the page says why.
 */
export function DistrictPage() {
  const { locationId = "", districtKey: key = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const raw = params.get("cohort");
  const cohort: CohortKey = COHORT_KEYS.find((c) => c === raw) ?? "all";
  const place = useLocationDetail(locationId);
  const districts = useDistricts(locationId, cohort);
  const district = districts.data?.districts.find((d) => districtKey(d.district_id) === key);
  useMarketTitle(district?.name ?? place.data?.name ?? null);

  const back = (
    <LinkButton to={placeAddress(locationId, cohort)} icon="arrow" small>
      {t.rynek.district.back({ place: place.data?.name ?? t.rynek.place.crumbOtodom })}
    </LinkButton>
  );

  if (place.isPending || (districts.isPending && districts.data === undefined))
    return (
      <div role="status" aria-busy="true" aria-label={t.rynek.district.loading}>
        <Skeleton height="200px" />
      </div>
    );
  if (place.data === undefined)
    return isClosed(place.error) ? (
      <InlineNotice tone="info" title={t.rynek.place.closedTitle} live="alert" actions={back}>
        {t.rynek.place.closedBody}
      </InlineNotice>
    ) : isNotFound(place.error) ? (
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
            busy={place.isFetching}
            onClick={() => void place.refetch()}
          >
            {t.common.retry}
          </Button>
        }
      >
        {failureOf(place.error).detail}
      </InlineNotice>
    );
  if (districts.data === undefined)
    return (
      <InlineNotice tone="danger" title={t.rynek.place.districts.failed} live="alert" actions={back}>
        {failureOf(districts.error).detail}
      </InlineNotice>
    );

  const data = districts.data;
  const cityRow = place.data.cohort.find((c) => c.cohort_key === cohort);
  const crumbs = (name: string) => (
    <nav aria-label={t.rynek.place.crumbs} className={styles["crumbs"]}>
      <ol>
        <li>{t.rynek.place.crumbRynek}</li>
        <li>
          <Link to={OTODOM}>{t.rynek.place.crumbOtodom}</Link>
        </li>
        <li>
          <Link to={placeAddress(locationId, cohort)}>{place.data?.name}</Link>
        </li>
        <li aria-current="page">{name}</li>
      </ol>
    </nav>
  );
  const choose = (next: CohortKey) => {
    const p = new URLSearchParams(params);
    if (next === "all") p.delete("cohort");
    else p.set("cohort", next);
    setParams(p);
  };

  if (data.coverage === "none")
    return (
      <div className={styles["page"]}>
        {crumbs(key)}
        <div>{back}</div>
        <InlineNotice tone="info" title={t.rynek.district.unsupportedTitle} live="status">
          {t.rynek.district.unsupportedBody} {t.rynek.place.districts.noneBody}
        </InlineNotice>
      </div>
    );
  if (district === undefined)
    return (
      <div className={styles["page"]}>
        {crumbs(key)}
        <div>{back}</div>
        <InlineNotice tone="warning" title={t.rynek.district.notFoundTitle} live="alert">
          {t.rynek.district.notFoundBody}
        </InlineNotice>
      </div>
    );

  const group = cohortLabel(cohort);
  const ctx: AskingContext = {
    area: `${district.name}, ${t.rynek.district.areaKind} ${place.data.name}`,
    group,
    day: cityRow?.summary_date ?? null,
    pricedCount: district.priced_count,
  };
  const others = data.districts.filter((d) => d.district_id !== district.district_id);
  const shown = district.sufficient;

  return (
    <div className={styles["page"]}>
      {crumbs(district.name)}
      <div>{back}</div>
      <p className={styles["muted"]}>{t.rynek.district.source}</p>
      <CohortFilters value={cohort} onChange={choose} />

      {district.priced_count === 0 ? (
        <InlineNotice tone="warning" title={t.rynek.district.noOffersTitle} live="status">
          {t.rynek.district.noOffersBody}
        </InlineNotice>
      ) : shown ? null : (
        <InlineNotice tone="warning" title={t.rynek.district.insufficientTitle} live="status">
          {t.rynek.district.insufficientBody({
            sample: formatCount(district.priced_count),
            min: formatCount(MIN_PRICED),
          })}
        </InlineNotice>
      )}

      <section aria-labelledby="district-cards" className={styles["section"]}>
        <h2 id="district-cards">{t.rynek.district.heading({ name: district.name })}</h2>
        <div className={styles["cards"]}>
          <MetricCard
            meta={ppm2Meta(ctx)}
            value={formatPricePerArea(district.median_ppm2)}
            {...(shown ? {} : { unavailable: t.rynek.place.withheldCard })}
          />
          <MetricCard
            meta={rangeMeta(ctx)}
            value={
              district.p25_ppm2 === null || district.p75_ppm2 === null
                ? NOT_COMPUTED
                : t.rynek.range({
                    low: formatPricePerArea(district.p25_ppm2),
                    high: formatPricePerArea(district.p75_ppm2),
                  })
            }
            {...(shown ? {} : { unavailable: t.rynek.place.withheldCard })}
          />
          <MetricCard meta={sampleMeta(ctx)} value={formatCount(district.priced_count)} />
        </div>
      </section>

      <section aria-labelledby="district-vs-city" className={styles["section"]}>
        <h2 id="district-vs-city">{t.rynek.district.vsCity}</h2>
        <ChartFigure
          title={t.rynek.district.vsCity}
          meta={{
            ...ppm2Meta(ctx),
            measure: t.rynek.district.vsCity,
            interpretation: t.rynek.district.vsCityLead,
          }}
          table={
            <DataTable
              caption={t.rynek.district.vsCity}
              columns={[
                { key: "area", header: t.rynek.compare.metric },
                { key: "ppm2", header: t.rynek.compare.ppm2, numeric: true },
                { key: "range", header: t.rynek.compare.quartiles, numeric: true },
                { key: "sample", header: t.rynek.compare.sample, numeric: true },
              ]}
              rows={[
                {
                  id: "district",
                  cells: {
                    area: district.name,
                    ppm2: shown ? formatPricePerArea(district.median_ppm2) : t.rynek.stats.withheldBar,
                    range:
                      shown && district.p25_ppm2 !== null && district.p75_ppm2 !== null
                        ? `${formatPricePerArea(district.p25_ppm2)} – ${formatPricePerArea(district.p75_ppm2)}`
                        : NOT_COMPUTED,
                    sample: formatCount(district.priced_count),
                  },
                },
                {
                  id: "city",
                  cells: {
                    area: place.data.name,
                    ppm2: cityRow?.sufficient
                      ? formatPricePerArea(cityRow.median_ppm2)
                      : t.rynek.stats.withheldBar,
                    range:
                      cityRow?.p25_ppm2 && cityRow.p75_ppm2
                        ? `${formatPricePerArea(cityRow.p25_ppm2)} – ${formatPricePerArea(cityRow.p75_ppm2)}`
                        : NOT_COMPUTED,
                    sample: cityRow === undefined ? NOT_COMPUTED : formatCount(cityRow.priced_count),
                  },
                },
              ]}
            />
          }
        >
          <BarCompare
            label={t.rynek.district.vsCity}
            items={[
              {
                id: "district",
                name: `${t.rynek.district.districtMedian}: ${district.name}`,
                value: shown ? plotValue(district.median_ppm2) : null,
                valueText: formatPricePerArea(district.median_ppm2),
                meta: t.rynek.stats.sampleLabel({ count: formatCount(district.priced_count) }),
                low: plotValue(district.p25_ppm2),
                high: plotValue(district.p75_ppm2),
                withheldText:
                  district.priced_count === 0
                    ? t.rynek.place.districts.noOffers
                    : t.rynek.place.districts.withheld,
              },
              {
                id: "city",
                name: `${t.rynek.district.cityMedian}: ${place.data.name}`,
                value: cityRow?.sufficient ? plotValue(cityRow.median_ppm2) : null,
                valueText: formatPricePerArea(cityRow?.median_ppm2),
                meta: t.rynek.stats.sampleLabel({ count: formatCount(cityRow?.priced_count ?? 0) }),
                low: plotValue(cityRow?.p25_ppm2),
                high: plotValue(cityRow?.p75_ppm2),
                alt: true,
              },
            ]}
          />
        </ChartFigure>
        <p className={styles["muted"]}>{t.rynek.district.noHistory}</p>
      </section>

      {others.length === 0 ? null : (
        <section aria-labelledby="district-others" className={styles["section"]}>
          <h2 id="district-others">{t.rynek.district.others}</h2>
          <ul className={styles["caveats"]}>
            {others.map((d) => (
              <li key={d.district_id}>
                <Link to={districtAddress(locationId, districtKey(d.district_id), cohort)}>{d.name}</Link>
                {": "}
                {d.sufficient ? formatPricePerArea(d.median_ppm2) : t.rynek.stats.withheldBar} (
                {t.rynek.stats.sampleLabel({ count: formatCount(d.priced_count) })})
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
