import { isRouteErrorResponse, useRouteError } from "react-router";

import { Button, LinkButton } from "../ui/Button";
import { InlineNotice } from "../ui/Status";
import { PageHeading } from "./PageHeading";

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

const COPY: Record<ErrorKind, { title: string; body: string; action: string }> = {
  chunk: {
    title: "Dostępna jest nowa wersja aplikacji",
    body: "Ta strona potrzebuje świeżej wersji. Odśwież ją, aby kontynuować. Nic z tego, co wpisano w innych kartach, nie zostanie utracone.",
    action: "Odśwież stronę",
  },
  response: {
    title: "Nie udało się otworzyć tej strony",
    body: "Serwer odpowiedział błędem. Spróbuj ponownie za chwilę.",
    action: "Spróbuj ponownie",
  },
  unexpected: {
    title: "Coś poszło nie tak",
    body: "Ten ekran nie zadziałał. Pozostała część aplikacji działa; spróbuj ponownie.",
    action: "Spróbuj ponownie",
  },
};

/**
 * The route error boundary. A reload is offered, never forced, so a bad deploy cannot put the page in a reload
 * loop. It renders inside the shell: the navigation still works.
 */
export function RouteError() {
  const error = useRouteError();
  const copy = COPY[classifyRouteError(error)];
  return (
    <>
      <PageHeading title={copy.title} />
      <InlineNotice
        tone="danger"
        title="Wystąpił błąd"
        live="alert"
        actions={
          <>
            <Button type="button" variant="primary" icon="refresh" onClick={() => window.location.reload()}>
              {copy.action}
            </Button>
            <LinkButton to="/app">Wróć do pulpitu</LinkButton>
          </>
        }
      >
        {copy.body}
      </InlineNotice>
    </>
  );
}
