import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";

import { Brand } from "./Brand";
import { MobileMenu } from "./MobileMenu";
import { LEGAL, PRIMARY } from "./navigation";
import { NavList } from "./NavList";
import styles from "./AppShell.module.css";
import { ThemeControl } from "./ThemeControl";

/** A single-page app gets no focus move from the browser on navigation: put it on the new page's heading. */
function useRouteFocus(): void {
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
}

/**
 * Landmarks: one banner (the rail on desktop, the bar on mobile), one `main`, a skip link first. The desktop rail
 * and the mobile bar are the same element, rearranged by CSS, so there is one theme control and one brand link.
 */
export function AppShell() {
  useRouteFocus();
  return (
    <div className={styles["shell"]}>
      <a className={styles["skip"]} href="#main">
        Przejdź do treści
      </a>
      <header className={styles["rail"]}>
        <div className={styles["brand"]}>
          <Brand />
        </div>
        <div className={styles["primary"]}>
          <NavList label="Nawigacja aplikacji" destinations={PRIMARY} />
        </div>
        <div className={styles["bottom"]}>
          <ThemeControl />
          <div className={styles["legal"]}>
            <NavList label="Dokumenty" destinations={LEGAL} />
          </div>
        </div>
        <div className={styles["menu"]}>
          <MobileMenu />
        </div>
      </header>
      <main id="main" tabIndex={-1} className={styles["main"]}>
        <div className={styles["content"]}>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
