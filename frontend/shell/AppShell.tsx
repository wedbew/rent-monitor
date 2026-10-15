import { Outlet } from "react-router";

import { AccountBlock } from "./AccountBlock";
import { Brand } from "./Brand";
import { MobileMenu } from "./MobileMenu";
import { LEGAL, PRIMARY } from "./navigation";
import { NavList } from "./NavList";
import styles from "./AppShell.module.css";
import { useSession } from "./session";
import { ThemeControl } from "./ThemeControl";
import { VerifyBanner } from "./VerifyBanner";
import { t } from "../i18n";

/**
 * Landmarks: one banner (the rail on desktop, the bar on mobile), one `main`, a skip link first. The desktop rail
 * and the mobile bar are the same element, rearranged by CSS, so there is one theme control and one brand link.
 */
export function AppShell() {
  const session = useSession();
  return (
    <div className={styles["shell"]}>
      <a className={styles["skip"]} href="#main">
        {t.shell.skipToContent}
      </a>
      <header className={styles["rail"]}>
        <div className={styles["brand"]}>
          <Brand />
        </div>
        <div className={styles["primary"]}>
          <NavList label={t.shell.appNavigation} destinations={PRIMARY} />
        </div>
        <div className={styles["bottom"]}>
          <ThemeControl />
          <div className={styles["legal"]}>
            <NavList label={t.shell.documents} destinations={LEGAL} />
          </div>
          {session.status === "signedIn" ? (
            <div className={styles["account"]}>
              <AccountBlock />
            </div>
          ) : null}
        </div>
        <div className={styles["menu"]}>
          <MobileMenu />
        </div>
      </header>
      <main id="main" tabIndex={-1} className={styles["main"]}>
        <div className={styles["content"]}>
          {session.status === "signedIn" ? (
            <div className={styles["banner"]}>
              <VerifyBanner />
            </div>
          ) : null}
          <Outlet />
        </div>
      </main>
    </div>
  );
}
