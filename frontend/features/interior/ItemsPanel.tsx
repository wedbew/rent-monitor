import { type FormEvent, useId, useRef, useState } from "react";

import { formatCount } from "../../api/format";
import { Button } from "../../ui/Button";
import { TextField } from "../../ui/Field";
import { FormErrorSummary, type FieldError, useFormAttempt } from "../../ui/FormErrors";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice, moneyOrUnknown, parseMoneyInput, reasonOf, StoredImage } from "./common";
import {
  type CustomItemOut,
  type ProjectOut,
  useAddItem,
  useDeleteItem,
  useUpdateItem,
  useUploadItemPhoto,
} from "./hooks";
import styles from "./interior.module.css";
import { rejectionText } from "./PhotoPanel";
import { t } from "../../i18n";

export const MAX_ITEMS = 30; // rm_contracts.interior.MAX_ITEMS_PER_PROJECT
type Ids = { readonly name: string; readonly quantity: string; readonly price: string; readonly url: string };
const idsFor = (prefix: string): Ids => ({
  name: `${prefix}-name`,
  quantity: `${prefix}-quantity`,
  price: `${prefix}-price`,
  url: `${prefix}-url`,
});

/** Only a name is required. A price, a link and a quantity are checked for shape; the server checks again. */
export function itemErrors(
  input: { name: string; quantity: string; price: string; url: string },
  IDS: Ids,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (input.name.trim() === "") errors[IDS.name] = t.interior.items.nameMissing;
  if (
    !/^\d{1,2}$/.test(input.quantity.trim()) ||
    input.quantity.trim() === "0" ||
    input.quantity.trim() === "00"
  )
    errors[IDS.quantity] = t.interior.items.quantityInvalid;
  if (input.price.trim() !== "" && parseMoneyInput(input.price) === null)
    errors[IDS.price] = t.interior.items.priceInvalid;
  if (input.url.trim() !== "" && !/^https?:\/\/\S+$/i.test(input.url.trim()))
    errors[IDS.url] = t.interior.items.urlInvalid;
  return errors;
}

interface FormProps {
  readonly initial: { name: string; quantity: number; price: string | null; url: string | null } | null;
  readonly busy: boolean;
  readonly failure: unknown;
  readonly submitLabel: string;
  readonly onCancel?: () => void;
  readonly onSubmit: (item: { name: string; quantity: number; price_pln?: string; url?: string }) => void;
}

function ItemForm({ initial, busy, failure, submitLabel, onCancel, onSubmit }: FormProps) {
  const IDS = idsFor(useId());
  const [name, setName] = useState(initial?.name ?? "");
  const [quantity, setQuantity] = useState(String(initial?.quantity ?? 1));
  const [price, setPrice] = useState(initial?.price?.replace(".", ",").replace(/,00$/, "") ?? "");
  const [url, setUrl] = useState(initial?.url ?? "");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [attempt, markInvalid] = useFormAttempt();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const found = itemErrors({ name, quantity, price, url }, IDS);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      markInvalid();
      return;
    }
    const priceText = parseMoneyInput(price);
    onSubmit({
      name: name.trim(),
      quantity: Number.parseInt(quantity.trim(), 10),
      ...(priceText === null ? {} : { price_pln: priceText }),
      ...(url.trim() === "" ? {} : { url: url.trim() }),
    });
  }

  const summary: FieldError[] = Object.entries(errors).map(([fieldId, message]) => ({ fieldId, message }));
  return (
    <form className={styles["form"]} onSubmit={submit} noValidate>
      <FormErrorSummary errors={summary} attempt={attempt} />
      <TextField
        fieldId={IDS.name}
        label={t.interior.items.name}
        value={name}
        onValueChange={setName}
        error={errors[IDS.name]}
        maxLength={120}
        autoComplete="off"
      />
      <TextField
        fieldId={IDS.quantity}
        label={t.interior.items.quantity}
        value={quantity}
        onValueChange={setQuantity}
        error={errors[IDS.quantity]}
        inputMode="numeric"
        autoComplete="off"
      />
      <TextField
        fieldId={IDS.price}
        label={t.interior.items.price}
        hint={t.interior.items.priceHint}
        value={price}
        onValueChange={setPrice}
        error={errors[IDS.price]}
        inputMode="decimal"
        autoComplete="off"
      />
      <TextField
        fieldId={IDS.url}
        label={t.interior.items.url}
        hint={t.interior.items.urlHint}
        value={url}
        onValueChange={setUrl}
        error={errors[IDS.url]}
        inputMode="url"
        autoComplete="off"
      />
      {failure !== null ? <FailureNotice error={failure} /> : null}
      <div className={styles["actions"]}>
        <Button type="submit" variant="primary" busy={busy}>
          {submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" onClick={onCancel}>
            {t.interior.items.cancel}
          </Button>
        ) : null}
      </div>
    </form>
  );
}

function ItemRow({ project, item }: { readonly project: ProjectOut; readonly item: CustomItemOut }) {
  const [editing, setEditing] = useState(false);
  const update = useUpdateItem();
  const remove = useDeleteItem();
  const photo = useUploadItemPhoto();
  const input = useRef<HTMLInputElement>(null);
  const rejected = photo.isError ? reasonOf(photo.error) : null;
  const projectId = project.project_id;

  if (editing) {
    return (
      <li className={styles["card"]}>
        <ItemForm
          initial={{ name: item.name, quantity: item.quantity, price: item.price_pln, url: item.url }}
          busy={update.isPending}
          failure={update.isError ? update.error : null}
          submitLabel={t.interior.items.save}
          onCancel={() => setEditing(false)}
          onSubmit={(next) =>
            update.mutate(
              { projectId, itemId: item.item_id, item: next },
              { onSuccess: () => setEditing(false) },
            )
          }
        />
      </li>
    );
  }
  return (
    <li className={styles["card"]}>
      <div className={styles["row"]}>
        {item.photo !== null ? (
          <div className={styles["thumb"]}>
            <StoredImage
              projectId={projectId}
              media={item.photo}
              alt={t.interior.items.photoAlt({ name: item.name })}
            />
          </div>
        ) : null}
        <div className={styles["grow"]}>
          <h3 className={styles["h3"]}>{item.name}</h3>
          <ul className={styles["facts"]}>
            <li>{t.interior.items.quantityLine({ count: formatCount(item.quantity) })}</li>
            <li>{moneyOrUnknown(item.price_pln, t.interior.items.priceUnknown)}</li>
            <li>{t.interior.items.userAdded}</li>
          </ul>
          {item.url !== null ? (
            <a
              className={styles["link"]}
              href={item.url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              aria-label={t.interior.items.linkOpen({ name: item.name })}
            >
              {t.interior.offer.link}
            </a>
          ) : null}
        </div>
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        data-testid={`interior-item-photo-${item.item_id}`}
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (file !== undefined && !photo.isPending) photo.mutate({ projectId, itemId: item.item_id, file });
        }}
      />
      <div className={styles["actions"]}>
        <Button
          type="button"
          small
          busy={photo.isPending}
          aria-label={t.interior.items.photoChoose({ name: item.name })}
          onClick={() => input.current?.click()}
        >
          {photo.isPending ? t.interior.items.photoUploading : t.interior.items.photoShort}
        </Button>
        <Button
          type="button"
          small
          aria-label={t.interior.items.edit({ name: item.name })}
          onClick={() => setEditing(true)}
        >
          {t.interior.items.editShort}
        </Button>
        <Button
          type="button"
          small
          variant="danger"
          busy={remove.isPending}
          aria-label={t.interior.items.remove({ name: item.name })}
          onClick={() => !remove.isPending && remove.mutate({ projectId, itemId: item.item_id })}
        >
          {t.interior.items.removeShort}
        </Button>
      </div>
      {rejected !== null ? (
        <InlineNotice tone="danger" title={rejectionText(rejected)} live="alert" />
      ) : photo.isError ? (
        <FailureNotice error={photo.error} />
      ) : null}
      {remove.isError ? <FailureNotice error={remove.error} /> : null}
    </li>
  );
}

/**
 * The person's own items: only a name is required. A missing price is shown as unknown and stays out of the sum, it
 * is never counted as 0 zł. Every item carries the label "added by you, unverified": nothing here is a quote.
 */
export function ItemsPanel({ project }: { readonly project: ProjectOut }) {
  const add = useAddItem();
  const [formKey, setFormKey] = useState(0);
  const full = project.items.length >= MAX_ITEMS;
  return (
    <section className={styles["panel"]} aria-labelledby="interior-items">
      <h2 className={styles["h2"]} id="interior-items">
        {t.interior.items.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.items.lead}</p>
      <p className={styles["muted"]}>
        {t.interior.items.count({ used: formatCount(project.items.length), max: formatCount(MAX_ITEMS) })}
      </p>
      {project.items.length === 0 ? (
        <p>{t.interior.items.empty}</p>
      ) : (
        <ul className={styles["cards"]}>
          {project.items.map((item) => (
            <ItemRow key={item.item_id} project={project} item={item} />
          ))}
        </ul>
      )}
      {!full ? (
        <div className={styles["card"]}>
          <ItemForm
            key={formKey}
            initial={null}
            busy={add.isPending}
            failure={add.isError ? add.error : null}
            submitLabel={t.interior.items.add}
            onSubmit={(item) =>
              add.mutate(
                { projectId: project.project_id, item },
                { onSuccess: () => setFormKey((k) => k + 1) },
              )
            }
          />
        </div>
      ) : null}
    </section>
  );
}
