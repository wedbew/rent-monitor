import { InlineNotice } from "../ui/Status";
import type { Availability } from "./navigation";
import { PageHeading } from "./PageHeading";
import { t } from "../i18n";

interface PendingPageProps {
  readonly title: string;
  readonly availability: Exclude<Availability, "ready">;
  readonly lead?: string;
}

/** An honest destination for a route that exists in the navigation but is not built or not offered yet. */
export function PendingPage({ title, availability, lead }: PendingPageProps) {
  const copy = t.shell.pending[availability];
  return (
    <>
      <PageHeading title={title} {...(lead ? { lead } : {})} />
      <InlineNotice tone="info" title={copy.title}>
        {copy.body}
      </InlineNotice>
    </>
  );
}
