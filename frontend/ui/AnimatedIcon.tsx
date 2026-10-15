import { type ComponentType, lazy, Suspense, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Icon, type IconName } from "./Icon";
import styles from "./AnimatedIcon.module.css";

/** An animation the owning control plays; the library icon exposes exactly these two calls. */
interface Handle {
  startAnimation: () => void;
  stopAnimation: () => void;
}
interface AnimatedProps {
  readonly size?: number;
  readonly "aria-hidden"?: boolean | "true";
  readonly ref?: React.Ref<Handle>;
}

type Loader = () => Promise<{ default: ComponentType<AnimatedProps> }>;

/** Icons that earn a motion (the control they sit in is hovered or focused). Everything else stays static lucide. */
const LOADERS: Partial<Record<IconName, Loader>> = {
  sun: () => import("./animatedIcons").then((m) => ({ default: m.SunIcon as ComponentType<AnimatedProps> })),
  moon: () =>
    import("./animatedIcons").then((m) => ({ default: m.MoonIcon as ComponentType<AnimatedProps> })),
  refresh: () =>
    import("./animatedIcons").then((m) => ({ default: m.RefreshCwIcon as ComponentType<AnimatedProps> })),
};
const LAZY = Object.fromEntries(Object.entries(LOADERS).map(([name, load]) => [name, lazy(load)])) as Partial<
  Record<IconName, ReturnType<typeof lazy<ComponentType<AnimatedProps>>>>
>;

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}
const reducedNow = () => typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;

/** The person's motion preference, live. */
export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, reducedNow, () => false);
}

/** True for icons that have an animated form. */
export const hasAnimation = (name: IconName): boolean => name in LOADERS;

interface Props {
  readonly name: IconName;
  readonly size?: number;
}

/**
 * A lucide icon that plays its animation while the button or link around it is hovered or keyboard-focused. The
 * static icon is shown until the first hover or focus has loaded the animation, and always when the person asks for
 * reduced motion or the icon has no animation. Decorative: the control holds the accessible name.
 */
export function AnimatedIcon({ name, size = 18 }: Props) {
  const reduced = usePrefersReducedMotion();
  const Animated = LAZY[name];
  const host = useRef<HTMLSpanElement>(null);
  const handle = useRef<Handle | null>(null);
  // The animation chunk (motion and the icons) is fetched on the first hover or focus of the control, not on every
  // page load: a person who never points at the control never pays for it.
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    const control = host.current?.closest("button, a");
    if (!control || reduced || Animated === undefined) return undefined;
    const play = () => {
      setArmed(true);
      handle.current?.startAnimation();
    };
    const stop = () => handle.current?.stopAnimation();
    control.addEventListener("pointerenter", play);
    control.addEventListener("pointerleave", stop);
    control.addEventListener("focusin", play);
    control.addEventListener("focusout", stop);
    return () => {
      control.removeEventListener("pointerenter", play);
      control.removeEventListener("pointerleave", stop);
      control.removeEventListener("focusin", play);
      control.removeEventListener("focusout", stop);
    };
  }, [reduced, Animated]);
  const fallback = <Icon name={name} size={size} />;
  if (reduced || Animated === undefined) return fallback;
  return (
    <span ref={host} className={styles["host"]} aria-hidden="true">
      {armed ? (
        <Suspense fallback={fallback}>
          <Animated
            ref={(instance: Handle | null) => {
              handle.current = instance;
              // Loaded while the pointer or focus is still on the control: play the animation it asked for.
              if (instance && host.current?.closest("button, a")?.matches(":hover, :focus-within"))
                instance.startAnimation();
            }}
            size={size}
            aria-hidden="true"
          />
        </Suspense>
      ) : (
        fallback
      )}
    </span>
  );
}
