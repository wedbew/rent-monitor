import { InlineNotice } from "../ui/Status";
import type { Availability } from "./navigation";
import { PageHeading } from "./PageHeading";

const COPY: Record<Exclude<Availability, "ready">, { title: string; body: string }> = {
  building: {
    title: "Ta część aplikacji jest w budowie",
    body: "Ten ekran powstaje w kolejnych etapach. Nie pokazujemy danych przykładowych jako prawdziwych.",
  },
  unavailable: {
    title: "Niedostępne",
    body: "Ta funkcja nie jest jeszcze dostępna. Nic nie jest pobierane z konta.",
  },
};

interface PendingPageProps {
  readonly title: string;
  readonly availability: Exclude<Availability, "ready">;
  readonly lead?: string;
}

/** An honest destination for a route that exists in the navigation but is not built or not offered yet. */
export function PendingPage({ title, availability, lead }: PendingPageProps) {
  const copy = COPY[availability];
  return (
    <>
      <PageHeading title={title} {...(lead ? { lead } : {})} />
      <InlineNotice tone="info" title={copy.title}>
        {copy.body}
      </InlineNotice>
    </>
  );
}
