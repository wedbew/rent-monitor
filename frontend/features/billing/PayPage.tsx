import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { PageHeading } from "../../shell/PageHeading";
import { Button, LinkButton } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { TRANSACTION_ID } from "./guards";
import { openCheckout, PaddleError, paddleConfigured } from "./paddle";
import styles from "./billing.module.css";
import { t } from "../../i18n";

/**
 * `/pay` is the default payment link Paddle is configured with (docs/PADDLE-INTEGRATION.md section 3): it receives
 * `?_ptxn=<transaction>`, loads Paddle.js with the public client token only and opens that transaction. A value that
 * is not a Paddle transaction id is never handed to Paddle.js. The return address leads to the page that polls the
 * server; nothing here grants anything.
 */
export function PayPage() {
  const [params] = useSearchParams();
  const txn = params.get("_ptxn") ?? "";
  const valid = TRANSACTION_ID.test(txn);
  const configured = paddleConfigured();
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!valid || !configured) return;
    // The lifetime of this transaction on this page: leaving, or a different `_ptxn`, cancels an open still loading.
    const lifetime = new AbortController();
    openCheckout(txn, `/app/credits/success?txn=${txn}`, { signal: lifetime.signal }).catch(
      (error: unknown) => {
        if (error instanceof PaddleError && error.kind === "cancelled") return;
        if (!lifetime.signal.aborted) setFailed(true);
      },
    );
    return () => lifetime.abort();
  }, [valid, configured, txn, attempt]);

  return (
    <div className={styles["page"]}>
      <PageHeading title={t.billing.pay.title} lead={t.billing.pay.lead} />
      {!configured ? (
        <InlineNotice tone="info" title={t.billing.pay.notConfiguredTitle}>
          {t.billing.packs.notConfiguredBody}
        </InlineNotice>
      ) : !valid ? (
        <InlineNotice tone="warning" title={t.billing.pay.invalidTitle}>
          {t.billing.pay.invalidBody}
        </InlineNotice>
      ) : failed ? (
        <InlineNotice
          tone="danger"
          title={t.billing.pay.failedTitle}
          live="alert"
          actions={
            <Button
              type="button"
              icon="refresh"
              onClick={() => {
                setFailed(false);
                setAttempt((n) => n + 1);
              }}
            >
              {t.billing.pay.retry}
            </Button>
          }
        />
      ) : (
        <p role="status" className={styles["note"]}>
          {t.billing.pay.opening}
        </p>
      )}
      <div className={styles["actions"]}>
        <LinkButton to="/app/credits" icon="arrow">
          {t.billing.pay.toCredits}
        </LinkButton>
      </div>
    </div>
  );
}
