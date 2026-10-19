import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router";

import {
  formatCount,
  formatCounted,
  formatDate,
  formatMoney,
  formatPricePerArea,
  NOT_COMPUTED,
} from "../../api/format";
import { t } from "../../i18n";
import { PageHeading } from "../../shell/PageHeading";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { failureOf } from "./failure";
import { cleanSearch, placeAddress } from "./filters";
import { type LocationSummary, useLocations } from "./queries";
import { ScrollRegion } from "./ScrollRegion";
import { StatusBadge } from "./StatusBadge";
import styles from "./market.module.css";

// LEGAL[republication]: shows aggregates of Otodom asking rents per place, never an offer or listing text (RM-422)
function Row({ place, q }: { readonly place: LocationSummary; readonly q: string }) {
  const withheld = place.withheld_reason !== null;
  return (
    <tr>
      <th scope="row">
        <Link to={placeAddress(place.location_id, q)}>{place.name}</Link>
      </th>
      <td>
        <StatusBadge status={place.data_status} />
      </td>
      <td className={styles["num"]}>
        {withheld ? (
          <span className={styles["withheld"]}>{t.market.withheld.insufficient_sample}</span>
        ) : (
          formatMoney(place.median_rent_pln, { decimals: 0 })
        )}
      </td>
      <td className={styles["num"]}>{formatPricePerArea(place.median_ppm2)}</td>
      <td className={styles["num"]}>
        {place.priced_count === null ? NOT_COMPUTED : formatCount(place.priced_count)}
      </td>
      <td>{place.latest_summary_date === null ? NOT_COMPUTED : formatDate(place.latest_summary_date)}</td>
    </tr>
  );
}

/**
 * The places with their latest asking-rent medians. The search is in the address; the list is the server's: paged
 * over its cursor, never sliced here, and its end is the absence of a cursor. A place with no published reading
 * says so instead of showing a zero.
 */
export function MarketPage() {
  const [params, setParams] = useSearchParams();
  const q = cleanSearch(params.get("q"));
  const { query, items } = useLocations(q);
  const [draft, setDraft] = useState<string | null>(null);

  function search(event: FormEvent) {
    event.preventDefault();
    const next = cleanSearch(draft ?? q);
    setParams(next === "" ? {} : { q: next });
    setDraft(null);
  }
  const refreshing = query.isFetching && !query.isPending && !query.isFetchingNextPage;

  return (
    <div className={styles["page"]}>
      <PageHeading title={t.market.title} eyebrow={t.market.eyebrow} lead={t.market.lead} />

      <section className={styles["filters"]} aria-label={t.market.list.filtersLabel}>
        <form
          className={styles["search"]}
          onSubmit={search}
          role="search"
          aria-label={t.market.list.searchLabel}
        >
          <TextField
            label={t.market.list.searchField}
            value={draft ?? q}
            onValueChange={setDraft}
            autoComplete="off"
            spellCheck={false}
            maxLength={60}
          />
          <Button type="submit" icon="search">
            {t.market.list.search}
          </Button>
        </form>
        {q !== "" ? (
          <Button
            type="button"
            small
            onClick={() => {
              setParams({});
              setDraft(null);
            }}
          >
            {t.market.list.clear}
          </Button>
        ) : null}
      </section>

      {query.isPending ? (
        <div
          className={styles["skeletons"]}
          role="status"
          aria-busy="true"
          aria-label={t.market.list.loading}
        >
          <Skeleton height="48px" />
          <Skeleton height="48px" />
          <Skeleton height="48px" />
        </div>
      ) : query.isError && items.length === 0 ? (
        <InlineNotice
          tone="danger"
          title={t.market.list.failed}
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={query.isFetching}
              onClick={() => void query.refetch()}
            >
              {t.common.retry}
            </Button>
          }
        >
          {failureOf(query.error).detail}
        </InlineNotice>
      ) : items.length === 0 ? (
        <div className={styles["empty"]}>
          <strong>{q === "" ? t.market.list.emptyTitle : t.market.list.noMatchTitle}</strong>
          <p>{q === "" ? t.market.list.emptyBody : t.market.list.noMatchBody}</p>
        </div>
      ) : (
        <>
          <div className={styles["summary"]}>
            <span className={styles["count"]} role="status">
              {refreshing
                ? t.market.list.refreshing
                : t.market.list.shown({ count: formatCounted(items.length, t.format.nouns.places) })}
            </span>
          </div>
          <ScrollRegion label={t.market.list.resultsLabel}>
            <table className={styles["table"]}>
              <caption>{t.market.list.tableCaption}</caption>
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
                  <th scope="col">{t.market.detail.latestHeading}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((place) => (
                  <Row key={place.location_id} place={place} q={q} />
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <div className={styles["more"]}>
            {query.isFetchNextPageError ? (
              <InlineNotice tone="danger" title={t.market.list.moreFailed} live="alert">
                {failureOf(query.error).detail}
              </InlineNotice>
            ) : null}
            {query.hasNextPage ? (
              <Button
                type="button"
                icon="refresh"
                busy={query.isFetchingNextPage}
                onClick={() => void query.fetchNextPage()}
              >
                {t.market.list.loadMore}
              </Button>
            ) : (
              <span className={styles["count"]}>
                {t.market.list.allShown({ count: formatCount(items.length) })}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
