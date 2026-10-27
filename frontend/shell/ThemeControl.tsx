import { AnimatedIcon } from "../ui/AnimatedIcon";
import styles from "./ThemeControl.module.css";
import { useTheme } from "./theme";
import { t } from "../i18n";

/**
 * Names the destination mode, with a matching moon/sun icon. The mobile toolbar shows only the icon;
 * its localized accessible name and native tooltip remain available at every width.
 */
export function ThemeControl() {
  const [theme, toggle] = useTheme();
  const toDark = theme === "light";
  const label = toDark ? t.shell.theme.toDark : t.shell.theme.toLight;
  return (
    <button type="button" className={styles["control"]} onClick={toggle} aria-label={label} title={label}>
      <span className={styles["icon"]}>
        <AnimatedIcon name={toDark ? "moon" : "sun"} />
      </span>
      <span className={styles["label"]}>{label}</span>
    </button>
  );
}
