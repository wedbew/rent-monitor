import { useState } from "react";
import { useSearchParams } from "react-router";

import { formatReports } from "../../api/format";
import { PageHeading } from "../../shell/PageHeading";
import { Button, LinkButton } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { ProblemNotice } from "../auth/ProblemNotice";
import { readFailure } from "../auth/forms";
import { SETTLED, shortReference, TRANSACTION_ID } from "./guards";
import { usePurchase, usePurchases } from "./queries";
import styles from "./billing.module.css";
import { t } from "../../i18n";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** After this long without a settled answer the page says it is taking longer, and still never claims credit. */
export const SLOW_AFTER_MS = 120_000;

/**
 * Where Paddle sends the buyer back (`?purchase=<id>`, or `?txn=<transaction>` from the payment-link page). The
 * browser's "success" proves nothing: this page asks the server, with backoff, until it says granted, failed, under
 * review or refunded, and shows exactly that. It never grants, never launches an analysis, never counts credit.
 */
export function SuccessPage() {
  const [params] = useSearchParams();
  const purchaseParam = params.get("purchase") ?? "";
  const txn = params.get("txn") ?? "";
  const byTransaction = !UUID.test(purchaseParam) && TRANSACTION_ID.test(txn);
  const list = usePurchases();
  const resolved = UUID.test(purchaseParam)
    ? purchaseParam
    : byTransaction
      ? (list.data?.purchases.find((p) => p.transactionId === txn)?.id ?? null)
      : null;
  const purchase = usePurchase(resolved);
  const [openedAt] = useState(() => Date.now());

  const body = () => {
    if (!UUID.test(purchaseParam) && !byTransaction)
      return (
        <InlineNotice tone="warning" title={t.billing.success.unknownPurchaseTitle}>
          {t.billing.success.unknownPurchaseBody}
        </InlineNotice>
      );
    if (resolved === null) {
      // Not found among rows that could not all be read is not "unknown": it may be one of the hidden ones.
      if (list.isError || (list.data?.hidden ?? 0) > 0)
        return <InlineNotice tone="danger" title={t.billing.success.failedLoad} live="alert" />;
      if (list.isSuccess)
        return (
          <InlineNotice tone="warning" title={t.billing.success.unknownPurchaseTitle}>
            {t.billing.success.unknownPurchaseBody}
          </InlineNotice>
        );
      return (
        <div role="status" aria-busy="true" aria-label={t.billing.success.checking}>
          <Skeleton height="72px" />
        </div>
      );
    }
    if (purchase.isError && (purchase.data === undefined || purchase.permanentFailure)) {
      const general = readFailure(purchase.error).general;
      // A permanent answer (not found, not yours) does not change by asking again; anything else can be retried by hand.
      const retry = purchase.permanentFailure ? undefined : (
        <Button type="button" icon="refresh" onClick={purchase.checkAgain}>
          {t.billing.success.checkAgain}
        </Button>
      );
      return general !== null ? (
        <ProblemNotice problem={general} actions={retry} />
      ) : (
        <InlineNotice tone="danger" title={t.billing.success.failedLoad} live="alert" actions={retry} />
      );
    }
    if (purchase.data === undefined)
      return (
        <div role="status" aria-busy="true" aria-label={t.billing.success.checking}>
          <Skeleton height="72px" />
        </div>
      );
    const data = purchase.data;
    const copy = t.billing.purchases.states[data.state];
    if (data.state === "granted")
      return (
        <InlineNotice tone="success" title={t.billing.success.grantedTitle} live="status">
          {t.billing.success.grantedBody({ reports: formatReports(data.reports) })}
        </InlineNotice>
      );
    if (SETTLED.has(data.state))
      return (
        <InlineNotice tone={data.state === "failed" ? "danger" : "warning"} title={copy.label} live="status">
          {copy.detail} {t.billing.checkout.reference({ id: shortReference(data.id) })}
        </InlineNotice>
      );
    const slow = purchase.dataUpdatedAt - openedAt >= SLOW_AFTER_MS;
    if (purchase.gaveUp)
      return (
        <InlineNotice
          tone="warning"
          title={t.billing.success.gaveUpTitle}
          live="status"
          actions={
            <Button type="button" icon="refresh" onClick={purchase.checkAgain}>
              {t.billing.success.checkAgain}
            </Button>
          }
        >
          {t.billing.success.gaveUpBody} {t.billing.checkout.reference({ id: shortReference(data.id) })}
        </InlineNotice>
      );
    return (
      <div className={styles["stack"]}>
        {purchase.isError ? (
          <InlineNotice tone="warning" title={t.billing.success.staleTitle} live="status">
            {t.billing.success.staleBody}
          </InlineNotice>
        ) : null}
        <InlineNotice tone="info" title={slow ? t.billing.success.slowTitle : copy.label} live="status">
          {t.billing.success.waiting} {t.billing.success.doNotPayAgain}{" "}
          {t.billing.checkout.reference({ id: shortReference(data.id) })}
        </InlineNotice>
      </div>
    );
  };

  const granted = purchase.data?.state === "granted";
  return (
    <div className={styles["page"]}>
      <PageHeading title={t.billing.success.title} />
      {body()}
      <div className={styles["actions"]}>
        {granted ? (
          <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
            {t.billing.success.toAnalysis}
          </LinkButton>
        ) : null}
        <LinkButton to="/app/credits" icon="arrow">
          {t.billing.success.toPurchases}
        </LinkButton>
      </div>
    </div>
  );
}
