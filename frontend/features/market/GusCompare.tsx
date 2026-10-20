import { useQueries } from "@tanstack/react-query";

import { api, unwrap } from "../../api/client";
import { tenantKey } from "../../api/query";
import { formatCount, formatDecimal, NOT_COMPUTED } from "../../api/format";
import { t } from "../../i18n";
import { useMe } from "../../shell/session";
import type { LocationIndex } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import styles from "./gus.module.css";

interface Props {
  readonly ids: readonly string[];
  readonly names: ReadonlyMap<string, string>;
}

/**
 * The index of two to four places side by side: the score and the national position (with its denominator), then each
 * indicator's value, year, national position and contribution. Each column is the gmina of that place, and the unit and year of
 * every value are written in its cell, so values of different gminas and years are never set beside each other bare.
 */
export function GusCompare({ ids, names }: Props) {
  const me = useMe();
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: tenantKey(me.id, "market", "ranking", id),
      queryFn: async ({ signal }: { signal: AbortSignal }): Promise<LocationIndex> =>
        unwrap(
          await api.GET("/api/market/locations/{location_id}/ranking", {
            params: { path: { location_id: id } },
            signal,
          }),
        ),
      staleTime: 5 * 60_000,
      enabled: ids.length >= 2,
    })),
  });
  if (ids.length < 2) return <p className={styles["muted"]}>{t.rynek.gus.compare.need}</p>;
  const first = results.find((r) => r.data !== undefined)?.data?.index.components ?? [];
  return (
    <section aria-labelledby="gus-compare" className={styles["section"]}>
      <h2 id="gus-compare">{t.rynek.gus.compare.heading}</h2>
      <p className={styles["muted"]}>{t.rynek.gus.compare.lead}</p>
      <ScrollRegion label={t.rynek.gus.compare.heading}>
        <table className={styles["table"]}>
          <caption>{t.rynek.gus.compare.heading}</caption>
          <thead>
            <tr>
              <th scope="col">{t.rynek.compare.metric}</th>
              {ids.map((id) => (
                <th scope="col" key={id}>
                  {names.get(id) ?? id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">{t.rynek.gus.compare.scoreRow}</th>
              {results.map((r, i) => (
                <td key={ids[i]}>
                  {r.isError
                    ? t.rynek.gus.compare.failed
                    : r.data?.index.score == null
                      ? NOT_COMPUTED
                      : `${formatDecimal(r.data.index.score, 1)} ${t.rynek.gus.scoreOf}`}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row">{t.rynek.gus.compare.rankRow}</th>
              {results.map((r, i) => {
                const p = r.data?.index.positions.find((x) => x.scope === "national");
                return (
                  <td key={ids[i]}>
                    {p === undefined || p.rank === null || p.of === null
                      ? NOT_COMPUTED
                      : t.rynek.gus.components.rankOf({ rank: formatCount(p.rank), of: formatCount(p.of) })}
                  </td>
                );
              })}
            </tr>
            {first.map((component) => (
              <tr key={component.key}>
                <th scope="row">
                  {component.name_pl}
                  <span className={styles["componentNote"]}>{component.favourable_pl}</span>
                </th>
                {results.map((r, i) => {
                  const c = r.data?.index.components.find((x) => x.key === component.key);
                  return (
                    <td key={ids[i]}>
                      {c === undefined || c.value === null ? (
                        NOT_COMPUTED
                      ) : (
                        <>
                          {`${formatDecimal(c.value, 2)} ${c.unit_pl}`}
                          <span className={styles["componentNote"]}>
                            {t.rynek.gus.components.yearLabel({ year: String(c.year ?? "") })}
                            {c.national_rank === null || c.national_of === null
                              ? ""
                              : `; ${t.rynek.gus.components.rankOf({ rank: formatCount(c.national_rank), of: formatCount(c.national_of) })}`}
                          </span>
                        </>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </ScrollRegion>
    </section>
  );
}
