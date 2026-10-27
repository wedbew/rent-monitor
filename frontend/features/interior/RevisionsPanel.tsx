import { useRef } from "react";

import { formatCount, formatDateTime } from "../../api/format";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice } from "./common";
import { type ProjectOut, useSaveRevision } from "./hooks";
import styles from "./interior.module.css";
import { BasketSummary } from "./BoardPanel";
import { OfferBody } from "./OfferCard";
import { t } from "../../i18n";

interface Props {
  readonly project: ProjectOut;
  readonly generate: (revisionId: string) => void;
  readonly generating: boolean;
  readonly generationOff: boolean;
  readonly draftDirty?: boolean;
}

/**
 * Immutable versions. Saving one first checks every picked offer again at the source and records what it saw, so the
 * version keeps the prices and states of that moment whatever the shops do later.
 */
export function RevisionsPanel({ project, generate, generating, generationOff, draftDirty = false }: Props) {
  const save = useSaveRevision();
  const done = useRef(false);
  return (
    <section className={styles["panel"]} aria-labelledby="interior-revisions">
      <h2 className={styles["h2"]} id="interior-revisions">
        {t.interior.revisions.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.revisions.lead}</p>
      <div className={styles["actions"]}>
        <Button
          type="button"
          variant="primary"
          busy={save.isPending}
          disabled={draftDirty}
          onClick={() => {
            if (save.isPending) return;
            done.current = false;
            save.mutate({ projectId: project.project_id }, { onSuccess: () => (done.current = true) });
          }}
        >
          {save.isPending ? t.interior.revisions.saving : t.interior.revisions.save}
        </Button>
      </div>
      {save.isSuccess ? (
        <InlineNotice tone="success" title={t.interior.revisions.saved} live="status" />
      ) : null}
      {save.isError ? <FailureNotice error={save.error} /> : null}
      {project.revisions.length === 0 ? (
        <p>{t.interior.revisions.empty}</p>
      ) : (
        <ol className={styles["cards"]} reversed>
          {project.revisions.map((revision) => {
            const number = formatCount(revision.number);
            const hasPhoto = revision.source_digest !== null;
            return (
              <li key={revision.revision_id} className={styles["card"]}>
                <h3 className={styles["h3"]}>{t.interior.revisions.item({ number })}</h3>
                <p className={styles["muted"]}>
                  {t.interior.revisions.created({ when: formatDateTime(revision.created_at) })}
                </p>
                <p>
                  {t.interior.revisions.contents({
                    items: formatCount(revision.items.length),
                    products: formatCount((revision.selections ?? []).length),
                  })}
                  {hasPhoto ? "" : ` · ${t.interior.revisions.noPhoto}`}
                </p>
                {(revision.selections ?? []).length > 0 ? (
                  <div className={styles["stack"]}>
                    <h4 className={styles["h4"]}>{t.interior.revisions.offersAtSave}</h4>
                    <ul className={styles["cards"]}>
                      {(revision.selections ?? []).map((selection) => (
                        <li
                          key={`${selection.offer.product_id}/${selection.offer.variant_id}`}
                          className={styles["card"]}
                        >
                          <OfferBody offer={selection.offer} demo={selection.offer.provider === "demo"} />
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <BasketSummary basket={revision.basket} budget={revision.brief.budget_pln ?? null} />
                <div className={styles["actions"]}>
                  <Button
                    type="button"
                    small
                    disabled={!hasPhoto || generating || generationOff}
                    aria-label={t.interior.revisions.generate({ number })}
                    onClick={() => generate(revision.revision_id)}
                  >
                    {t.interior.revisions.generateShort}
                  </Button>
                </div>
                {!hasPhoto ? <p className={styles["muted"]}>{t.interior.revisions.needPhoto}</p> : null}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
