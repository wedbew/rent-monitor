import styles from "./Skeleton.module.css";

interface SkeletonProps {
  /** Reserve the layout of what is loading; never put a fabricated number here. */
  readonly width?: string;
  readonly height?: string;
}

/** A loading placeholder. It is hidden from assistive technology: the region that loads says `aria-busy`. */
export function Skeleton({ width = "100%", height = "1em" }: SkeletonProps) {
  return <span className={styles["skeleton"]} style={{ width, height }} aria-hidden="true" />;
}
