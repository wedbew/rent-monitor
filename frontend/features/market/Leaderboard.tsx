import { useState } from "react";

import { formatCount, formatDecimal, NOT_COMPUTED } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { MAX_COMPARED } from "./explore";
import type { RankingOverview } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import styles from "./gus.module.css";

const PAGE = 25;

interface Props {
  readonly overview: RankingOverview;
  readonly selected: string | null;
  readonly compared: readonly string[];
  readonly onSelect: (id: string) => void;
  readonly onToggleCompare: (id: string) => void;
}

/**
 * The places of the account by the index of their gmina, best first. The denominator of every position is the whole
 * national cohort (all gminas with a complete index), not the length of this list, and the caption says so. A place
 * without a score is listed with its state, never hidden and never given a zero.
 */
export function Leaderboard({ overview, selected, compared, onSelect, onToggleCompare }: Props) {
  const [limit, setLimit] = useState(PAGE);
  const index = selected === null ? -1 : overview.items.findIndex((p) => p.location_id === selected);
  const rows = overview.items.slice(0, Math.max(limit, index + 1));
  return (
    <section aria-labelledby="gus-leaderboard" className={styles["section"]}>
      <h2 id="gus-leaderboard">{t.rynek.gus.leaderboard.heading}</h2>
      <p className={styles["muted"]}>{t.rynek.gus.leaderboard.lead}</p>
      <ScrollRegion label={t.rynek.gus.leaderboard.heading}>
        <table className={styles["table"]}>
          <caption>
            {t.rynek.gus.leaderboard.caption({
              cohort: overview.cohort_name_pl,
              count: formatCount(overview.scored_gminas),
            })}
          </caption>
          <thead>
            <tr>
              <th scope="col">{t.rynek.gus.leaderboard.columns.place}</th>
              <th scope="col">{t.rynek.gus.leaderboard.columns.gmina}</th>
              <th scope="col" className={styles["num"]}>
                {t.rynek.gus.leaderboard.columns.score}
              </th>
              <th scope="col" className={styles["num"]}>
                {t.rynek.gus.leaderboard.columns.rank}
              </th>
              <th scope="col">{t.rynek.gus.leaderboard.columns.compare}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const chosen = compared.includes(p.location_id);
              const isSelected = p.location_id === selected;
              return (
                <tr key={p.location_id} aria-selected={isSelected} data-selected={isSelected || undefined}>
                  <th scope="row">
                    <button
                      type="button"
                      className={styles["pick"]}
                      aria-pressed={isSelected}
                      aria-label={t.rynek.gus.leaderboard.open({ name: p.name })}
                      onClick={() => onSelect(p.location_id)}
                    >
                      {p.name}
                    </button>
                  </th>
                  <td>{p.gmina_name ?? NOT_COMPUTED}</td>
                  <td className={styles["num"]}>
                    {p.score === null ? t.rynek.gus.leaderboard.noScore : formatDecimal(p.score, 1)}
                  </td>
                  <td className={styles["num"]}>
                    {p.rank === null || p.of === null
                      ? NOT_COMPUTED
                      : t.rynek.gus.components.rankOf({ rank: formatCount(p.rank), of: formatCount(p.of) })}
                  </td>
                  <td>
                    <Button
                      type="button"
                      small
                      aria-pressed={chosen}
                      aria-label={(chosen
                        ? t.rynek.gus.leaderboard.compareRemove
                        : t.rynek.gus.leaderboard.compareAdd)({ name: p.name })}
                      disabled={(!chosen && compared.length >= MAX_COMPARED) || p.score === null}
                      onClick={() => onToggleCompare(p.location_id)}
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
      {rows.length < overview.items.length ? (
        <div>
          <Button type="button" onClick={() => setLimit((n) => n + PAGE)}>
            {t.rynek.gus.leaderboard.showMore}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
