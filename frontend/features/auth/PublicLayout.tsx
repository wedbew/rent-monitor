import { Link, Outlet } from "react-router";

import { Brand } from "../../shell/Brand";
import { ThemeControl } from "../../shell/ThemeControl";
import styles from "./PublicLayout.module.css";

/** The frame of every page a signed-out person can reach: brand, appearance, the one centred column, documents. */
export function PublicLayout() {
  return (
    <div className={styles["layout"]}>
      <a className={styles["skip"]} href="#main">
        Przejdź do treści
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
        <nav aria-label="Dokumenty">
          <Link to="/terms">Regulamin</Link>
          <Link to="/privacy">Polityka prywatności</Link>
        </nav>
      </footer>
    </div>
  );
}
