import { useQueries } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";

import { api, unwrap } from "../../api/client";
import { tenantKey } from "../../api/query";
import {
  formatCount,
  formatCounted,
  formatDecimal,
  formatMoney,
  formatPricePerArea,
  NOT_COMPUTED,
} from "../../api/format";
import { t } from "../../i18n";
import { PageHeading } from "../../shell/PageHeading";
import { useMe } from "../../shell/session";
import { Button, LinkButton } from "../../ui/Button";
import { Segmented } from "../../ui/Segmented";
import { Select } from "../../ui/Select";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import {
  type ExploreState,
  MAX_COMPARED,
  METRIC_LABELS,
  METRICS,
  readExplore,
  SORT_LABELS,
  SORTS,
  sortPlaces,
  toggleCompared,
  VIEWS,
  writeExplore,
} from "./explore";
import { failureOf } from "./failure";
import { placeAddress } from "./filters";
import { MarketMap } from "./MarketMap";
import { MarketPage } from "./MarketPage";
import {
  type LocationContext,
  type MetricView,
  type Overview,
  type OverviewPlace,
  useOverview,
} from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import { StatusBadge } from "./StatusBadge";
import styles from "./explore.module.css";

// LEGAL[republication]: aggregates of Otodom asking rents and GUS statistics per place, never a listing (RM-282)

function FreeBanner({ overview }: { readonly overview: Overview }) {
  if (overview.access !== "free") return null;
  return (
    <InlineNotice
      tone="info"
      title={t.market.explore.freeBannerTitle({
        visible: formatCount(overview.visible_places),
        total: formatCount(overview.total_places),
      })}
      actions={
        <LinkButton to="/app/credits" small>
          {t.market.explore.freeBannerAction}
        </LinkButton>
      }
    >
      {overview.free_rule_pl} {t.market.explore.freeBannerBody}
    </InlineNotice>
  );
}

function PlaceTable({
  places,
  state,
  go,
}: {
  readonly places: readonly OverviewPlace[];
  readonly state: ExploreState;
  readonly go: (patch: Partial<ExploreState>) => void;
}) {
  return (
    <ScrollRegion label={t.market.list.resultsLabel}>
      <table className={styles["table"]}>
        <caption>{t.market.explore.tableCaption}</caption>
        <thead>
          <tr>
            <th scope="col">{t.market.list.columns.place}</th>
            <th scope="col">{t.market.list.columns.status}</th>
            <th scope="col" className={styles["num"]}>
              {t.market.list.columns.medianRent}
            </th>
            <th scope="col" className={styles["num"]}>
              {t.market.list.columns.medianPpm2}
            </th>
            <th scope="col" className={styles["num"]}>
              {t.market.list.columns.sample}
            </th>
            <th scope="col">{t.market.explore.compareTitle}</th>
          </tr>
        </thead>
        <tbody>
          {places.map((p) => {
            const chosen = state.ids.includes(p.location_id);
            return (
              <tr key={p.location_id} aria-selected={p.location_id === state.sel}>
                <th scope="row">
                  <button
                    type="button"
                    className={styles["pick"]}
                    aria-pressed={p.location_id === state.sel}
                    aria-label={t.market.explore.pick({ name: p.name })}
                    onClick={() => go({ sel: p.location_id })}
                  >
                    {p.name}
                  </button>
                </th>
                <td>
                  <StatusBadge status={p.data_status} />
                </td>
                <td className={styles["num"]}>
                  {p.withheld_reason === null
                    ? formatMoney(p.median_rent_pln, { decimals: 0 })
                    : t.market.withheld.insufficient_sample}
                </td>
                <td className={styles["num"]}>{formatPricePerArea(p.median_ppm2)}</td>
                <td className={styles["num"]}>
                  {p.priced_count === null ? NOT_COMPUTED : formatCount(p.priced_count)}
                </td>
                <td>
                  <Button
                    type="button"
                    small
                    aria-pressed={chosen}
                    aria-label={(chosen ? t.market.explore.compareRemove : t.market.explore.compareAdd)({
                      name: p.name,
                    })}
                    disabled={!chosen && state.ids.length >= MAX_COMPARED}
                    onClick={() => go({ ids: toggleCompared(state.ids, p.location_id) })}
                  >
                    {chosen ? "−" : "+"}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

function SelectedPanel({ place }: { readonly place: OverviewPlace | undefined }) {
  return (
    <section className={styles["panel"]} aria-label={t.market.explore.selected}>
      <h2>{t.market.explore.selected}</h2>
      {place === undefined ? (
        <p>{t.market.explore.none}</p>
      ) : (
        <>
          <p className={styles["strong"]}>{place.name}</p>
          <p>
            {formatPricePerArea(place.median_ppm2)} · {formatMoney(place.median_rent_pln, { decimals: 0 })}
          </p>
          <LinkButton to={placeAddress(place.location_id, "")} icon="arrow" small>
            {t.market.explore.open}
          </LinkButton>
        </>
      )}
    </section>
  );
}

const cell = (m: MetricView | undefined): string =>
  m === undefined || m.state === "unavailable" || m.year === null || m.measured === null
    ? NOT_COMPUTED
    : `${m.value === null ? NOT_COMPUTED : `${formatDecimal(m.value, 2)} ${m.unit === "-" ? "" : m.unit}`.trim()} · ${m.measured.name}, ${m.year}`;

function Compare({
  places,
  ids,
}: {
  readonly places: readonly OverviewPlace[];
  readonly ids: readonly string[];
}) {
  const me = useMe();
  const contexts = useQueries({
    queries: ids.map((id) => ({
      queryKey: tenantKey(me.id, "market", "context", id),
      queryFn: async ({ signal }: { signal: AbortSignal }): Promise<LocationContext> =>
        unwrap(
          await api.GET("/api/market/locations/{location_id}/context", {
            params: { path: { location_id: id } },
            signal,
          }),
        ),
      staleTime: 5 * 60_000,
    })),
  });
  if (ids.length < 2) return <p>{t.market.explore.compareHint}</p>;
  const chosen = ids.map((id) => places.find((p) => p.location_id === id));
  const keys = contexts.find((c) => c.data !== undefined)?.data?.metrics ?? [];
  return (
    <section aria-label={t.market.explore.compareTitle}>
      <p className={styles["muted"]}>{t.market.explore.compareNotComparable}</p>
      <ScrollRegion label={t.market.explore.compareTitle}>
        <table className={styles["table"]}>
          <caption>{t.market.explore.compareTitle}</caption>
          <thead>
            <tr>
              <th scope="col">{t.market.explore.compareMetric}</th>
              {ids.map((id, i) => (
                <th scope="col" key={id}>
                  <Link to={placeAddress(id, "")}>{chosen[i]?.name ?? id}</Link>
                  {contexts[i]?.isError ? <div>{t.market.explore.compareFailed}</div> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="rowgroup" colSpan={ids.length + 1}>
                {t.market.explore.compareRent}
              </th>
            </tr>
            <tr>
              <th scope="row">{t.market.list.columns.medianPpm2}</th>
              {chosen.map((p, i) => (
                <td key={ids[i]}>{p === undefined ? NOT_COMPUTED : formatPricePerArea(p.median_ppm2)}</td>
              ))}
            </tr>
            <tr>
              <th scope="row">{t.market.list.columns.medianRent}</th>
              {chosen.map((p, i) => (
                <td key={ids[i]}>
                  {p === undefined ? NOT_COMPUTED : formatMoney(p.median_rent_pln, { decimals: 0 })}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row">{t.market.list.columns.sample}</th>
              {chosen.map((p, i) => (
                <td key={ids[i]}>{p?.priced_count == null ? NOT_COMPUTED : formatCount(p.priced_count)}</td>
              ))}
            </tr>
            <tr>
              <th scope="rowgroup" colSpan={ids.length + 1}>
                {t.market.explore.compareContext}
              </th>
            </tr>
            {keys.map((m) => (
              <tr key={m.key}>
                <th scope="row">{m.name_pl}</th>
                {contexts.map((c, i) => (
                  <td key={ids[i]}>
                    {c.data === undefined ? NOT_COMPUTED : cell(c.data.metrics.find((x) => x.key === m.key))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}

export function MarketExplorer() {
  const [params, setParams] = useSearchParams();
  const state = readExplore(params);
  const q = params.get("q");
  const overview = useOverview();
  const go = (patch: Partial<ExploreState>) => {
    const next = writeExplore({ ...state, ...patch });
    if (q !== null && (patch.view ?? state.view) === "list") next.set("q", q);
    setParams(next);
  };
  const places = sortPlaces(overview.data?.items ?? [], state.sort);

  return (
    <div className={styles["page"]}>
      <PageHeading title={t.market.title} eyebrow={t.market.eyebrow} lead={t.market.lead} />
      {overview.data === undefined ? null : <FreeBanner overview={overview.data} />}
      <Segmented
        label={t.market.explore.viewsLabel}
        value={state.view}
        options={VIEWS.map((value) => ({ value, label: t.market.explore.views[value] }))}
        onValueChange={(view) => go({ view: VIEWS.find((v) => v === view) ?? "map" })}
      />
      {state.view === "list" ? (
        <MarketPage embedded />
      ) : overview.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.market.explore.loading}>
          <Skeleton height="320px" />
        </div>
      ) : overview.isError ? (
        <InlineNotice
          tone="danger"
          title={t.market.explore.failed}
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={overview.isFetching}
              onClick={() => void overview.refetch()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {failureOf(overview.error).detail}
        </InlineNotice>
      ) : state.view === "compare" ? (
        <>
          <Compare places={places} ids={state.ids} />
          <PlaceTable places={places} state={state} go={go} />
        </>
      ) : (
        <>
          <div className={styles["controls"]}>
            <Select
              label={t.market.explore.metricLabel}
              value={state.metric}
              options={METRICS.map((value) => ({ value, label: METRIC_LABELS[value] }))}
              onValueChange={(metric) => go({ metric: METRICS.find((m) => m === metric) ?? "ppm2" })}
            />
            <Select
              label={t.market.explore.sortLabel}
              value={state.sort}
              options={SORTS.map((value) => ({ value, label: SORT_LABELS[value] }))}
              onValueChange={(sort) => go({ sort: SORTS.find((s) => s === sort) ?? "name" })}
            />
            <span className={styles["muted"]} role="status">
              {t.market.explore.shown({ count: formatCounted(places.length, t.format.nouns.places) })}
            </span>
          </div>
          <div className={styles["split"]}>
            <MarketMap
              places={places}
              metric={state.metric}
              selected={state.sel}
              onSelect={(id) => go({ sel: id })}
            />
            <SelectedPanel place={places.find((p) => p.location_id === state.sel)} />
          </div>
          <PlaceTable places={places} state={state} go={go} />
        </>
      )}
    </div>
  );
}
