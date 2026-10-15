import { useEffect } from "react";

import styles from "./PageHeading.module.css";

interface PageHeadingProps {
  readonly title: string;
  /** Short line above the heading (an eyebrow), optional. */
  readonly eyebrow?: string;
  readonly lead?: string;
}

export const TITLE_SUFFIX = " · renti";

/**
 * Every page starts with this: the one `h1`, the document title for the route, and a focus target. After a client
 * navigation the shell moves focus to this heading, because the browser does not do it for a single-page app.
 */
export function PageHeading({ title, eyebrow, lead }: PageHeadingProps) {
  useEffect(() => {
    document.title = `${title}${TITLE_SUFFIX}`;
  }, [title]);
  return (
    <div className={styles["heading"]}>
      {eyebrow ? <p className={styles["eyebrow"]}>{eyebrow}</p> : null}
      <h1 tabIndex={-1}>{title}</h1>
      {lead ? <p className={styles["lead"]}>{lead}</p> : null}
    </div>
  );
}
