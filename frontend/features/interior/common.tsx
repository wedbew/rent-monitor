import { useState } from "react";

import { ApiError, isAmbiguousFailure } from "../../api/errors";
import { formatMoney } from "../../api/format";
import { describeProblem, describeTransport } from "../../api/problems";
import { Button } from "../../ui/Button";
import { InlineNotice } from "../../ui/Status";
import { ProblemNotice } from "../auth/ProblemNotice";
import { mediaUrl, type MediaRef } from "./hooks";
import styles from "./interior.module.css";
import { t } from "../../i18n";

/** The `reason` some problems add (IMAGE_REJECTED, INTERIOR_LIMIT_REACHED, GENERATION_CONFLICT): a string or nothing. */
export function reasonOf(error: unknown): string | null {
  if (!(error instanceof ApiError) || error.problem === null) return null;
  const reason = (error.problem as unknown as Record<string, unknown>)["reason"];
  return typeof reason === "string" ? reason : null;
}

/** The decimal string in złoty, or the words for "unknown": an absent price is never shown as zero. */
export const moneyOrUnknown = (value: string | null | undefined, unknown: string): string =>
  value === null || value === undefined ? unknown : formatMoney(value);

/**
 * A failed write in words. An ambiguous failure (dropped connection, timeout, server error after starting) is
 * "unknown", never "failed": the person is told to reload and look before trying again (rules/frontend.md section 4).
 */
export function FailureNotice({
  error,
  onReload,
}: {
  readonly error: unknown;
  readonly onReload?: () => void;
}) {
  if (
    isAmbiguousFailure(error) &&
    !(error instanceof ApiError && error.code === "MEDIA_STORAGE_UNAVAILABLE")
  ) {
    return (
      <InlineNotice
        tone="warning"
        title={t.interior.unknownTitle}
        live="alert"
        {...(onReload
          ? {
              actions: (
                <Button type="button" small onClick={onReload}>
                  {t.interior.reload}
                </Button>
              ),
            }
          : {})}
      >
        {t.interior.unknownBody}
      </InlineNotice>
    );
  }
  if (error instanceof ApiError && error.problem !== null) {
    return (
      <ProblemNotice
        problem={describeProblem(error.problem.code, {
          requestId: error.requestId,
          retryAfterS: error.retryAfterS,
        })}
      />
    );
  }
  return <ProblemNotice problem={describeTransport("invalid-response")} />;
}

/** A stored image, delivered by the authenticated route. A failed load shows words, not a broken picture. */
export function StoredImage({
  projectId,
  media,
  alt,
}: {
  readonly projectId: string;
  readonly media: MediaRef;
  readonly alt: string;
}) {
  const [failed, setFailed] = useState(false);
  if (failed) return <p className={styles["imageFailed"]}>{t.interior.photo.previewFailed}</p>;
  return (
    <img
      className={styles["image"]}
      src={mediaUrl(projectId, media.media_id)}
      alt={alt}
      width={media.width ?? undefined}
      height={media.height ?? undefined}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

/** A product photo: only a same-origin path or an https address is ever used as an image source. */
export function safeImageSrc(url: string | null): string | null {
  if (url === null) return null;
  if (url.startsWith("/") && !url.startsWith("//")) return url;
  return url.startsWith("https://") ? url : null;
}

export function ProductImage({ url, alt }: { readonly url: string | null; readonly alt: string }) {
  const [failed, setFailed] = useState(false);
  const src = safeImageSrc(url);
  if (src === null || failed) return <div className={styles["noImage"]}>{t.interior.offer.noImage}</div>;
  return (
    <img
      className={styles["productImage"]}
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}

export function ClosedBeta() {
  return (
    <InlineNotice tone="info" title={t.interior.closed.title}>
      {t.interior.closed.body}
    </InlineNotice>
  );
}

/** A decimal in złoty typed by a person ("199", "199,99"): to the API's dot form, or null when it is not one. */
export function parseMoneyInput(raw: string): string | null {
  const value = raw.trim().replace(",", ".");
  return /^\d{1,8}(\.\d{1,2})?$/.test(value) ? value : null;
}
