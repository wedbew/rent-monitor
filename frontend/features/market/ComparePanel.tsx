import { useQueries } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, unwrap } from "../../api/client";
import { tenantKey } from "../../api/query";
import {
  formatCount,
  formatDate,
  formatDecimal,
  formatMoney,
  formatPricePerArea,
  NOT_COMPUTED,
} from "../../api/format";
import { BarCompare, type BarItem } from "../../charts/BarCompare";
import { ChartFigure } from "../../charts/ChartFigure";
import { DataTable } from "../../charts/DataTable";
import { plotValue } from "../../charts/meta";
import { t } from "../../i18n";
import { useMe } from "../../shell/session";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { InlineNotice } from "../../ui/Status";
import { placeAddress } from "./addresses";
import { cohortLabel } from "./cohorts";
import { MAX_COMPARED, matchesName } from "./explore";
import type { CohortKey } from "./filters";
import type { LocationContext, LocationDetail, MetricView, OverviewPlace } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import styles from "./explore.module.css";

interface Props {
  readonly places: readonly OverviewPlace[];
  readonly ids: readonly string[];
  readonly cohort: CohortKey;
  readonly onToggle: (id: string) => void;
  readonly onClear: () => void;
  readonly message: string | null;
}

const gusCell = (m: MetricView | undefined): string =>
  m === undefined || m.state === "unavailable" || m.year === null || m.measured === null || m.value === null
    ? t.rynek.compare.gusUnavailable
    : t.rynek.compare.gusCell({
        value: formatDecimal(m.value, 2),
        unit: m.unit === "-" ? m.measured.name : `${m.unit}; ${m.measured.name}`,
        year: String(m.year),
      });

/**
 * The comparison: two to four places side by side, with the Otodom asking-rent figures for the chosen group of flats
 * (medians, the middle half of offers, sample, freshness) and, apart from them, the GUS context of each place with its
 * unit, level and year. With fewer than two places it explains what to do and offers a picker, so "Porównaj miejsca"
 * always leads somewhere that can be completed. Adding and removing is announced, and so is the limit.
 */
export function ComparePanel({ places, ids, cohort, onToggle, onClear, message }: Props) {
  const me = useMe();
  const [search, setSearch] = useState("");
  const chosen = ids.flatMap((id) => {
    const p = places.find((x) => x.location_id === id);
    return p === undefined ? [] : [p];
  });
  const details = useQueries({
    queries: ids.map((id) => ({
      queryKey: tenantKey(me.id, "market", "place", id),
      queryFn: async ({ signal }: { signal: AbortSignal }): Promise<LocationDetail> =>
        unwrap(
          await api.GET("/api/market/locations/{location_id}", {
            params: { path: { location_id: id } },
            signal,
          }),
        ),
      staleTime: 30_000,
      enabled: ids.length >= 2,
    })),
  });
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
      enabled: ids.length >= 2,
    })),
  });

  const group = cohortLabel(cohort);
  const candidates = places
    .filter((p) => !ids.includes(p.location_id) && matchesName(p.name, search))
    .slice(0, 8);
  const full = ids.length >= MAX_COMPARED;
  const quartiles = (i: number): { low: string | null; high: string | null } => {
    const row = details[i]?.data?.cohort.find((c) => c.cohort_key === cohort);
    return { low: row?.p25_ppm2 ?? null, high: row?.p75_ppm2 ?? null };
  };

  const bars: BarItem[] = chosen.map((p) => {
    const q = quartiles(ids.indexOf(p.location_id));
    const sufficient = p.sufficient === true && p.median_ppm2 !== null;
    return {
      id: p.location_id,
      name: p.name,
      value: sufficient ? plotValue(p.median_ppm2) : null,
      valueText: formatPricePerArea(p.median_ppm2),
      meta: t.rynek.stats.sampleLabel({ count: formatCount(p.priced_count ?? 0) }),
      low: plotValue(q.low),
      high: plotValue(q.high),
      withheldText:
        p.priced_count === null
          ? t.rynek.explore.unavailable
          : t.rynek.explore.withheld({ count: formatCount(p.priced_count) }),
      nameNode: <Link to={placeAddress(p.location_id, cohort)}>{p.name}</Link>,
    };
  });

  const metricKeys = (() => {
    const seen = new Map<string, MetricView>();
    for (const c of contexts)
      for (const m of c.data?.metrics ?? [])
        if (m.state !== "unavailable" && !seen.has(m.key)) seen.set(m.key, m);
    return [...seen.values()];
  })();

  return (
    <section className={styles["compare"]} aria-labelledby="compare-heading">
      <div className={styles["compareHead"]}>
        <h2 id="compare-heading">{t.rynek.compare.heading}</h2>
        <p className={styles["muted"]}>{t.rynek.compare.lead}</p>
      </div>
      <p className={styles["liveMessage"]} role="status" data-testid="compare-message">
        {message}
      </p>

      <div className={styles["chosen"]}>
        <h3>{t.rynek.compare.chosen}</h3>
        {chosen.length === 0 ? null : (
          <ul className={styles["chips"]}>
            {chosen.map((p) => (
              <li key={p.location_id}>
                <Button
                  type="button"
                  small
                  aria-label={t.rynek.compare.remove({ name: p.name })}
                  onClick={() => onToggle(p.location_id)}
                >
                  {p.name} ×
                </Button>
              </li>
            ))}
          </ul>
        )}
        {ids.length === 0 ? null : (
          <Button type="button" small onClick={onClear}>
            {t.rynek.compare.clear}
          </Button>
        )}
      </div>

      <div className={styles["picker"]}>
        <h3>{t.rynek.compare.picker}</h3>
        <TextField
          label={t.rynek.compare.pickerSearch}
          value={search}
          onValueChange={setSearch}
          autoComplete="off"
          spellCheck={false}
        />
        {full ? (
          <InlineNotice
            tone="info"
            title={t.rynek.compare.limit({ max: formatCount(MAX_COMPARED) })}
            live="status"
          />
        ) : null}
        {candidates.length === 0 ? (
          <p className={styles["muted"]}>{t.rynek.compare.pickerEmpty}</p>
        ) : (
          <ul className={styles["chips"]}>
            {candidates.map((p) => (
              <li key={p.location_id}>
                <Button
                  type="button"
                  small
                  disabled={full}
                  aria-label={t.rynek.compare.add({ name: p.name })}
                  onClick={() => onToggle(p.location_id)}
                >
                  {p.name} +
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {ids.length < 2 ? (
        <InlineNotice tone="info" title={t.rynek.compare.needTitle}>
          {t.rynek.compare.needBody}
        </InlineNotice>
      ) : (
        <>
          <ChartFigure
            compact
            title={t.rynek.compare.chartTitle}
            meta={{
              measure: t.rynek.compare.ppm2,
              unit: t.rynek.compare.ppm2Unit,
              area: chosen.map((p) => p.name).join(", "),
              period: t.rynek.sources.otodomFacts.period,
              source: t.rynek.sources.otodomFacts.source,
              sample: t.rynek.stats.sampleLabel({
                count: formatCount(chosen.reduce((s, p) => s + (p.priced_count ?? 0), 0)),
              }),
              interpretation: `${t.rynek.stats.median} ${t.rynek.stats.askingNote} ${t.rynek.filters.appliesTo({ filter: group })}`,
            }}
            table={
              <DataTable
                caption={t.rynek.compare.chartTitle}
                columns={[
                  { key: "place", header: t.rynek.explore.columns.place },
                  { key: "ppm2", header: t.rynek.compare.ppm2, numeric: true },
                  { key: "range", header: t.rynek.compare.quartiles, numeric: true },
                  { key: "sample", header: t.rynek.compare.sample, numeric: true },
                ]}
                rows={chosen.map((p) => {
                  const q = quartiles(ids.indexOf(p.location_id));
                  return {
                    id: p.location_id,
                    cells: {
                      place: p.name,
                      ppm2:
                        p.sufficient === true ? formatPricePerArea(p.median_ppm2) : t.rynek.stats.withheldBar,
                      range:
                        q.low === null || q.high === null
                          ? NOT_COMPUTED
                          : `${formatPricePerArea(q.low)} – ${formatPricePerArea(q.high)}`,
                      sample: p.priced_count === null ? NOT_COMPUTED : formatCount(p.priced_count),
                    },
                  };
                })}
              />
            }
          >
            <BarCompare items={bars} label={t.rynek.compare.chartTitle} />
          </ChartFigure>

          <ScrollRegion label={t.rynek.compare.heading}>
            <table className={styles["table"]}>
              <caption>{t.rynek.compare.heading}</caption>
              <thead>
                <tr>
                  <th scope="col">{t.rynek.compare.metric}</th>
                  {chosen.map((p) => (
                    <th scope="col" key={p.location_id}>
                      <Link to={placeAddress(p.location_id, cohort)}>{p.name}</Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="rowgroup" colSpan={chosen.length + 1}>
                    {t.rynek.compare.otodomGroup}. {t.rynek.filters.appliesTo({ filter: group })}
                  </th>
                </tr>
                <tr>
                  <th scope="row">{t.rynek.compare.ppm2}</th>
                  {chosen.map((p) => (
                    <td key={p.location_id}>
                      {p.sufficient === true ? formatPricePerArea(p.median_ppm2) : t.rynek.stats.withheldBar}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">{t.rynek.compare.rent}</th>
                  {chosen.map((p) => (
                    <td key={p.location_id}>
                      {p.sufficient === true
                        ? formatMoney(p.median_rent_pln, { decimals: 0 })
                        : t.rynek.stats.withheldBar}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">{t.rynek.compare.quartiles}</th>
                  {chosen.map((p, i) => {
                    const q = quartiles(i);
                    return (
                      <td key={p.location_id}>
                        {q.low === null || q.high === null
                          ? NOT_COMPUTED
                          : `${formatPricePerArea(q.low)} – ${formatPricePerArea(q.high)}`}
                      </td>
                    );
                  })}
                </tr>
                <tr>
                  <th scope="row">{t.rynek.compare.sample}</th>
                  {chosen.map((p) => (
                    <td key={p.location_id}>
                      {p.priced_count === null ? NOT_COMPUTED : formatCount(p.priced_count)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">{t.rynek.compare.refreshed}</th>
                  {chosen.map((p) => (
                    <td key={p.location_id}>
                      {p.latest_summary_date === null ? NOT_COMPUTED : formatDate(p.latest_summary_date)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="rowgroup" colSpan={chosen.length + 1}>
                    {t.rynek.compare.gusGroup}
                  </th>
                </tr>
                {metricKeys.map((m) => (
                  <tr key={m.key}>
                    <th scope="row">{m.name_pl}</th>
                    {chosen.map((p) => {
                      const i = ids.indexOf(p.location_id);
                      const ctx = contexts[i];
                      return (
                        <td key={p.location_id}>
                          {ctx?.isError === true
                            ? t.rynek.compare.gusFailed
                            : ctx?.data === undefined
                              ? NOT_COMPUTED
                              : gusCell(ctx.data.metrics.find((x) => x.key === m.key))}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <p className={styles["muted"]}>{t.rynek.compare.notComparable}</p>
        </>
      )}
    </section>
  );
}
