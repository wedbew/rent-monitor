import { type FormEvent, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { ApiError, TransportError } from "../../../api/errors";
import { describeProblem, describeTransport } from "../../../api/problems";
import { formatAnalyses, formatDate, formatMoney, NOT_COMPUTED, formatCount } from "../../../api/format";
import { PageHeading } from "../../../shell/PageHeading";
import { Button, LinkButton } from "../../../ui/Button";
import { TextField } from "../../../ui/Field";
import { Select } from "../../../ui/Select";
import { Skeleton } from "../../../ui/Skeleton";
import { InlineNotice } from "../../../ui/Status";
import type { AuditSummary } from "../queries";
import { statusCopy } from "../status";
import {
  type CollectionFilters,
  GRADE_OPTIONS,
  hasActiveFilters,
  readFilters,
  STATUS_OPTIONS,
  type View,
  writeFilters,
} from "./filters";
import { useAuditList } from "./useAuditList";
import styles from "./AnalysesPage.module.css";

const title = (audit: AuditSummary) => `Ogłoszenie ${audit.otodom_id}`;
const money = (value: string | null) => (value === null ? NOT_COMPUTED : formatMoney(value, { decimals: 0 }));

function Badge({ audit }: { readonly audit: AuditSummary }) {
  const copy = statusCopy(audit.status, audit.error_code);
  return <span className={`${styles["badge"]} ${styles[copy.tone]}`}>{copy.label}</span>;
}

// LEGAL[republication]: shows listing identifiers and asking-price summaries from the tenant's analyses (RM-275)
function Cards({ items }: { readonly items: readonly AuditSummary[] }) {
  return (
    <ul className={styles["cards"]} aria-label="Analizy">
      {items.map((audit) => (
        <li key={audit.audit_id} className={`${styles["card"]} ${styles["cardWrap"]}`}>
          <div className={styles["cardTop"]}>
            <span className={styles["cardTitle"]}>
              <Link to={`/app/analyses/${audit.audit_id}`}>{title(audit)}</Link>
            </span>
            <Badge audit={audit} />
          </div>
          <dl className={styles["facts"]}>
            <div>
              <dt>Data</dt>
              <dd>{formatDate(audit.created_at)}</dd>
            </div>
            <div>
              <dt>Ocena</dt>
              <dd>{audit.grade ?? "—"}</dd>
            </div>
            <div>
              <dt>Cena ofertowa</dt>
              <dd>{money(audit.asking_price_pln)}</dd>
            </div>
            <div>
              <dt>Cena progowa</dt>
              <dd>{money(audit.max_bid_pln)}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  );
}

// LEGAL[republication]: shows the same listing identifiers and asking-price summaries in a table (RM-275)
function Table({ items }: { readonly items: readonly AuditSummary[] }) {
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
    <div className={styles["region"]} role="region" aria-label="Tabela analiz" tabIndex={0}>
      <table className={styles["table"]}>
        <caption>Od najnowszej. Kwoty w złotych.</caption>
        <thead>
          <tr>
            <th scope="col">Ogłoszenie</th>
            <th scope="col">Data</th>
            <th scope="col">Status</th>
            <th scope="col">Ocena</th>
            <th scope="col" className={styles["num"]}>
              Cena ofertowa
            </th>
            <th scope="col" className={styles["num"]}>
              Cena progowa
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((audit) => (
            <tr key={audit.audit_id}>
              <th scope="row">
                <Link to={`/app/analyses/${audit.audit_id}`}>{title(audit)}</Link>
              </th>
              <td>{formatDate(audit.created_at)}</td>
              <td>
                <Badge audit={audit} />
              </td>
              <td>{audit.grade ?? "—"}</td>
              <td className={styles["num"]}>{money(audit.asking_price_pln)}</td>
              <td className={styles["num"]}>{money(audit.max_bid_pln)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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
    setDraft(null);
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
        title="Moje analizy"
        eyebrow="Historia"
        lead="Wszystkie Twoje analizy, od najnowszej. Raport otwierasz bez zużywania kolejnego."
      />

      <div className={styles["toolbar"]}>
        <form className={styles["search"]} onSubmit={search} role="search" aria-label="Szukaj analizy">
          <TextField
            label="Numer ogłoszenia (początek)"
            value={draft ?? filters.q}
            onValueChange={setDraft}
            autoComplete="off"
            spellCheck={false}
            maxLength={20}
          />
          <Button type="submit" icon="search">
            Szukaj
          </Button>
        </form>
        <Select
          label="Status"
          value={filters.status}
          options={STATUS_OPTIONS}
          onValueChange={(status) => update({ status: status as CollectionFilters["status"] })}
        />
        <Select
          label="Ocena"
          value={filters.grade}
          options={GRADE_OPTIONS}
          onValueChange={(grade) => update({ grade: grade as CollectionFilters["grade"] })}
        />
        <div className={styles["views"]} role="group" aria-label="Widok">
          {(["cards", "table"] as const satisfies readonly View[]).map((view) => (
            <Button
              key={view}
              type="button"
              small
              variant={filters.view === view ? "primary" : "secondary"}
              aria-pressed={filters.view === view}
              onClick={() => update({ view })}
            >
              {view === "cards" ? "Karty" : "Tabela"}
            </Button>
          ))}
        </div>
      </div>

      {filtered ? (
        <div className={styles["bar"]}>
          <span className={styles["count"]}>Filtry są włączone.</span>
          <Button type="button" small onClick={() => update({ status: "", grade: "", q: "" })}>
            Wyczyść filtry
          </Button>
        </div>
      ) : null}

      {query.isPending ? (
        <div className={styles["skeletons"]} role="status" aria-busy="true" aria-label="Wczytuję analizy">
          <Skeleton height="72px" />
          <Skeleton height="72px" />
          <Skeleton height="72px" />
        </div>
      ) : query.isError && items.length === 0 ? (
        <InlineNotice
          tone="danger"
          title="Nie udało się wczytać analiz"
          live="alert"
          actions={
            <Button
              type="button"
              variant="primary"
              icon="refresh"
              busy={query.isFetching}
              onClick={() => void query.refetch()}
            >
              Spróbuj ponownie
            </Button>
          }
        >
          {failureOf(query.error).detail}
        </InlineNotice>
      ) : items.length === 0 ? (
        filtered ? (
          <div className={styles["empty"]}>
            <strong>Żadna analiza nie pasuje do filtrów</strong>
            <p>Zmień filtry albo wyczyść je, aby zobaczyć wszystkie analizy.</p>
          </div>
        ) : (
          <div className={styles["empty"]}>
            <strong>Nie masz jeszcze żadnej analizy</strong>
            <p>Wklej adres ogłoszenia z Otodom, a w kilkadziesiąt sekund dostaniesz raport.</p>
            <div>
              <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
                Sprawdź pierwsze mieszkanie
              </LinkButton>
            </div>
          </div>
        )
      ) : (
        <>
          <div className={styles["bar"]}>
            <span className={styles["count"]} role="status">
              {refreshing ? "Odświeżam listę…" : `Wyświetlono ${formatAnalyses(items.length)}`}
            </span>
          </div>
          {filters.view === "table" ? <Table items={items} /> : <Cards items={items} />}
          <div className={styles["more"]}>
            {query.isFetchNextPageError ? (
              <InlineNotice tone="danger" title="Nie udało się wczytać kolejnych analiz" live="alert">
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
                Załaduj więcej
              </Button>
            ) : (
              <span className={styles["count"]}>To wszystkie analizy ({formatCount(items.length)}).</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
