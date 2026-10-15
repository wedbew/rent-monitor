import { LinkButton } from "../ui/Button";
import { PageHeading } from "./PageHeading";

/** An unknown path inside the app. It keeps the shell, so the person can leave with the navigation. */
export function NotFound() {
  return (
    <>
      <PageHeading
        title="Nie znaleziono strony"
        lead="Adres jest nieprawidłowy albo ta strona została przeniesiona."
      />
      <LinkButton to="/app" variant="primary" icon="arrow">
        Wróć do pulpitu
      </LinkButton>
    </>
  );
}
