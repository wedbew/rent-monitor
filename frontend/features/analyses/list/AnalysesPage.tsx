import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, TransportError } from "../../../api/errors";
import { describeProblem, describeTransport } from "../../../api/problems";
import { formatAnalyses, formatDate, formatMoney, NOT_COMPUTED, formatCount } from "../../../api/format";
import { PageHeading } from "../../../shell/PageHeading";
import { Button, LinkButton } from "../../../ui/Button";
import { TextField } from "../../../ui/Field";
import { Segmented } from "../../../ui/Segmented";
import { Select } from "../../../ui/Select";
import { Skeleton } from "../../../ui/Skeleton";
import { InlineNotice } from "../../../ui/Status";
import type { AuditSummary } from "../queries";
import {
  type CollectionFilters,
  GRADE_OPTIONS,
  hasActiveFilters,
  readFilters,
  STATUS_OPTIONS,
  writeFilters,
} from "./filters";
import { AnalysesTable } from "./AnalysesTable";
import { AuditBadge } from "./AuditBadge";
import { useAuditList } from "./useAuditList";
import styles from "./AnalysesPage.module.css";
import { t } from "../../../i18n";

const title = (audit: AuditSummary) => t.common.listingTitle({ id: audit.otodom_id });
const money = (value: string | null) => (value === null ? NOT_COMPUTED : formatMoney(value, { decimals: 0 }));

// LEGAL[republication]: shows listing identifiers and asking-price summaries from the tenant's analyses (RM-275)
function Cards({ items }: { readonly items: readonly AuditSummary[] }) {
  return (
    <ul className={styles["cards"]} aria-label={t.analyses.list.cardsLabel}>
      {items.map((audit) => (
        <li key={audit.audit_id} className={`${styles["card"]} ${styles["cardWrap"]}`}>
          <div className={styles["cardTop"]}>
            <span className={styles["cardTitle"]}>
              <Link to={`/app/analyses/${audit.audit_id}`}>{title(audit)}</Link>
            </span>
            <AuditBadge audit={audit} />
          </div>
          <dl className={styles["facts"]}>
            <div>
              <dt>{t.analyses.list.columns.date}</dt>
              <dd>{formatDate(audit.created_at)}</dd>
            </div>
            <div>
              <dt>{t.analyses.list.columns.grade}</dt>
              <dd>{audit.grade ?? "—"}</dd>
            </div>
            <div>
              <dt>{t.analyses.list.columns.askingPrice}</dt>
              <dd>{money(audit.asking_price_pln)}</dd>
            </div>
            <div>
              <dt>{t.analyses.list.columns.maxBid}</dt>
              <dd>{money(audit.max_bid_pln)}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

function failureOf(error: unknown) {
  return error instanceof ApiError && error.code !== null
    ? describeProblem(error.code, { requestId: error.requestId })
    : describeTransport(error instanceof TransportError ? error.kind : "invalid-response");
}

/**
 * The person's analyses, newest first, over the API's cursor paging. View and filters are in the address. The
 * list is the server's: a filter is a request, "Załaduj więcej" asks for the next page, and the end of the list
 * is the absence of a cursor (never a guess from a short page).
 */
export function AnalysesPage() {
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const { query, items } = useAuditList(filters);
  const [draft, setDraft] = useState<string | null>(null);

  function update(patch: Partial<CollectionFilters>) {
    setParams(writeFilters({ ...filters, ...patch }));
    // Only a change to the search itself discards the typed text: switching the view or a filter keeps what the
    // person has typed and not yet sent.
    if (patch.q !== undefined) setDraft(null);
  }
  function search(event: FormEvent) {
    event.preventDefault();
    update({ q: (draft ?? filters.q).trim() });
  }

  const filtered = hasActiveFilters(filters);
  const refreshing = query.isFetching && !query.isPending && !query.isFetchingNextPage;

  return (
    <div className={styles["page"]}>
      <PageHeading
        title={t.analyses.list.title}
        eyebrow={t.analyses.list.eyebrow}
        lead={t.analyses.list.lead}
      />

      <section className={styles["filters"]} aria-label={t.analyses.list.filtersLabel}>
        <form
          className={styles["search"]}
          onSubmit={search}
          role="search"
          aria-label={t.analyses.list.searchLabel}
        >
          <TextField
            label={t.analyses.list.searchField}
            value={draft ?? filters.q}
            onValueChange={setDraft}
            autoComplete="off"
            spellCheck={false}
            maxLength={20}
          />
          <Button type="submit" icon="search">
            {t.analyses.list.search}
          </Button>
        </form>
        <Select
          label={t.analyses.list.statusFilter}
          value={filters.status}
          options={STATUS_OPTIONS}
          onValueChange={(status) => update({ status: status as CollectionFilters["status"] })}
        />
        <Select
          label={t.analyses.list.gradeFilter}
          value={filters.grade}
          options={GRADE_OPTIONS}
          onValueChange={(grade) => update({ grade: grade as CollectionFilters["grade"] })}
        />
      </section>

      <div className={styles["results"]}>
        <div className={styles["summary"]}>
          {items.length > 0 ? (
            <span className={styles["count"]} role="status">
              {refreshing
                ? t.analyses.list.refreshing
                : t.analyses.list.shown({ count: formatAnalyses(items.length) })}
            </span>
          ) : null}
          {filtered ? (
            <>
              <span className={styles["count"]}>{t.analyses.list.filtersOn}</span>
              <Button type="button" small onClick={() => update({ status: "", grade: "", q: "" })}>
                {t.analyses.list.clearFilters}
              </Button>
            </>
          ) : null}
        </div>
        <Segmented
          label={t.analyses.list.viewLabel}
          value={filters.view}
          options={[
            { value: "cards", label: t.analyses.list.viewCards, icon: "cards" },
            { value: "table", label: t.analyses.list.viewTable, icon: "table" },
          ]}
          onValueChange={(view) => update({ view })}
        />
      </div>

      {query.isPending ? (
        <div
          className={styles["skeletons"]}
          role="status"
          aria-busy="true"
          aria-label={t.analyses.list.loading}
        >
          <Skeleton height="72px" />
          <Skeleton height="72px" />
          <Skeleton height="72px" />
        </div>
      ) : query.isError && items.length === 0 ? (
        <InlineNotice
          tone="danger"
          title={t.analyses.list.failed}
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
        filtered ? (
          <div className={styles["empty"]}>
            <strong>{t.analyses.list.noMatchTitle}</strong>
            <p>{t.analyses.list.noMatchBody}</p>
          </div>
        ) : (
          <div className={styles["empty"]}>
            <strong>{t.dashboard.recent.emptyTitle}</strong>
            <p>{t.dashboard.recent.emptyBody}</p>
            <div>
              <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
                {t.dashboard.recent.emptyAction}
              </LinkButton>
            </div>
          </div>
        )
      ) : (
        <>
          {filters.view === "table" ? <AnalysesTable items={items} /> : <Cards items={items} />}
          <div className={styles["more"]}>
            {query.isFetchNextPageError ? (
              <InlineNotice tone="danger" title={t.analyses.list.moreFailed} live="alert">
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
                {t.analyses.list.loadMore}
              </Button>
            ) : (
              <span className={styles["count"]}>
                {t.analyses.list.allShown({ count: formatCount(items.length) })}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
