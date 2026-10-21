import { type FormEvent, useState } from "react";

import { InlineNotice } from "../../ui/Status";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { Skeleton } from "../../ui/Skeleton";
import { FailureNotice, parseMoneyInput } from "./common";
import {
  type ProjectOut,
  type SearchParams,
  useCatalogueSearch,
  useCatalogueStatus,
  useSelectProduct,
} from "./hooks";
import styles from "./interior.module.css";
import { OfferBody } from "./OfferCard";
import { t } from "../../i18n";

const CATEGORIES = Object.keys(
  t.interior.catalogue.categories,
) as (keyof typeof t.interior.catalogue.categories)[];

/**
 * Real offers from the connected source, found by the server and shown as it returned them. Choosing a variant asks
 * the server to fetch that exact offer itself: the browser never sends a price. With no source connected there is
 * nothing to search, and the panel says so instead of inventing products.
 */
// LEGAL[third-party-data]: shows merchant product data to the signed-in person who searched (RM-451)
// LEGAL[republication]: product titles, prices and photos come from the source's licence (RM-451)
export function CataloguePanel({ project }: { readonly project: ProjectOut }) {
  const status = useCatalogueStatus();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [priceError, setPriceError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<SearchParams | null>(null);
  const search = useCatalogueSearch(project.project_id, submitted);
  const pick = useSelectProduct();
  const picked = new Set(
    (project.selections ?? []).map((s) => `${s.offer.provider}/${s.offer.product_id}/${s.offer.variant_id}`),
  );

  function run(event: FormEvent) {
    event.preventDefault();
    if (maxPrice.trim() !== "" && parseMoneyInput(maxPrice) === null) {
      setPriceError(t.interior.catalogue.maxPriceInvalid);
      return;
    }
    setPriceError(null);
    setSubmitted({ q: q.trim(), category, maxPrice: parseMoneyInput(maxPrice) ?? "" });
  }

  const demo = status.data?.is_demo === true;
  const connected = status.data?.available === true;
  return (
    <section className={styles["panel"]} aria-labelledby="interior-catalogue">
      <h2 className={styles["h2"]} id="interior-catalogue">
        {t.interior.catalogue.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.catalogue.lead}</p>
      {status.isPending ? (
        <Skeleton height="3rem" />
      ) : status.isError ? (
        <FailureNotice error={status.error} />
      ) : !connected ? (
        <InlineNotice tone="info" title={t.interior.catalogue.notConnectedTitle}>
          {t.interior.catalogue.notConnectedBody}
        </InlineNotice>
      ) : (
        <>
          <p className={styles["source"]}>
            {(demo ? t.interior.catalogue.sourceDemo : t.interior.catalogue.sourceLive)({
              label: status.data.source_label ?? "",
            })}
          </p>
          {demo ? <InlineNotice tone="warning" title={t.interior.catalogue.demoWarning} /> : null}
          <form className={styles["form"]} onSubmit={run} noValidate>
            <TextField
              label={t.interior.catalogue.query}
              hint={t.interior.catalogue.queryHint}
              value={q}
              onValueChange={setQ}
              maxLength={120}
              autoComplete="off"
            />
            <Select
              label={t.interior.catalogue.category}
              value={category}
              options={[
                { value: "", label: t.interior.catalogue.categoryAny },
                ...CATEGORIES.map((value) => ({ value, label: t.interior.catalogue.categories[value] })),
              ]}
              onValueChange={setCategory}
            />
            <TextField
              label={t.interior.catalogue.maxPrice}
              value={maxPrice}
              onValueChange={setMaxPrice}
              error={priceError}
              inputMode="decimal"
              autoComplete="off"
            />
            <div className={styles["actions"]}>
              <Button type="submit" variant="primary" busy={search.isFetching}>
                {t.interior.catalogue.search}
              </Button>
            </div>
          </form>
          {search.isError ? (
            <FailureNotice error={search.error} onReload={() => void search.refetch()} />
          ) : null}
          {pick.isError ? <FailureNotice error={pick.error} /> : null}
          {search.data !== undefined ? (
            search.data.length === 0 ? (
              <p>{t.interior.catalogue.noResults}</p>
            ) : (
              <ul className={styles["cards"]} aria-label={t.interior.catalogue.resultsLabel}>
                {search.data.map((candidate) => {
                  const { offer } = candidate;
                  const key = `${offer.provider}/${offer.product_id}/${offer.variant_id}`;
                  return (
                    <li key={key} className={styles["card"]}>
                      <OfferBody offer={offer} demo={demo} />
                      <ul className={styles["flags"]}>
                        {(candidate.flags ?? []).map((flag) => (
                          <li key={flag}>
                            {(t.interior.catalogue.flags as Record<string, string>)[flag] ?? flag}
                          </li>
                        ))}
                      </ul>
                      <div className={styles["actions"]}>
                        <Button
                          type="button"
                          variant="primary"
                          small
                          busy={
                            pick.isPending &&
                            pick.variables?.variantId === offer.variant_id &&
                            pick.variables.productId === offer.product_id
                          }
                          disabled={picked.has(key)}
                          aria-label={t.interior.catalogue.pick({
                            title: `${offer.title} (${Object.values(offer.attributes).join(", ")})`,
                          })}
                          onClick={() =>
                            !pick.isPending &&
                            pick.mutate({
                              projectId: project.project_id,
                              provider: offer.provider,
                              productId: offer.product_id,
                              variantId: offer.variant_id,
                              quantity: 1,
                            })
                          }
                        >
                          {picked.has(key) ? t.interior.catalogue.picked : t.interior.catalogue.pickShort}
                        </Button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )
          ) : null}
        </>
      )}
    </section>
  );
}
