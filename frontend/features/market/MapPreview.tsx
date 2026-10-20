import { useEffect, useRef } from "react";

import { formatCount, formatDate, formatDateTime, formatMoney, formatPricePerArea } from "../../api/format";
import { t } from "../../i18n";
import { Button, LinkButton } from "../../ui/Button";
import { StatusBadge } from "./StatusBadge";
import type { OverviewPlace } from "./queries";
import styles from "./map.module.css";

interface Props {
  readonly place: OverviewPlace | undefined;
  /** Several places at one point the map cannot separate: pick one to preview. */
  readonly cluster: readonly OverviewPlace[] | null;
  readonly groupLabel: string;
  readonly compared: boolean;
  readonly compareFull: boolean;
  readonly href: string;
  readonly onClose: () => void;
  readonly onToggleCompare: () => void;
  readonly onPick: (id: string) => void;
}

/** The numbers of one place, or the reason there are none, in words and never as a zero. */
function Figures({ place }: { readonly place: OverviewPlace }) {
  if (place.data_status === "unavailable" || place.priced_count === null)
    return <p className={styles["previewNote"]}>{t.rynek.explore.unavailable}</p>;
  if (place.sufficient !== true)
    return (
      <p className={styles["previewNote"]}>
        {t.rynek.explore.withheld({ count: formatCount(place.priced_count) })}
      </p>
    );
  return (
    <dl className={styles["previewFacts"]}>
      <div>
        <dt>{t.rynek.preview.ppm2}</dt>
        <dd>{formatPricePerArea(place.median_ppm2)}</dd>
      </div>
      <div>
        <dt>{t.rynek.preview.rent}</dt>
        <dd>{formatMoney(place.median_rent_pln, { decimals: 0 })}</dd>
      </div>
      <div>
        <dt>{t.rynek.preview.sample}</dt>
        <dd>{formatCount(place.priced_count)}</dd>
      </div>
    </dl>
  );
}

/**
 * What a marker opens: the place's name and status, its figures for the chosen group of flats with the day they
 * come from and when the data was last refreshed, and the two actions (open the place, add it to the comparison).
 * It is a plain region, not a modal: nothing traps focus and Escape or the close button dismiss it. A tap opens it
 * too, so a touch user has everything a hover shows.
 */
export function MapPreview({
  place,
  cluster,
  groupLabel,
  compared,
  compareFull,
  href,
  onClose,
  onToggleCompare,
  onPick,
}: Props) {
  const ref = useRef<HTMLElement>(null);
  // The marker that opened this preview is not drawn while it is open (it would sit under it), so keyboard focus
  // moves here instead of falling to the page; Escape inside closes it and the map returns focus to the marker.
  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, [place?.location_id]);
  return (
    <aside
      ref={ref}
      tabIndex={-1}
      className={styles["preview"]}
      aria-label={t.rynek.preview.heading}
      data-map-ui
      data-testid="map-preview"
    >
      <div className={styles["previewHead"]}>
        <h3 className={styles["previewTitle"]}>
          {place === undefined
            ? t.rynek.preview.clusterHeading({ count: formatCount(cluster?.length ?? 0) })
            : place.name}
        </h3>
        <Button type="button" onClick={onClose} aria-label={t.rynek.preview.close}>
          {t.rynek.preview.closeShort}
        </Button>
      </div>
      {place === undefined ? (
        <>
          <p className={styles["previewNote"]}>{t.rynek.preview.clusterBody}</p>
          <ul className={styles["previewList"]}>
            {(cluster ?? []).map((p) => (
              <li key={p.location_id}>
                <Button
                  type="button"
                  aria-label={t.rynek.preview.clusterChoose({ name: p.name })}
                  onClick={() => onPick(p.location_id)}
                >
                  {p.name}
                </Button>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <>
          <div className={styles["previewMeta"]}>
            <StatusBadge status={place.data_status} />
            <span>{t.rynek.preview.group({ filter: groupLabel })}</span>
          </div>
          <Figures place={place} />
          <dl className={styles["previewFacts"]}>
            <div>
              <dt>{t.rynek.preview.day}</dt>
              <dd>
                {place.latest_summary_date === null ? t.format.noDate : formatDate(place.latest_summary_date)}
              </dd>
            </div>
            <div>
              <dt>{t.rynek.preview.freshness}</dt>
              <dd>
                {place.last_successful_refresh_at === null
                  ? t.format.noDate
                  : formatDateTime(place.last_successful_refresh_at)}
              </dd>
            </div>
          </dl>
          <div className={styles["previewActions"]}>
            <LinkButton to={href} variant="primary" icon="arrow">
              {t.rynek.preview.open}
            </LinkButton>
            <Button
              type="button"
              aria-pressed={compared}
              disabled={!compared && compareFull}
              onClick={onToggleCompare}
            >
              {compared
                ? t.rynek.preview.compareRemove
                : compareFull
                  ? t.rynek.preview.compareFull
                  : t.rynek.preview.compareAdd}
            </Button>
          </div>
        </>
      )}
    </aside>
  );
}
