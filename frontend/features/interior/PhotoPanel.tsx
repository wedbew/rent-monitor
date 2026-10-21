import { useRef, useState } from "react";

import { formatCount } from "../../api/format";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { FailureNotice, reasonOf, StoredImage } from "./common";
import { type ProjectOut, useUploadSource } from "./hooks";
import styles from "./interior.module.css";
import { t } from "../../i18n";

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // rm_core.interior_images.MAX_UPLOAD_BYTES

/** The words for an upload the server refused, by its stable `reason`. */
export function rejectionText(reason: string | null): string {
  const known = t.interior.photo.rejected as Record<string, string>;
  return (reason !== null ? known[reason] : undefined) ?? t.interior.photo.rejected.unknown;
}

/**
 * The room photo. The browser sends the chosen file as it is; the server checks it, strips location data, bounds its
 * size and keeps its own normalised copy, so a refused file is the server's decision and is shown with its reason.
 * Earlier photos stay beside a new one (a project keeps up to five), because saved versions refer to them.
 */
// LEGAL[images]: uploads the person's room photo to the API, which stores a normalised copy (RM-451)
export function PhotoPanel({ project }: { readonly project: ProjectOut }) {
  const upload = useUploadSource();
  const input = useRef<HTMLInputElement>(null);
  const [tooLarge, setTooLarge] = useState(false);

  function chosen(file: File | undefined) {
    if (file === undefined || upload.isPending) return;
    const big = file.size > MAX_UPLOAD_BYTES;
    setTooLarge(big);
    if (big) {
      upload.reset();
      return;
    }
    upload.mutate({ projectId: project.project_id, file });
  }

  const rejected = upload.isError && reasonOf(upload.error) !== null ? reasonOf(upload.error) : null;
  return (
    <section className={styles["panel"]} aria-labelledby="interior-photo">
      <h2 className={styles["h2"]} id="interior-photo">
        {t.interior.photo.title}
      </h2>
      <p className={styles["muted"]}>{t.interior.photo.lead}</p>
      {project.source !== null ? (
        <figure className={styles["figure"]}>
          <StoredImage projectId={project.project_id} media={project.source} alt={t.interior.photo.alt} />
          <figcaption className={styles["muted"]}>
            {t.interior.photo.original}
            {project.source.width !== null && project.source.height !== null
              ? `, ${t.interior.photo.size({ width: formatCount(project.source.width), height: formatCount(project.source.height) })}`
              : ""}
          </figcaption>
        </figure>
      ) : (
        <p>{t.interior.photo.none}</p>
      )}
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        hidden
        data-testid="interior-source-input"
        onChange={(event) => {
          chosen(event.target.files?.[0]);
          event.target.value = ""; // the same file can be chosen again after a failure
        }}
      />
      <div className={styles["actions"]}>
        <Button
          type="button"
          variant="primary"
          busy={upload.isPending}
          onClick={() => input.current?.click()}
        >
          {upload.isPending ? t.interior.photo.uploading : t.interior.photo.choose}
        </Button>
      </div>
      <p className={styles["muted"]}>{t.interior.photo.chooseHint}</p>
      {project.source !== null ? <p className={styles["muted"]}>{t.interior.photo.replaceNote}</p> : null}
      {tooLarge && !upload.isPending ? (
        <InlineNotice tone="danger" title={t.interior.photo.rejected.too_large} live="alert" />
      ) : null}
      {rejected !== null ? (
        <InlineNotice tone="danger" title={rejectionText(rejected)} live="alert" />
      ) : upload.isError ? (
        <FailureNotice error={upload.error} />
      ) : null}
    </section>
  );
}
