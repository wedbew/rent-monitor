import { useMemo } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";

import { formatCount } from "../../api/format";
import { t } from "../../i18n";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { gusPlaceAddress } from "./addresses";
import { failureOf, isClosed, isNotFound } from "./failure";
import { MAX_COMPARED, parseIds, toggleCompared } from "./explore";
import { GusCompare } from "./GusCompare";
import { GusProfile } from "./GusProfile";
import { Leaderboard } from "./Leaderboard";
import { PlacePicker } from "./PlacePicker";
import { useLocationRanking, useRankingOverview } from "./queries";
import { RankingCard } from "./RankingCard";
import { useMarketTitle } from "./MarketLayout";
import styles from "./gus.module.css";

const ID = /^[a-z0-9-]{1,64}$/;

/**
 * The GUS tab. The selected place is the path (`/app/market/gus/:id`) or `?sel=`; the places chosen for a comparison
 * are `?ids=`. It shows, for the gmina that place belongs to, the experimental index with its position and components,
 * then the places of the account in order of that index, a side-by-side comparison, and the full GUS profile. Nothing
 * here uses Otodom figures, and the source, period and territorial grain are stated by the layout above.
 */
export function GusPage() {
  const { locationId } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const sel =
    locationId ?? (params.get("sel") !== null && ID.test(params.get("sel") ?? "") ? params.get("sel") : null);
  const ids = parseIds(params.get("ids"));
  const overview = useRankingOverview();
  const ranking = useLocationRanking(sel ?? "", sel !== null);
  const names = useMemo(
    () => new Map((overview.data?.items ?? []).map((p) => [p.location_id, p.name])),
    [overview.data],
  );
  const placeName = ranking.data?.name ?? (sel === null ? null : (names.get(sel) ?? sel));
  useMarketTitle(placeName);

  const choose = (id: string) => {
    void navigate({
      pathname: gusPlaceAddress(id),
      search: params.get("ids") === null ? "" : `?ids=${params.get("ids")}`,
    });
  };
  const toggle = (id: string) => {
    const next = toggleCompared(ids, id);
    const p = new URLSearchParams(params);
    if (next.length === 0) p.delete("ids");
    else p.set("ids", next.join(","));
    setParams(p, { replace: true });
  };

  return (
    <div className={styles["page"]}>
      <section aria-labelledby="gus-ranking" className={styles["section"]}>
        <h2 id="gus-ranking">{t.rynek.gus.rankingHeading}</h2>
        {overview.data === undefined ? null : (
          <PlacePicker
            label={t.rynek.gus.pickerLabel}
            hint={t.rynek.gus.pickerHint}
            places={overview.data.items.map((p) => ({ id: p.location_id, name: p.name }))}
            selectedId={sel}
            onPick={choose}
          />
        )}
        {sel === null ? (
          <p className={styles["muted"]}>{t.rynek.gus.pickerHint}</p>
        ) : ranking.isPending ? (
          <div role="status" aria-busy="true" aria-label={t.rynek.gus.leaderboard.loading}>
            <Skeleton height="320px" />
          </div>
        ) : ranking.data === undefined ? (
          isClosed(ranking.error) ? (
            <InlineNotice tone="info" title={t.rynek.place.closedTitle} live="alert">
              {t.rynek.place.closedBody}
            </InlineNotice>
          ) : isNotFound(ranking.error) ? (
            <InlineNotice tone="warning" title={t.rynek.place.notFoundTitle} live="alert">
              {t.rynek.place.notFoundBody}
            </InlineNotice>
          ) : (
            <InlineNotice
              tone="danger"
              title={t.rynek.gus.leaderboard.failed}
              live="alert"
              actions={
                <Button
                  type="button"
                  variant="primary"
                  icon="refresh"
                  busy={ranking.isFetching}
                  onClick={() => void ranking.refetch()}
                >
                  {t.common.retry}
                </Button>
              }
            >
              {failureOf(ranking.error).detail}
            </InlineNotice>
          )
        ) : (
          <>
            <p className={styles["context"]}>{t.rynek.gus.selectedFor({ name: ranking.data.name })}</p>
            {ranking.data.mapping.relation === "within_gmina" && ranking.data.index.gmina !== null ? (
              <p className={styles["muted"]}>
                {t.rynek.gus.withinNote({ gmina: ranking.data.index.gmina.name })}
              </p>
            ) : null}
            <RankingCard
              index={ranking.data.index}
              placeName={ranking.data.name}
              profileHref={(key) => `${gusPlaceAddress(ranking.data?.location_id ?? "")}#metric-${key}`}
            />
          </>
        )}
      </section>

      {overview.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.rynek.gus.leaderboard.loading}>
          <Skeleton height="200px" />
        </div>
      ) : overview.data === undefined ? (
        <InlineNotice
          tone="danger"
          title={t.rynek.gus.leaderboard.failed}
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
      ) : (
        <>
          <Leaderboard
            overview={overview.data}
            selected={sel}
            compared={ids}
            onSelect={choose}
            onToggleCompare={toggle}
          />
          <p className={styles["live"]} role="status">
            {ids.length >= MAX_COMPARED ? t.rynek.compare.limit({ max: formatCount(MAX_COMPARED) }) : null}
          </p>
          <GusCompare ids={ids} names={names} />
        </>
      )}

      {sel === null ? null : <GusProfile locationId={sel} placeName={placeName ?? sel} />}
    </div>
  );
}
