import { formatCount, formatMoney } from "../../api/format";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice } from "./common";
import {
  type ProjectOut,
  type SelectionOut,
  useCatalogueStatus,
  useRefreshSelection,
  useRemoveSelection,
  useSetQuantity,
} from "./hooks";
import styles from "./interior.module.css";
import { OfferBody, stateTone } from "./OfferCard";
import { t } from "../../i18n";

/** The server's own sums over the person's items and picked offers. Nothing is added up in the browser. */
export function BasketSummary({
  basket,
  budget,
}: {
  readonly basket: ProjectOut["basket"];
  readonly budget: string | null | undefined;
}) {
  return (
    <div className={styles["basket"]} role="group" aria-label={t.interior.basket.title}>
      <h3 className={styles["h3"]}>{t.interior.basket.title}</h3>
      <ul className={styles["facts"]}>
        <li>
          <strong>{t.interior.basket.subtotal({ amount: formatMoney(basket.known_subtotal_pln) })}</strong>
        </li>
        <li>{t.interior.basket.priced({ count: formatCount(basket.priced_lines) })}</li>
        {basket.unpriced_lines > 0 ? (
          <li>{t.interior.basket.unpriced({ count: formatCount(basket.unpriced_lines) })}</li>
        ) : null}
        {basket.stale_lines > 0 ? (
          <li>{t.interior.basket.stale({ count: formatCount(basket.stale_lines) })}</li>
        ) : null}
        <li>{t.interior.basket.delivery({ amount: formatMoney(basket.delivery_known_pln) })}</li>
        {basket.delivery_unknown_lines > 0 ? (
          <li>{t.interior.basket.deliveryUnknown({ count: formatCount(basket.delivery_unknown_lines) })}</li>
        ) : null}
        {budget !== null && budget !== undefined ? (
          <li>{t.interior.basket.budget({ amount: formatMoney(budget) })}</li>
        ) : null}
      </ul>
      <p className={styles["muted"]}>
        {basket.complete ? t.interior.basket.complete : t.interior.basket.incomplete}
      </p>
    </div>
  );
}

function SelectionCard({
  projectId,
  selection,
  demo,
}: {
  readonly projectId: string;
  readonly selection: SelectionOut;
  readonly demo: boolean;
}) {
  const quantity = useSetQuantity();
  const remove = useRemoveSelection();
  const refresh = useRefreshSelection();
  const { offer } = selection;
  const label = offer.title;
  const set = (next: number) =>
    !quantity.isPending &&
    next >= 1 &&
    next <= 99 &&
    quantity.mutate({ projectId, selectionId: selection.selection_id, quantity: next });
  return (
    <li className={styles["card"]} data-offer-state={stateTone(offer.state)}>
      <OfferBody offer={offer} demo={demo} />
      <p className={`${styles["state"]} ${styles[stateTone(offer.state)] ?? ""}`}>
        {t.interior.offer.state[offer.state]}
      </p>
      {offer.state === "expired" ? <p className={styles["muted"]}>{t.interior.board.staleHint}</p> : null}
      {offer.state === "unavailable" ? (
        <p className={styles["muted"]}>{t.interior.board.unavailableHint}</p>
      ) : null}
      <p>
        <strong>
          {selection.line_total_pln === null
            ? t.interior.board.lineTotalNone
            : t.interior.board.lineTotal({ amount: formatMoney(selection.line_total_pln) })}
        </strong>
      </p>
      <div className={styles["actions"]}>
        <Button
          type="button"
          small
          aria-label={t.interior.board.decrease({ title: label })}
          disabled={selection.quantity <= 1}
          onClick={() => set(selection.quantity - 1)}
        >
          {t.interior.board.decreaseShort}
        </Button>
        <span aria-live="polite" aria-label={t.interior.board.quantity({ title: label })}>
          {formatCount(selection.quantity)}
        </span>
        <Button
          type="button"
          small
          aria-label={t.interior.board.increase({ title: label })}
          disabled={selection.quantity >= 99}
          onClick={() => set(selection.quantity + 1)}
        >
          {t.interior.board.increaseShort}
        </Button>
        <Button
          type="button"
          small
          busy={refresh.isPending}
          aria-label={t.interior.board.refresh({ title: label })}
          onClick={() =>
            !refresh.isPending && refresh.mutate({ projectId, selectionId: selection.selection_id })
          }
        >
          {t.interior.board.refreshShort}
        </Button>
        <Button
          type="button"
          small
          variant="danger"
          busy={remove.isPending}
          aria-label={t.interior.board.remove({ title: label })}
          onClick={() =>
            !remove.isPending && remove.mutate({ projectId, selectionId: selection.selection_id })
          }
        >
          {t.interior.board.removeShort}
        </Button>
      </div>
      {refresh.isSuccess ? (
        <InlineNotice tone="success" title={t.interior.board.refreshed} live="status" />
      ) : null}
      {refresh.isError ? <FailureNotice error={refresh.error} /> : null}
      {quantity.isError ? <FailureNotice error={quantity.error} /> : null}
      {remove.isError ? <FailureNotice error={remove.error} /> : null}
    </li>
  );
}

/**
 * The product board: the exact variants the person picked, each with its photo, price, state and the time it was
 * checked. It is the dependable record of the selection; a generated picture only illustrates it.
 */
export function BoardPanel({ project }: { readonly project: ProjectOut }) {
  const status = useCatalogueStatus();
  const demo = status.data?.is_demo === true;
  return (
    <section className={styles["panel"]} aria-labelledby="interior-board">
      <h2 className={styles["h2"]} id="interior-board">
        {t.interior.board.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.board.lead}</p>
      {(project.selections ?? []).length === 0 ? (
        <p>{t.interior.board.empty}</p>
      ) : (
        <ul className={styles["cards"]}>
          {(project.selections ?? []).map((selection) => (
            <SelectionCard
              key={selection.selection_id}
              projectId={project.project_id}
              selection={selection}
              demo={demo}
            />
          ))}
        </ul>
      )}
      <BasketSummary basket={project.basket} budget={project.brief.budget_pln ?? null} />
    </section>
  );
}
