import type { ReactNode } from "react";

import styles from "./market.module.css";

/** A table wider than the screen scrolls inside a named region the keyboard can reach. */
export function ScrollRegion({ label, children }: { readonly label: string; readonly children: ReactNode }) {
  return (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scrollable region must be reachable by keyboard
    <div className={styles["region"]} role="region" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}
