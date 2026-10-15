import { LinkButton } from "../ui/Button";
import { PageHeading } from "./PageHeading";
import { t } from "../i18n";

/** An unknown path inside the app. It keeps the shell, so the person can leave with the navigation. */
export function NotFound() {
  return (
    <>
      <PageHeading title={t.shell.notFound.title} lead={t.shell.notFound.lead} />
      <LinkButton to="/app" variant="primary" icon="arrow">
        {t.shell.backToDashboard}
      </LinkButton>
    </>
  );
}
