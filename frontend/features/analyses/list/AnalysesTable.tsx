import { createColumnHelper, tableFeatures, useTable } from "@tanstack/react-table";
import { Link } from "react-router";

import { formatDate, formatMoney, NOT_COMPUTED } from "../../../api/format";
import { t } from "../../../i18n";
import type { AuditSummary } from "../queries";
import { SaveToggle } from "../../saved/SaveToggle";
import { AuditBadge } from "./AuditBadge";
import styles from "./AnalysesPage.module.css";

const money = (value: string | null) => (value === null ? NOT_COMPUTED : formatMoney(value, { decimals: 0 }));

/**
 * No client-side features are registered on purpose. Filtering, ordering and paging belong to the server: the API
 * filters by status, grade and id prefix, orders newest first and pages by cursor. The table therefore only lays out
 * the rows the server returned and never sorts, filters or slices them, so nothing here can look global and be local.
 */
const features = tableFeatures({});
const column = createColumnHelper<typeof features, AuditSummary>();
const L = t.analyses.list.columns;

const columns = column.columns([
  column.display({
    id: "listing",
    header: L.listing,
    cell: ({ row }) => (
      <Link to={`/app/analyses/${row.original.audit_id}`}>
        {t.common.listingTitle({ id: row.original.otodom_id })}
      </Link>
    ),
  }),
  column.display({ id: "date", header: L.date, cell: ({ row }) => formatDate(row.original.created_at) }),
  column.display({ id: "status", header: L.status, cell: ({ row }) => <AuditBadge audit={row.original} /> }),
  column.display({ id: "grade", header: L.grade, cell: ({ row }) => row.original.grade ?? "—" }),
  column.display({
    id: "askingPrice",
    header: L.askingPrice,
    cell: ({ row }) => money(row.original.asking_price_pln),
    meta: { numeric: true },
  }),
  column.display({
    id: "maxBid",
    header: L.maxBid,
    cell: ({ row }) => money(row.original.max_bid_pln),
    meta: { numeric: true },
  }),
  column.display({
    id: "saved",
    header: L.saved,
    cell: ({ row }) => <SaveToggle otodomId={row.original.otodom_id} small />,
  }),
]);

/**
 * The analyses as a semantic table (TanStack Table lays out columns and rows). The listing cell is the row header and
 * the only link, as in the cards; the date column says it is the order the server uses (`aria-sort`), which is a
 * fact about the data and not a control: the API offers no other order.
 */
// LEGAL[republication]: shows the same listing identifiers and asking-price summaries in a table (RM-275)
export function AnalysesTable({ items }: { readonly items: readonly AuditSummary[] }) {
  const table = useTable({ features, columns, data: items });
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
    <div className={styles["region"]} role="region" aria-label={t.analyses.list.tableLabel} tabIndex={0}>
      <table className={styles["table"]}>
        <caption>{t.analyses.list.tableCaption}</caption>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th
                  key={header.id}
                  scope="col"
                  className={header.column.columnDef.meta?.numeric ? styles["num"] : undefined}
                  aria-sort={header.column.id === "date" ? "descending" : undefined}
                >
                  {header.isPlaceholder ? null : <table.FlexRender header={header} />}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.original.audit_id}>
              {row.getAllCells().map((cell) =>
                cell.column.id === "listing" ? (
                  <th key={cell.id} scope="row">
                    <table.FlexRender cell={cell} />
                  </th>
                ) : (
                  <td
                    key={cell.id}
                    className={cell.column.columnDef.meta?.numeric ? styles["num"] : undefined}
                  >
                    <table.FlexRender cell={cell} />
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
