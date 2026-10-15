import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

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
    const frame = requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("main h1")?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [pathname]);
  return <Outlet />;
}
