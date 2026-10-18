import { useCallback, useEffect, useRef } from "react";

/**
 * The lifetime of a mounted component, for work that outlives a click (a checkout that waits for a script to load).
 * Call the returned function when the work is about to act, not when it started: it gives `null` once the component
 * is gone. Created in an effect, so a StrictMode replay aborts the first one and the second is the live one.
 */
export function useMountLifetime(): () => AbortSignal | null {
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    const own = new AbortController();
    controller.current = own;
    return () => {
      own.abort();
      if (controller.current === own) controller.current = null;
    };
  }, []);
  return useCallback(() => controller.current?.signal ?? null, []);
}
