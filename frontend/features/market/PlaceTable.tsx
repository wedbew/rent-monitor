import { Link } from "react-router";

import { formatCount, formatMoney, formatPricePerArea, NOT_COMPUTED } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { MAX_COMPARED } from "./explore";
import type { OverviewPlace } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import { StatusBadge } from "./StatusBadge";
import styles from "./explore.module.css";

interface Props {
  readonly places: readonly OverviewPlace[];
  readonly selected: string | null;
  readonly compared: readonly string[];
  readonly href: (id: string) => string;
  readonly onSelect: (id: string) => void;
  readonly onToggleCompare: (id: string) => void;
}

/**
 * The places as a table, in step with the map: selecting a row selects its marker and opens its preview, and the
 * selected row is marked both to the eye (a heavier row) and to assistive technology (`aria-selected`). A value the
 * source withheld says why in the cell; it is never a zero.
 */
export function PlaceTable({ places, selected, compared, href, onSelect, onToggleCompare }: Props) {
  return (
    <ScrollRegion label={t.rynek.explore.tableCaption}>
      <table className={styles["table"]}>
        <caption>{t.rynek.explore.tableCaption}</caption>
        <thead>
          <tr>
            <th scope="col">{t.rynek.explore.columns.place}</th>
            <th scope="col">{t.rynek.explore.columns.status}</th>
            <th scope="col" className={styles["num"]}>
              {t.rynek.explore.columns.ppm2}
            </th>
            <th scope="col" className={styles["num"]}>
              {t.rynek.explore.columns.rent}
            </th>
            <th scope="col" className={styles["num"]}>
              {t.rynek.explore.columns.sample}
            </th>
            <th scope="col">{t.rynek.explore.columns.compare}</th>
          </tr>
        </thead>
        <tbody>
          {places.map((p) => {
            const chosen = compared.includes(p.location_id);
            const isSelected = p.location_id === selected;
            const noData = p.data_status === "unavailable" || p.priced_count === null;
            return (
              <tr key={p.location_id} aria-selected={isSelected} data-selected={isSelected || undefined}>
                <th scope="row">
                  <button
                    type="button"
                    className={styles["pick"]}
                    aria-pressed={isSelected}
                    aria-label={t.rynek.explore.select({ name: p.name })}
                    onClick={() => onSelect(p.location_id)}
                  >
                    {p.name}
                  </button>
                  <Link
                    to={href(p.location_id)}
                    className={styles["rowLink"]}
                    aria-label={t.rynek.explore.open({ name: p.name })}
                  >
                    {t.rynek.explore.openPlace}
                  </Link>
                </th>
                <td>
                  <StatusBadge status={p.data_status} />
                </td>
                {noData || p.sufficient !== true ? (
                  <td className={styles["muted"]} colSpan={2}>
                    {noData
                      ? t.rynek.explore.unavailable
                      : t.rynek.explore.withheld({ count: formatCount(p.priced_count ?? 0) })}
                  </td>
                ) : (
                  <>
                    <td className={styles["num"]}>{formatPricePerArea(p.median_ppm2)}</td>
                    <td className={styles["num"]}>{formatMoney(p.median_rent_pln, { decimals: 0 })}</td>
                  </>
                )}
                <td className={styles["num"]}>
                  {p.priced_count === null ? NOT_COMPUTED : formatCount(p.priced_count)}
                </td>
                <td>
                  <Button
                    type="button"
                    small
                    aria-pressed={chosen}
                    aria-label={(chosen ? t.rynek.compare.remove : t.rynek.compare.add)({ name: p.name })}
                    disabled={!chosen && compared.length >= MAX_COMPARED}
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
  );
}
