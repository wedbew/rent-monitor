import { TransportError } from "../../api/errors";
import { InlineNotice } from "../../ui/Status";
import { readFailure } from "../auth/forms";
import { ProblemNotice } from "../auth/ProblemNotice";
import { t } from "../../i18n";

/**
 * A failed save, unsave or note change in words. After a dropped connection or a body we cannot read the UI says it
 * does not know (the server may have applied it); it never reports success it was not told (rules/frontend.md 4).
 */
export function MutationNotice({ error }: { readonly error: unknown }) {
  if (
    error instanceof TransportError &&
    (error.kind === "network" || error.kind === "timeout" || error.kind === "invalid-response")
  )
    return (
      <InlineNotice tone="warning" title={t.saved.unknownTitle} live="alert">
        {t.saved.unknownBody}
      </InlineNotice>
    );
  const { general } = readFailure(error);
  if (general === null) return <InlineNotice tone="danger" title={t.saved.failedTitle} live="alert" />;
  return <ProblemNotice problem={general} />;
}
