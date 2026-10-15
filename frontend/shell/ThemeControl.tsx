import { Icon } from "../ui/Icon";
import styles from "./ThemeControl.module.css";
import { useTheme } from "./theme";

/**
 * One control for the appearance. Its visible text is its accessible name and always names the mode it switches
 * TO, with the matching icon (moon for dark, sun for light), so what is read, shown and announced agree.
 */
export function ThemeControl() {
  const [theme, toggle] = useTheme();
  const toDark = theme === "light";
  return (
    <button type="button" className={styles["control"]} onClick={toggle}>
      <span className={styles["icon"]}>
        <Icon name={toDark ? "moon" : "sun"} />
      </span>
      <span>{toDark ? "Tryb ciemny" : "Tryb jasny"}</span>
    </button>
  );
}
