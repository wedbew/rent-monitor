import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";

import { ApiError, TransportError } from "../../api/errors";
import { describeProblem, describeTransport, isProblemCode } from "../../api/problems";
import { t } from "../../i18n";
import { PageHeading } from "../../shell/PageHeading";
import { refreshAccount } from "../../shell/session";
import { Button, LinkButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { useAudit } from "./queries";
import { stageLabel } from "./progress/frames";
import type { Connection } from "./progress/streams";
import { formatPercent } from "../../api/format";
import { parseReport } from "../../api/report";
import { ReportView } from "./report/ReportView";
import { useAuditProgress } from "./progress/useAuditProgress";
import { hasReport, isActive, statusCopy } from "./status";
import styles from "./AnalysisPage.module.css";

export const RECONNECT_GRACE_MS = 8000;

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** What happened to the report credit, in the server's own terms (`charge_state`), never inferred from the status. */
const CHARGE = t.analyses.page.charge;

/**
 * One analysis. While it runs: the server's stages and percentage over a live stream (with a polling fallback);
 * when it ends: the final status, the credit outcome and, for a success, the way to the report. Whatever the
 * stream said, the final state is read again from the API.
 */
export function AnalysisPage() {
  const { auditId = "" } = useParams();
  if (!ID.test(auditId)) {
    return (
      <div className={styles["page"]}>
        <PageHeading title={t.analyses.page.title} />
        <InlineNotice tone="warning" title={t.analyses.page.notFoundTitle}>
          {t.analyses.page.badAddress}
        </InlineNotice>
        <LinkButton to="/app/analyses" icon="arrow">
          {t.shell.destinations.analyses}
        </LinkButton>
      </div>
    );
  }
  return <Analysis key={auditId} auditId={auditId} />;
}

function Analysis({ auditId }: { readonly auditId: string }) {
  const client = useQueryClient();
  const [streamFailed, setStreamFailed] = useState(false);
  const grace = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audit = useAudit(auditId, { fast: streamFailed });
  const active = audit.data !== undefined && isActive(audit.data.status);
  // A stream the browser cannot (re)establish is replaced by polling: at once when it gave up, after a grace
  // period while it is still retrying (a short drop heals by itself and must not start a poll).
  const onConnection = (state: Connection) => {
    if (state === "failed") setStreamFailed(true);
    if (state === "reconnecting" && grace.current === null) {
      grace.current = setTimeout(() => setStreamFailed(true), RECONNECT_GRACE_MS);
    }
    if (state === "live" && grace.current !== null) {
      clearTimeout(grace.current);
      grace.current = null;
    }
  };
  useEffect(
    () => () => {
      if (grace.current !== null) clearTimeout(grace.current);
    },
    [],
  );
  const progress = useAuditProgress(active ? `/api/audits/${auditId}/events` : null, {
    onTerminal: () => {
      refreshAccount(client); // captured or released: the balance is the server's to say
    },
    onConnection,
  });

  if (audit.isPending) {
    return (
      <div className={styles["page"]}>
        <PageHeading title={t.analyses.page.title} />
        <div role="status" aria-busy="true" aria-label={t.analyses.page.loading}>
          <Skeleton height="120px" />
        </div>
      </div>
    );
  }
  if (audit.isError) {
    const error = audit.error;
    const notFound = error instanceof ApiError && error.status === 404;
    const described =
      error instanceof ApiError && error.code !== null
        ? describeProblem(error.code, { requestId: error.requestId })
        : describeTransport(error instanceof TransportError ? error.kind : "invalid-response");
    return (
      <div className={styles["page"]}>
        <PageHeading title={t.analyses.page.title} />
        <InlineNotice
          tone={notFound ? "warning" : "danger"}
          title={notFound ? t.analyses.page.notFoundTitle : described.title}
          live="alert"
          actions={
            notFound ? (
              <LinkButton to="/app/analyses" icon="arrow">
                {t.shell.destinations.analyses}
              </LinkButton>
            ) : (
              <Button
                type="button"
                variant="primary"
                icon="refresh"
                busy={audit.isFetching}
                onClick={() => void audit.refetch()}
              >
                {t.common.retry}
              </Button>
            )
          }
        >
          {notFound ? t.analyses.page.notYours : described.detail}
        </InlineNotice>
      </div>
    );
  }

  const data = audit.data;
  const copy = statusCopy(data.status, data.error_code);
  // A finished report is the page: the listing and the sections, nothing about the run that produced it. The credit
  // outcome of a finished run is on the account; "Moje analizy" is in the navigation.
  if (hasReport(data.status)) {
    return (
      <div className={`${styles["page"]} ${styles["report"]}`}>
        <PageHeading title={t.common.listingTitle({ id: data.otodom_id })} compact />
        <ReportBody result={data.result} degraded={data.status === "succeeded_degraded"} />
      </div>
    );
  }
  return (
    <div className={styles["page"]}>
      <PageHeading
        title={t.analyses.page.title}
        eyebrow={t.common.listingTitle({ id: data.otodom_id })}
        lead={isActive(data.status) && progress.stage !== null ? t.analyses.page.inProgress : copy.label}
      />

      {isActive(data.status) ? (
        <section className={styles["card"]} aria-label={t.analyses.page.progressLabel}>
          {progress.connection === "reconnecting" ? (
            <InlineNotice tone="warning" title={t.analyses.page.reconnectingTitle} live="status">
              {t.analyses.page.reconnectingBody}
            </InlineNotice>
          ) : null}
          {streamFailed ? (
            <InlineNotice tone="info" title={t.analyses.page.pollingTitle} live="status">
              {t.analyses.page.pollingBody}
            </InlineNotice>
          ) : null}
          <p className={styles["pct"]} aria-hidden="true">
            {progress.pct !== null ? formatPercent(progress.pct) : "…"}
          </p>
          <div
            className={styles["bar"]}
            role="progressbar"
            aria-label={t.analyses.page.progressLabel}
            aria-valuemin={0}
            aria-valuemax={100}
            {...(progress.pct !== null ? { "aria-valuenow": progress.pct } : {})}
          >
            <span className={styles["fill"]} style={{ width: `${progress.pct ?? 0}%` }} />
          </div>
          <p role="status" className={styles["meta"]}>
            {progress.stage !== null
              ? stageLabel(progress.stage)
              : data.status === "queued"
                ? t.analyses.page.waitingInQueue
                : t.analyses.page.starting}
          </p>
          {progress.stages.length > 0 ? (
            <ol className={styles["stages"]} aria-label={t.analyses.page.stagesLabel}>
              {progress.stages.map((stage) => (
                <li key={stage} aria-current={stage === progress.stage ? "step" : undefined}>
                  <Icon name={stage === progress.stage ? "arrow" : "check"} />
                  {stageLabel(stage)}
                </li>
              ))}
            </ol>
          ) : null}
          <p className={styles["meta"]}>{CHARGE[data.charge_state]}</p>
        </section>
      ) : (
        <section className={styles["card"]} aria-label={t.analyses.page.resultLabel}>
          <InlineNotice tone={copy.tone === "neutral" ? "info" : copy.tone} title={copy.label} live="status">
            {describeProblemFor(data.error_code)}
          </InlineNotice>
          <p className={styles["meta"]}>{CHARGE[data.charge_state]}</p>
          <div className={styles["actions"]}>
            <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
              {t.shell.destinations["new-analysis"]}
            </LinkButton>
            <LinkButton to="/app/analyses" icon="arrow">
              {t.shell.destinations.analyses}
            </LinkButton>
          </div>
        </section>
      )}
    </div>
  );
}

/** The stored result, rendered only in a version this build knows; anything else is said so, never guessed at. */
function ReportBody({ result, degraded }: { readonly result: unknown; readonly degraded: boolean }) {
  const parsed = parseReport(result);
  if (parsed.kind === "ready") return <ReportView report={parsed.report} degraded={degraded} />;
  if (parsed.kind === "unsupported")
    return (
      <InlineNotice tone="warning" title={t.analyses.page.unsupportedTitle} live="status">
        {t.analyses.page.unsupportedBody}
      </InlineNotice>
    );
  return (
    <InlineNotice tone="danger" title={t.analyses.page.invalidTitle} live="status">
      {t.analyses.page.invalidBody}
    </InlineNotice>
  );
}

/** The stored error code is server data: only a known problem code gets its copy, anything else a plain line. */
function describeProblemFor(code: string | null): string {
  return code !== null && isProblemCode(code) ? describeProblem(code).detail : t.analyses.page.notFinished;
}
