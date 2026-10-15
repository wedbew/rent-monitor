import { useEffect } from "react";
import { isRouteErrorResponse, useRouteError } from "react-router";

import { Button, LinkButton } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { reportError } from "./observability";
import { PageHeading } from "./PageHeading";
import { t } from "../i18n";

/** A lazily loaded route chunk that no longer exists after a deploy (the HTML still points at an old file). */
export function isChunkLoadError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return (
    error.name === "ChunkLoadError" ||
    /Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i.test(
      error.message,
    )
  );
}

export type ErrorKind = "chunk" | "response" | "unexpected";

export function classifyRouteError(error: unknown): ErrorKind {
  if (isChunkLoadError(error)) return "chunk";
  return isRouteErrorResponse(error) ? "response" : "unexpected";
}

/**
 * The route error boundary. A reload is offered, never forced, so a bad deploy cannot put the page in a reload
 * loop. It renders inside the shell: the navigation still works.
 */
export function RouteError() {
  const error = useRouteError();
  const kind = classifyRouteError(error);
  const copy = t.shell.routeError[kind];
  // A screen that crashed is reported (a chunk gone after a deploy and a route's own error answer are expected).
  useEffect(() => {
    if (kind === "unexpected") reportError(error);
  }, [error, kind]);
  return (
    <>
      <PageHeading title={copy.title} />
      <InlineNotice
        tone="danger"
        title={t.shell.routeError.heading}
        live="alert"
        actions={
          <>
            <Button type="button" variant="primary" icon="refresh" onClick={() => window.location.reload()}>
              {copy.action}
            </Button>
            <LinkButton to="/app">{t.shell.backToDashboard}</LinkButton>
          </>
        }
      >
        {copy.body}
      </InlineNotice>
    </>
  );
}
