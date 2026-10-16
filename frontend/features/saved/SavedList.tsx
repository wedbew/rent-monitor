import { Link } from "react-router";

import { formatCount, formatDate } from "../../api/format";
import { Button } from "../../ui/Button";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { useSavedState } from "./useSaved";
import styles from "./saved.module.css";
import { t } from "../../i18n";

/**
 * The saved listings (`GET /api/saved`, newest first), each with its private note and a link to the person's newest
 * analysis of it. This is the server's list, not a filter of the loaded analyses.
 */
// GDPR[personal-data]: shows the person's own free-text notes (RM-276)
// LEGAL[republication]: shows listing identifiers from the tenant's own analyses (RM-276)
export function SavedList() {
  const state = useSavedState();
  if (state.status === "loading")
    return (
      <div role="status" aria-busy="true" aria-label={t.saved.list.loading}>
        <Skeleton height="72px" />
      </div>
    );
  if (state.status === "error")
    return (
      <InlineNotice
        tone="danger"
        title={t.saved.list.failed}
        live="alert"
        actions={
          <Button type="button" variant="primary" icon="refresh" onClick={state.retry}>
            {t.common.retry}
          </Button>
        }
      />
    );
  if (state.items.length === 0)
    return (
      <div className={styles["empty"]}>
        <strong>{t.saved.list.emptyTitle}</strong>
        <p>{t.saved.list.emptyBody}</p>
      </div>
    );
  return (
    <div className={styles["savedList"]}>
      <span role="status" className={styles["count"]}>
        {t.saved.list.shown({ count: formatCount(state.items.length) })}
      </span>
      {state.truncated ? (
        <InlineNotice
          tone="info"
          title={t.saved.list.truncated({ count: formatCount(state.items.length) })}
        />
      ) : null}
      <ul className={styles["items"]} aria-label={t.saved.list.label}>
        {state.items.map((item) => (
          <li key={item.otodomId} className={styles["item"]}>
            <strong>{t.common.listingTitle({ id: item.otodomId })}</strong>
            <span className={styles["meta"]}>
              {t.saved.list.savedOn({ when: formatDate(item.createdAt) })}
            </span>
            <p className={item.note ? styles["noteText"] : styles["meta"]}>
              {item.note !== null && item.note !== "" ? item.note : t.saved.list.noNote}
            </p>
            {item.latestAuditId !== null ? (
              <Link to={`/app/analyses/${item.latestAuditId}`}>
                {t.saved.list.open}
                <span className="sr-only"> {t.common.listingTitle({ id: item.otodomId })}</span>
              </Link>
            ) : (
              <span className={styles["meta"]}>{t.saved.list.noAnalysis}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
