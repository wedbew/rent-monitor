import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

import { requestHeadingFocus } from "./headingFocus";
import styles from "./RootLayout.module.css";

/**
 * Above every frame (signed-out, app, documents). A single-page app gets no focus move from the browser when the
 * route changes: put it on the new page's heading, whichever frame the page is in. The first render is skipped:
 * a fresh page load already starts at the top.
 */
export function RootLayout() {
  const { pathname } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const frame = requestAnimationFrame(requestHeadingFocus);
    return () => cancelAnimationFrame(frame);
  }, [pathname]);
  return <Outlet />;
}

/**
 * What a page shows while its code loads (a lazily loaded page, #312): a quiet status, never a blank screen. A
 * failure to load lands in the route's error boundary instead.
 */
export function AppLoading() {
  return (
    <p role="status" aria-live="polite" className={styles["loading"]}>
      Wczytuję stronę…
    </p>
  );
}
