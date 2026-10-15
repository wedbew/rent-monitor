import { Link, Outlet } from "react-router";

import { Brand } from "../../shell/Brand";
import { ThemeControl } from "../../shell/ThemeControl";
import styles from "./PublicLayout.module.css";
import { t } from "../../i18n";

/** The frame of every page a signed-out person can reach: brand, appearance, the one centred column, documents. */
export function PublicLayout() {
  return (
    <div className={styles["layout"]}>
      <a className={styles["skip"]} href="#main">
        {t.shell.skipToContent}
      </a>
      <header className={styles["bar"]}>
        <Brand />
        <div className={styles["theme"]}>
          <ThemeControl />
        </div>
      </header>
      <main id="main" tabIndex={-1} className={styles["main"]}>
        <div className={styles["card"]}>
          <Outlet />
        </div>
      </main>
      <footer className={styles["footer"]}>
        <nav aria-label={t.shell.documents}>
          <Link to="/terms">{t.shell.destinations.terms}</Link>
          <Link to="/privacy">{t.shell.destinations.privacy}</Link>
        </nav>
      </footer>
    </div>
  );
}
