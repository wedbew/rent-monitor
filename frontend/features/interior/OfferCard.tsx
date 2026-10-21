import { formatDateTime, formatDecimal, formatMoney } from "../../api/format";
import type { OfferOut } from "./hooks";
import { ProductImage } from "./common";
import styles from "./interior.module.css";
import { t } from "../../i18n";

export function stateTone(state: OfferOut["state"]): string {
  return state === "fresh" ? "fresh" : state === "expired" ? "expired" : "unavailable";
}

/** Price, delivery and stock exactly as the source gave them. An unknown value is said to be unknown, never zero. */
export function OfferFacts({ offer }: { readonly offer: OfferOut }) {
  const price = offer.price_pln === null ? t.interior.offer.priceUnknown : formatMoney(offer.price_pln);
  const delivery =
    !offer.delivery_known || offer.delivery_pln === null
      ? t.interior.offer.deliveryUnknown
      : offer.delivery_pln === "0.00"
        ? t.interior.offer.deliveryFree
        : t.interior.offer.delivery({ amount: formatMoney(offer.delivery_pln) });
  const dims = offer.dimensions;
  return (
    <ul className={styles["facts"]}>
      <li>
        <strong>{price}</strong>
        {offer.price_pln !== null && offer.price_is_gross === true ? ` ${t.interior.offer.gross}` : ""}
      </li>
      {offer.price_conditions !== null ? (
        <li>{t.interior.offer.conditions({ text: offer.price_conditions })}</li>
      ) : null}
      <li>{delivery}</li>
      <li>{t.interior.offer.availability[offer.availability]}</li>
      <li>{t.interior.offer.seller({ name: offer.seller })}</li>
      {dims !== null && dims !== undefined && dims.width_cm && dims.depth_cm && dims.height_cm ? (
        <li>
          {t.interior.offer.dimensions({
            width: formatDecimal(dims.width_cm, 1),
            depth: formatDecimal(dims.depth_cm, 1),
            height: formatDecimal(dims.height_cm, 1),
          })}{" "}
          {t.interior.offer.dimensionsSource({ source: dims.source })}
        </li>
      ) : null}
      <li>{t.interior.offer.observed({ when: formatDateTime(offer.observed_at) })}</li>
      <li>{t.interior.offer.expires({ when: formatDateTime(offer.expires_at) })}</li>
    </ul>
  );
}

/** One offer: photo, title, the exact variant (colour, size, material), facts and the way to the shop's own page. */
export function OfferBody({ offer, demo }: { readonly offer: OfferOut; readonly demo: boolean }) {
  return (
    <div className={styles["offer"]}>
      <ProductImage
        url={offer.image_url}
        alt={(demo ? t.interior.offer.demoImageAlt : t.interior.offer.imageAlt)({ title: offer.title })}
      />
      <div className={styles["grow"]}>
        <h3 className={styles["h3"]}>{offer.title}</h3>
        <p className={styles["muted"]}>
          {Object.entries(offer.attributes)
            .map(([key, value]) => `${key}: ${value}`)
            .join(", ")}
        </p>
        <OfferFacts offer={offer} />
        <a
          className={styles["link"]}
          href={offer.product_url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          aria-label={t.interior.offer.linkLabel({ title: offer.title })}
        >
          {t.interior.offer.link}
        </a>
        <p className={styles["muted"]}>{t.interior.offer.notQuote}</p>
      </div>
    </div>
  );
}
