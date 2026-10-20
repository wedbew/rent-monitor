import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { formatCount, formatDateTime } from "../../api/format";
import { t } from "../../i18n";
import { hasNoLimit } from "../../shell/balance";
import { useMe } from "../../shell/session";
import { Button, LinkButton } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { Segmented } from "../../ui/Segmented";
import { Select } from "../../ui/Select";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { placeAddress } from "./addresses";
import { CohortFilters } from "./CohortFilters";
import { cohortLabel } from "./cohorts";
import { ComparePanel } from "./ComparePanel";
import {
  type ExploreState,
  MAX_COMPARED,
  matchesName,
  METRIC_LABELS,
  METRICS,
  readExplore,
  SORT_LABELS,
  SORTS,
  sortPlaces,
  toggleCompared,
  writeExplore,
} from "./explore";
import { failureOf } from "./failure";
import { MarketMap } from "./MarketMap";
import { PlaceTable } from "./PlaceTable";
import { type Overview, useOverview } from "./queries";
import styles from "./explore.module.css";

// LEGAL[republication]: aggregates of Otodom asking rents per place, never a listing (RM-282, RM-439)

const PAGE = 25;

function AccessNotice({ overview, unlimited }: { readonly overview: Overview; readonly unlimited: boolean }) {
  if (overview.access === "free")
    return (
      <InlineNotice
        tone="info"
        title={t.rynek.access.freeTitle({
          visible: formatCount(overview.visible_places),
          total: formatCount(overview.total_places),
        })}
        actions={
          <LinkButton to="/app/credits" small>
            {t.rynek.access.buy}
          </LinkButton>
        }
      >
        {overview.free_rule_pl} {t.rynek.access.freeBody}
      </InlineNotice>
    );
  return unlimited ? (
    <InlineNotice tone="success" title={t.rynek.access.unlimitedTitle}>
      {t.rynek.access.unlimitedBody}
    </InlineNotice>
  ) : null;
}

/**
 * The Otodom tab: the rental-market explorer. The group of flats (filter), the view, the selected place and the
 * places in the comparison are all in the address, so reload, Back and Forward restore them. Changing the group
 * changes the request (`cohort`), and with it the map, the table and the previews; the previous answer stays up,
 * marked busy, until the new one arrives. The map and the table share one selection.
 */
export function OtodomExplorer() {
  const [params, setParams] = useSearchParams();
  const state = readExplore(params);
  const me = useMe();
  const overview = useOverview(state.cohort);
  const [message, setMessage] = useState<string | null>(null);
  const [grown, setGrown] = useState<{ readonly key: string; readonly limit: number } | null>(null);
  const q = params.get("q") ?? "";

  const go = (patch: Partial<ExploreState>, replace = false) => {
    setParams(writeExplore({ ...state, ...patch }, params), { replace });
  };

  const all = useMemo(() => sortPlaces(overview.data?.items ?? [], state.sort), [overview.data, state.sort]);
  const found = useMemo(() => all.filter((p) => matchesName(p.name, q)), [all, q]);
  // A new group of flats, search or order starts the table from its top again: the growth belongs to its key.
  const tableKey = `${state.cohort}|${q}|${state.sort}`;
  const limit = grown?.key === tableKey ? grown.limit : PAGE;
  const selectedIndex = state.sel === null ? -1 : found.findIndex((p) => p.location_id === state.sel);
  const visibleCount = Math.max(limit, selectedIndex + 1);
  const rows = found.slice(0, visibleCount);

  const toggleCompare = (id: string) => {
    const name = all.find((p) => p.location_id === id)?.name ?? id;
    const has = state.ids.includes(id);
    if (!has && state.ids.length >= MAX_COMPARED) {
      setMessage(t.rynek.compare.limit({ max: formatCount(MAX_COMPARED) }));
      return;
    }
    const next = toggleCompared(state.ids, id);
    setMessage(
      (has ? t.rynek.compare.removed : t.rynek.compare.added)({
        name,
        count: formatCount(next.length),
        max: formatCount(MAX_COMPARED),
      }),
    );
    go({ ids: next }, true);
  };
  const clearCompare = () => {
    setMessage(null);
    go({ ids: [] }, true);
  };

  const refreshed = useMemo(() => {
    const times = (overview.data?.items ?? []).flatMap((p) =>
      p.last_successful_refresh_at === null ? [] : [p.last_successful_refresh_at],
    );
    return times.length === 0 ? null : times.reduce((a, b) => (a > b ? a : b));
  }, [overview.data]);

  const href = (id: string) => placeAddress(id, state.cohort);
  const group = cohortLabel(state.cohort);
  const busy = overview.isFetching && overview.isPlaceholderData;

  const header = (
    <>
      {overview.data === undefined ? null : (
        <AccessNotice overview={overview.data} unlimited={hasNoLimit(me)} />
      )}
      <p className={styles["muted"]}>
        {refreshed === null
          ? t.rynek.sources.noRefresh
          : t.rynek.sources.freshness({ when: formatDateTime(refreshed) })}
      </p>
      <CohortFilters value={state.cohort} busy={busy} onChange={(cohort) => go({ cohort, sel: null })} />
    </>
  );

  if (overview.isPending)
    return (
      <div className={styles["page"]}>
        {header}
        <div role="status" aria-busy="true" aria-label={t.rynek.explore.loading}>
          <Skeleton height="420px" />
        </div>
      </div>
    );
  if (overview.isError && overview.data === undefined)
    return (
      <div className={styles["page"]}>
        {header}
        <InlineNotice
          tone="danger"
          title={t.rynek.explore.overviewFailed}
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
      </div>
    );

  const noGroupData =
    all.length > 0 && all.every((p) => p.data_status === "unavailable" || p.priced_count === null);

  return (
    <div className={styles["page"]}>
      {header}
      <div className={styles["toolbar"]}>
        <Segmented
          label={t.rynek.explore.viewsLabel}
          value={state.view === "compare" ? "map" : state.view}
          options={[
            { value: "map", label: t.rynek.explore.views.map },
            { value: "list", label: t.rynek.explore.views.list },
          ]}
          onValueChange={(view) => go({ view: view === "list" ? "list" : "map" })}
        />
        {state.view === "compare" ? null : (
          <Select
            label={t.rynek.explore.metricLabel}
            value={state.metric}
            options={METRICS.map((value) => ({ value, label: METRIC_LABELS[value] }))}
            onValueChange={(metric) => go({ metric: METRICS.find((m) => m === metric) ?? "ppm2" })}
          />
        )}
        <Select
          label={t.rynek.explore.sortLabel}
          value={state.sort}
          options={SORTS.map((value) => ({ value, label: SORT_LABELS[value] }))}
          onValueChange={(sort) => go({ sort: SORTS.find((s) => s === sort) ?? "name" })}
        />
        <div className={styles["toolbarEnd"]}>
          <Button
            type="button"
            variant="primary"
            icon="arrow"
            aria-pressed={state.view === "compare"}
            onClick={() => go({ view: "compare" })}
            data-testid="compare-cta"
          >
            {state.ids.length === 0
              ? t.rynek.compare.cta
              : t.rynek.compare.ctaCount({ count: formatCount(state.ids.length) })}
          </Button>
        </div>
      </div>
      <p className={styles["liveMessage"]} role="status">
        {state.view === "compare" ? null : message}
      </p>

      {state.view === "compare" ? (
        <>
          <div>
            <Button type="button" small onClick={() => go({ view: "map" })}>
              {t.rynek.compare.back}
            </Button>
          </div>
          <ComparePanel
            places={all}
            ids={state.ids}
            cohort={state.cohort}
            onToggle={toggleCompare}
            onClear={clearCompare}
            message={message}
          />
        </>
      ) : (
        <>
          <p className={styles["muted"]}>{t.rynek.filters.appliesTo({ filter: group })}</p>
          {noGroupData ? (
            <InlineNotice tone="warning" title={t.rynek.filters.noPlacesInGroup} live="status" />
          ) : null}
          <div className={busy ? styles["busy"] : undefined} aria-busy={busy}>
            {state.view === "map" ? (
              <MarketMap
                places={all}
                metric={state.metric}
                selected={state.sel}
                compared={state.ids}
                compareFull={state.ids.length >= MAX_COMPARED}
                groupLabel={group}
                placeHref={href}
                onSelect={(id) => go({ sel: id })}
                onToggleCompare={toggleCompare}
              />
            ) : null}
          </div>
          <div className={styles["toolbar"]}>
            <div className={styles["search"]}>
              <TextField
                label={t.rynek.explore.searchLabel}
                hint={t.rynek.explore.searchHint}
                value={q}
                onValueChange={(value) => {
                  const next = new URLSearchParams(params);
                  if (value === "") next.delete("q");
                  else next.set("q", value.slice(0, 60));
                  setParams(next, { replace: true });
                }}
                autoComplete="off"
                spellCheck={false}
                maxLength={60}
              />
            </div>
            <p className={styles["muted"]} role="status">
              {t.rynek.explore.shown({
                shown: formatCount(Math.min(rows.length, found.length)),
                total: formatCount(found.length),
              })}
            </p>
          </div>
          {found.length === 0 ? (
            <p className={styles["muted"]}>{t.rynek.explore.noSearchMatch}</p>
          ) : (
            <>
              <PlaceTable
                places={rows}
                selected={state.sel}
                compared={state.ids}
                href={href}
                onSelect={(id) => go({ sel: state.sel === id ? null : id })}
                onToggleCompare={toggleCompare}
              />
              {rows.length < found.length ? (
                <div className={styles["more"]}>
                  <Button type="button" onClick={() => setGrown({ key: tableKey, limit: limit + PAGE })}>
                    {t.rynek.explore.showMore}
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}
