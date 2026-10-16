import { useState } from "react";

import { formatDateTime, formatMoney, formatReports } from "../../api/format";
import { PageHeading } from "../../shell/PageHeading";
import { useMe } from "../../shell/session";
import { isCurrentSession, sessionGeneration } from "../../shell/tenant";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { readFailure } from "../auth/forms";
import { ProblemNotice } from "../auth/ProblemNotice";
import { type Pack, type Purchase, type PurchaseState, SETTLED } from "./guards";
import { openCheckout, paddleConfigured } from "./paddle";
import { isAmbiguous, useCheckout, useInvoice, usePacks, usePurchases } from "./queries";
import styles from "./billing.module.css";
import { t } from "../../i18n";

/** The order number the person can quote: the start of its id, never anything secret. */
export const shortReference = (id: string): string => id.slice(0, 8);

const successPath = (purchaseId: string) => `/app/credits/success?purchase=${purchaseId}`;

function failureOf(error: unknown) {
  return readFailure(error).general;
}

function Balance() {
  const me = useMe();
  return (
    <section className={styles["balance"]} aria-label={t.billing.balance.label}>
      <p className={styles["eyebrow"]}>{t.billing.balance.label}</p>
      <p className={styles["big"]}>{formatReports(me.credit_balance)}</p>
      <p className={styles["note"]}>{t.billing.lead}</p>
    </section>
  );
}

function PackCard({
  pack,
  disabled,
  busy,
  onBuy,
}: {
  readonly pack: Pack;
  readonly disabled: boolean;
  readonly busy: boolean;
  readonly onBuy: (pack: Pack) => void;
}) {
  const reports = formatReports(pack.reports);
  return (
    <li className={styles["pack"]}>
      <strong className={styles["packTitle"]}>{t.billing.packs.title({ reports })}</strong>
      <span className={styles["price"]}>
        {t.billing.packs.price({ price: formatMoney(pack.grossPln, { decimals: 0 }) })}
      </span>
      <Button
        type="button"
        variant="primary"
        aria-label={t.billing.packs.buyLabel({ reports })}
        disabled={disabled}
        busy={busy}
        onClick={() => onBuy(pack)}
      >
        {t.billing.packs.buy}
      </Button>
    </li>
  );
}

function PacksSection() {
  const me = useMe();
  const packs = usePacks();
  const checkout = useCheckout();
  const [opening, setOpening] = useState<string | null>(null);
  const [openError, setOpenError] = useState<Purchase | null>(null);
  const [creationUnknown, setCreationUnknown] = useState<Purchase | null>(null);

  const buy = (pack: Pack) => {
    if (checkout.isPending || opening !== null) return;
    const started = sessionGeneration();
    setOpenError(null);
    setCreationUnknown(null);
    checkout.mutate(pack.code, {
      onSuccess: (purchase) => {
        if (!isCurrentSession(started)) return;
        if (purchase.state === "creation_unknown" || purchase.transactionId === null) {
          setCreationUnknown(purchase);
          return;
        }
        if (SETTLED.has(purchase.state)) return;
        setOpening(purchase.id);
        openCheckout(purchase.transactionId, successPath(purchase.id))
          .catch(() => {
            if (isCurrentSession(started)) setOpenError(purchase);
          })
          .finally(() => {
            if (isCurrentSession(started)) setOpening(null);
          });
      },
    });
  };

  const body = () => {
    if (packs.isPending)
      return (
        <div role="status" aria-busy="true" aria-label={t.billing.packs.loading}>
          <Skeleton height="96px" />
        </div>
      );
    if (packs.isError)
      return (
        <InlineNotice
          tone="danger"
          title={t.billing.packs.failed}
          live="alert"
          actions={
            <Button type="button" icon="refresh" onClick={() => void packs.refetch()}>
              {t.common.retry}
            </Button>
          }
        />
      );
    if (!packs.data.enabled)
      return (
        <InlineNotice tone="info" title={t.billing.packs.disabledTitle}>
          {t.billing.packs.disabledBody}
        </InlineNotice>
      );
    if (!paddleConfigured())
      return (
        <InlineNotice tone="info" title={t.billing.packs.notConfiguredTitle}>
          {t.billing.packs.notConfiguredBody}
        </InlineNotice>
      );
    if (packs.data.packs.length === 0) return <p className={styles["note"]}>{t.billing.packs.empty}</p>;
    return (
      <>
        {!me.email_verified ? (
          <InlineNotice tone="warning" title={t.billing.packs.unverifiedTitle}>
            {t.billing.packs.unverifiedBody}
          </InlineNotice>
        ) : null}
        <ul className={styles["packs"]} aria-label={t.billing.packs.list}>
          {packs.data.packs.map((pack) => (
            <PackCard
              key={pack.code}
              pack={pack}
              disabled={!me.email_verified}
              busy={checkout.isPending && checkout.variables === pack.code}
              onBuy={buy}
            />
          ))}
        </ul>
      </>
    );
  };

  const error = checkout.isError ? checkout.error : null;
  const ambiguous = error !== null && isAmbiguous(error);
  const failure = error !== null && !ambiguous ? failureOf(error) : null;

  return (
    <section className={styles["section"]} aria-labelledby="billing-packs">
      <h2 id="billing-packs">{t.billing.packs.heading}</h2>
      {body()}
      {ambiguous ? (
        <InlineNotice
          tone="warning"
          title={t.billing.checkout.unknownTitle}
          live="alert"
          actions={
            <Button
              type="button"
              onClick={() => {
                const pack = packs.data?.packs.find((p) => p.code === checkout.variables);
                if (pack !== undefined) buy(pack);
              }}
            >
              {t.billing.checkout.retry}
            </Button>
          }
        >
          {t.billing.checkout.unknownBody}
        </InlineNotice>
      ) : null}
      {failure !== null ? <ProblemNotice problem={failure} /> : null}
      {error !== null && !ambiguous && failure === null ? (
        <InlineNotice tone="danger" title={t.billing.checkout.failedTitle} live="alert" />
      ) : null}
      {creationUnknown !== null ? (
        <InlineNotice tone="warning" title={t.billing.checkout.processingTitle} live="alert">
          {t.billing.checkout.processingBody}{" "}
          {t.billing.checkout.reference({ id: shortReference(creationUnknown.id) })}
        </InlineNotice>
      ) : null}
      {openError !== null ? (
        <InlineNotice tone="warning" title={t.billing.checkout.paddleFailedTitle} live="alert">
          {t.billing.checkout.paddleFailedBody}
        </InlineNotice>
      ) : null}
      {opening !== null ? (
        <p role="status" className={styles["note"]}>
          {t.billing.checkout.opening}
        </p>
      ) : null}
    </section>
  );
}

const STATE_TONE: Record<PurchaseState, "info" | "success" | "warning" | "danger"> = {
  intent: "info",
  creating: "info",
  created: "info",
  creation_unknown: "warning",
  failed: "danger",
  paid: "info",
  granted: "success",
  review: "warning",
  refunded: "info",
};

/** A document exists once the sale was paid; before that there is nothing to fetch. */
const HAS_DOCUMENT: ReadonlySet<PurchaseState> = new Set(["paid", "granted", "refunded"]);

function PurchaseItem({ purchase }: { readonly purchase: Purchase }) {
  const invoice = useInvoice();
  const [resumeError, setResumeError] = useState(false);
  const [resuming, setResuming] = useState(false);
  const copy = t.billing.purchases.states[purchase.state];
  const reference = shortReference(purchase.id);
  const invoiceFailure = invoice.isError ? (failureOf(invoice.error) ?? null) : null;

  const resume = () => {
    if (resuming || purchase.transactionId === null) return;
    const started = sessionGeneration();
    setResuming(true);
    setResumeError(false);
    openCheckout(purchase.transactionId, successPath(purchase.id))
      .catch(() => {
        if (isCurrentSession(started)) setResumeError(true);
      })
      .finally(() => {
        if (isCurrentSession(started)) setResuming(false);
      });
  };

  const getInvoice = () => {
    if (invoice.isPending) return;
    invoice.mutate(purchase.id, {
      onSuccess: (url) => {
        window.open(url, "_blank", "noopener,noreferrer");
      },
    });
  };

  return (
    <li className={styles["purchase"]}>
      <div className={styles["purchaseHead"]}>
        <strong>
          {t.billing.purchases.item({ reports: formatReports(purchase.reports) })}
          {", "}
          {formatMoney(purchase.grossPln, { decimals: 0 })}
        </strong>
        <span className={`${styles["badge"]} ${styles[STATE_TONE[purchase.state]]}`}>{copy.label}</span>
      </div>
      <p className={styles["meta"]}>{copy.detail}</p>
      <p className={styles["meta"]}>
        {t.billing.purchases.placed({ when: formatDateTime(purchase.createdAt) })}
        {" · "}
        {t.billing.purchases.reference}: <code>{reference}</code>
      </p>
      <div className={styles["actions"]}>
        {purchase.state === "created" && purchase.transactionId !== null && paddleConfigured() ? (
          <Button
            type="button"
            variant="primary"
            small
            aria-label={t.billing.purchases.resumeLabel({ id: reference })}
            busy={resuming}
            onClick={resume}
          >
            {t.billing.purchases.resume}
          </Button>
        ) : null}
        {HAS_DOCUMENT.has(purchase.state) ? (
          <Button
            type="button"
            small
            aria-label={t.billing.purchases.invoiceLabel({ id: reference })}
            busy={invoice.isPending}
            onClick={getInvoice}
          >
            {t.billing.purchases.invoice}
          </Button>
        ) : null}
      </div>
      {resumeError ? (
        <InlineNotice tone="warning" title={t.billing.checkout.paddleFailedTitle} live="alert" />
      ) : null}
      {invoice.isError ? (
        invoiceFailure !== null ? (
          <ProblemNotice problem={invoiceFailure} />
        ) : (
          <InlineNotice tone="danger" title={t.billing.purchases.invoiceFailedTitle} live="alert" />
        )
      ) : null}
    </li>
  );
}

// LEGAL[tax-invoice]: the invoice is fetched from the provider on the buyer's request after an ownership check (RM-277)
function PurchasesSection() {
  const purchases = usePurchases();
  return (
    <section className={styles["section"]} aria-labelledby="billing-purchases">
      <h2 id="billing-purchases">{t.billing.purchases.heading}</h2>
      {purchases.isPending ? (
        <div role="status" aria-busy="true" aria-label={t.billing.purchases.loading}>
          <Skeleton height="72px" />
        </div>
      ) : purchases.isError ? (
        <InlineNotice
          tone="danger"
          title={t.billing.purchases.failed}
          live="alert"
          actions={
            <Button type="button" icon="refresh" onClick={() => void purchases.refetch()}>
              {t.common.retry}
            </Button>
          }
        />
      ) : purchases.data.length === 0 ? (
        <p className={styles["note"]}>{t.billing.purchases.empty}</p>
      ) : (
        <>
          <ul className={styles["purchases"]} aria-label={t.billing.purchases.list}>
            {purchases.data.map((purchase) => (
              <PurchaseItem key={purchase.id} purchase={purchase} />
            ))}
          </ul>
          <p className={styles["note"]}>{t.billing.purchases.invoiceNote}</p>
          <p className={styles["note"]}>{t.billing.purchases.support}</p>
        </>
      )}
    </section>
  );
}

/**
 * `/app/credits` (RM-277): the balance, the packs the server offers (prices are its gross PLN strings, never computed
 * on here), a purchase that is one intent with one idempotency key, and the list of purchases with their invoices.
 * Real checkout is only offered when the server says billing is enabled AND this build has a Paddle client token.
 */
// GDPR[processor]: the buyer's details go to Paddle in its own checkout; this page only holds the order state (RM-277)
export function CreditsPage() {
  return (
    <div className={styles["page"]}>
      <PageHeading title={t.shell.creditsPage} />
      <Balance />
      <PacksSection />
      <PurchasesSection />
    </div>
  );
}
