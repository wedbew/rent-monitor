import { Link } from "react-router";

import styles from "./Brand.module.css";

/** The supplied outlined logo; the light and dark artwork swap with the theme (the hidden one is not exposed). */
export function Brand() {
  return (
    <Link to="/app" className={styles["brand"]} aria-label="renti.tech, przejdź do pulpitu">
      <img className={styles["light"]} src="/renti-logo.svg" width="165" height="40" alt="" />
      <img className={styles["dark"]} src="/renti-logo-dark.svg" width="165" height="40" alt="" />
    </Link>
  );
}
