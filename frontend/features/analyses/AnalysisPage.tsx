import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router";

import { ApiError, TransportError } from "../../api/errors";
import { describeProblem, describeTransport } from "../../api/problems";
import { PageHeading } from "../../shell/PageHeading";
import { refreshAccount } from "../../shell/session";
import { Button, LinkButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Skeleton } from "../../ui/Skeleton";
import { InlineNotice } from "../../ui/Status";
import { useAudit } from "./queries";
import { stageLabel } from "./progress/frames";
import type { Connection } from "./progress/streams";
import { parseReport } from "../../api/report";
import { ReportView } from "./report/ReportView";
import { useAuditProgress } from "./progress/useAuditProgress";
import { hasReport, isActive, statusCopy } from "./status";
import styles from "./AnalysisPage.module.css";

export const RECONNECT_GRACE_MS = 8000;

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** What happened to the report credit, in the server's own terms (`charge_state`), never inferred from the status. */
const CHARGE: Record<"reserved" | "captured" | "released", string> = {
  reserved: "Raport jest zarezerwowany do końca analizy.",
  captured: "Raport został pobrany z konta.",
  released: "Raport nie został pobrany z konta.",
};

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
        <PageHeading title="Raport" />
        <InlineNotice tone="warning" title="Nie znaleziono analizy">
          Ten adres nie wskazuje żadnej Twojej analizy.
        </InlineNotice>
        <LinkButton to="/app/analyses" icon="arrow">
          Moje analizy
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
        <PageHeading title="Raport" />
        <div role="status" aria-busy="true" aria-label="Wczytuję analizę">
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
        <PageHeading title="Raport" />
        <InlineNotice
          tone={notFound ? "warning" : "danger"}
          title={notFound ? "Nie znaleziono analizy" : described.title}
          live="alert"
          actions={
            notFound ? (
              <LinkButton to="/app/analyses" icon="arrow">
                Moje analizy
              </LinkButton>
            ) : (
              <Button
                type="button"
                variant="primary"
                icon="refresh"
                busy={audit.isFetching}
                onClick={() => void audit.refetch()}
              >
                Spróbuj ponownie
              </Button>
            )
          }
        >
          {notFound ? "Ta analiza nie istnieje albo nie należy do Ciebie." : described.detail}
        </InlineNotice>
      </div>
    );
  }

  const data = audit.data;
  const copy = statusCopy(data.status, data.error_code);
  return (
    <div className={styles["page"]}>
      <PageHeading
        title="Raport"
        eyebrow={`Ogłoszenie ${data.otodom_id}`}
        lead={isActive(data.status) && progress.stage !== null ? "W trakcie" : copy.label}
      />

      {isActive(data.status) ? (
        <section className={styles["card"]} aria-label="Postęp analizy">
          {progress.connection === "reconnecting" ? (
            <InlineNotice tone="warning" title="Łączę ponownie" live="status">
              Połączenie z serwerem przerwało się. Analiza trwa dalej; postęp wróci za chwilę.
            </InlineNotice>
          ) : null}
          {streamFailed ? (
            <InlineNotice tone="info" title="Sprawdzam postęp co kilka sekund" live="status">
              Podgląd na żywo jest niedostępny. Wynik pojawi się tu, gdy analiza się skończy.
            </InlineNotice>
          ) : null}
          <p className={styles["pct"]} aria-hidden="true">
            {progress.pct !== null ? `${progress.pct}%` : "…"}
          </p>
          <div
            className={styles["bar"]}
            role="progressbar"
            aria-label="Postęp analizy"
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
                ? "Czekam na wolne miejsce w kolejce"
                : "Zaczynam"}
          </p>
          {progress.stages.length > 0 ? (
            <ol className={styles["stages"]} aria-label="Etapy analizy">
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
        <section className={styles["card"]} aria-label="Wynik analizy">
          <InlineNotice tone={copy.tone === "neutral" ? "info" : copy.tone} title={copy.label} live="status">
            {hasReport(data.status) ? "Analiza jest gotowa." : describeProblemFor(data.error_code)}
          </InlineNotice>
          <p className={styles["meta"]}>{CHARGE[data.charge_state]}</p>
          <div className={styles["actions"]}>
            {hasReport(data.status) ? null : (
              <LinkButton to="/app/analyses/new" variant="primary" icon="arrow">
                Nowa analiza
              </LinkButton>
            )}
            <LinkButton to="/app/analyses" icon="arrow">
              Moje analizy
            </LinkButton>
          </div>
        </section>
      )}
      {hasReport(data.status) ? (
        <ReportBody result={data.result} degraded={data.status === "succeeded_degraded"} />
      ) : null}
    </div>
  );
}

/** The stored result, rendered only in a version this build knows; anything else is said so, never guessed at. */
function ReportBody({ result, degraded }: { readonly result: unknown; readonly degraded: boolean }) {
  const parsed = parseReport(result);
  if (parsed.kind === "ready") return <ReportView report={parsed.report} degraded={degraded} />;
  if (parsed.kind === "unsupported")
    return (
      <InlineNotice tone="warning" title="Nieobsługiwana wersja raportu" live="status">
        Ten raport powstał w wersji, której ta aplikacja jeszcze nie potrafi wyświetlić. Dane są bezpieczne i
        nie zostały zmienione; nic nie jest pokazywane na podstawie domysłów.
      </InlineNotice>
    );
  return (
    <InlineNotice tone="danger" title="Nie można wyświetlić raportu" live="status">
      Zapisany wynik jest niekompletny. Napisz do pomocy, podając numer ogłoszenia.
    </InlineNotice>
  );
}

function describeProblemFor(code: string | null): string {
  if (code === null) return "Analiza nie została ukończona.";
  try {
    return describeProblem(code as Parameters<typeof describeProblem>[0]).detail;
  } catch {
    return "Analiza nie została ukończona.";
  }
}
