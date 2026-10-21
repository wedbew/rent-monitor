import { formatCount, formatDateTime, formatDecimal } from "../../api/format";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice, StoredImage } from "./common";
import { type GenerationOut, type ProjectOut, isActive, useCancelGeneration } from "./hooks";
import styles from "./interior.module.css";
import { t } from "../../i18n";

function Cost({ generation }: { readonly generation: GenerationOut }) {
  if (generation.cost_usd === null) return null;
  const amount = formatDecimal(generation.cost_usd, 4);
  return (
    <p className={styles["muted"]}>
      {(generation.cost_estimated ? t.interior.generation.costEstimated : t.interior.generation.cost)({
        amount,
      })}
    </p>
  );
}

function GenerationCard({
  project,
  generation,
  retry,
  retrying,
}: {
  readonly project: ProjectOut;
  readonly generation: GenerationOut;
  readonly retry: (revisionId: string) => void;
  readonly retrying: boolean;
}) {
  const cancel = useCancelGeneration();
  const projectId = project.project_id;
  const errors = t.interior.generation.errors as Record<string, string>;
  return (
    <li className={styles["card"]} data-generation-state={generation.state}>
      <h3 className={styles["h3"]}>
        {t.interior.generation.item({ when: formatDateTime(generation.created_at) })}
      </h3>
      <p className={styles["state"]} role="status">
        {t.interior.generation.state[generation.state]}
      </p>
      {isActive(generation.state) ? (
        <p className={styles["muted"]}>{t.interior.generation.progress}</p>
      ) : null}
      {generation.state === "queued" ? (
        <p className={styles["muted"]}>{t.interior.generation.queuedHint}</p>
      ) : null}
      {generation.state === "running" ? (
        <p className={styles["muted"]}>{t.interior.generation.runningHint}</p>
      ) : null}
      {generation.state === "failed" && generation.error_code !== null ? (
        <InlineNotice
          tone="danger"
          title={errors[generation.error_code] ?? t.interior.generation.errors.INTERNAL}
          live="alert"
        />
      ) : null}
      {generation.state === "succeeded" && generation.output !== null ? (
        <div className={styles["compare"]}>
          <figure className={styles["figure"]}>
            {project.source !== null ? (
              <StoredImage
                projectId={projectId}
                media={project.source}
                alt={t.interior.generation.beforeAlt}
              />
            ) : null}
            <figcaption>{t.interior.generation.before}</figcaption>
          </figure>
          <figure className={styles["figure"]}>
            <StoredImage
              projectId={projectId}
              media={generation.output}
              alt={t.interior.generation.afterAlt}
            />
            <figcaption>{t.interior.generation.after}</figcaption>
          </figure>
        </div>
      ) : null}
      {generation.state === "succeeded" ? (
        <p className={styles["illustration"]}>{t.interior.generation.illustration}</p>
      ) : null}
      <p className={styles["muted"]}>
        {t.interior.generation.references({
          used: formatCount(generation.references_used),
          skipped: formatCount(generation.references_skipped),
        })}
      </p>
      <Cost generation={generation} />
      <div className={styles["actions"]}>
        {generation.state === "queued" ? (
          <Button
            type="button"
            small
            busy={cancel.isPending}
            onClick={() =>
              !cancel.isPending && cancel.mutate({ projectId, generationId: generation.generation_id })
            }
          >
            {t.interior.generation.cancel}
          </Button>
        ) : null}
        {generation.state === "failed" || generation.state === "cancelled" ? (
          <Button type="button" small disabled={retrying} onClick={() => retry(generation.revision_id)}>
            {t.interior.generation.retry}
          </Button>
        ) : null}
      </div>
      {generation.state === "failed" ? (
        <p className={styles["muted"]}>{t.interior.generation.retryHint}</p>
      ) : null}
      {cancel.isSuccess ? (
        <InlineNotice tone="info" title={t.interior.generation.cancelled} live="status" />
      ) : null}
      {cancel.isError ? <FailureNotice error={cancel.error} /> : null}
    </li>
  );
}

interface Props {
  readonly project: ProjectOut;
  readonly generations: readonly GenerationOut[];
  readonly start: (revisionId: string) => void;
  readonly starting: boolean;
  readonly startError: unknown;
  readonly off: boolean;
}

/**
 * Illustrative pictures. The original photo is always shown beside the result and the result is always labelled an
 * illustration. Progress is read from the server (polled while an operation is active and stopped on a terminal
 * state), so a reload, a second tab or a lost connection never leaves a stale "running".
 */
export function GenerationsPanel({ project, generations, start, starting, startError, off }: Props) {
  const active = generations.some((g) => isActive(g.state));
  return (
    <section className={styles["panel"]} aria-labelledby="interior-generations">
      <h2 className={styles["h2"]} id="interior-generations">
        {t.interior.generation.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.generation.lead}</p>
      {off ? <InlineNotice tone="info" title={t.interior.generation.off} /> : null}
      {startError !== null ? <FailureNotice error={startError} /> : null}
      {generations.length === 0 ? (
        <p>{t.interior.generation.empty}</p>
      ) : (
        <ul className={styles["cards"]}>
          {generations.map((generation) => (
            <GenerationCard
              key={generation.generation_id}
              project={project}
              generation={generation}
              retry={start}
              retrying={starting || active}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
