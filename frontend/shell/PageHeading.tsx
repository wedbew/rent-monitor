import { useEffect, useRef } from "react";

import { takeHeadingFocus } from "./headingFocus";
import styles from "./PageHeading.module.css";
import { t } from "../i18n";

interface PageHeadingProps {
  readonly title: string;
  /** Short line above the heading (an eyebrow), optional. */
  readonly eyebrow?: string;
  readonly lead?: string;
}

/**
 * Every page starts with this: the one `h1`, the document title for the route, and a focus target. After a client
 * navigation the shell moves focus to this heading, because the browser does not do it for a single-page app.
 */
export function PageHeading({ title, eyebrow, lead }: PageHeadingProps) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = t.shell.documentTitle({ page: title });
  }, [title]);
  // A page whose code loaded after the navigation takes the focus the shell asked for (shell/headingFocus.ts).
  useEffect(() => {
    takeHeadingFocus(ref.current);
  }, []);
  return (
    <div className={styles["heading"]}>
      {eyebrow ? <p className={styles["eyebrow"]}>{eyebrow}</p> : null}
      <h1 ref={ref} tabIndex={-1}>
        {title}
      </h1>
      {lead ? <p className={styles["lead"]}>{lead}</p> : null}
    </div>
  );
}
