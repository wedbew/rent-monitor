import { useEffect, useRef, useState } from "react";

import { config } from "../../config";
import { useTheme } from "../../shell/theme";
import { InlineNotice } from "../../ui/Status";
import { Skeleton } from "../../ui/Skeleton";
import { type GisId, loadGis } from "./gis";
import styles from "./auth.module.css";

interface GoogleButtonProps {
  readonly text: "signin_with" | "signup_with";
  readonly onCredential: (credential: string) => void;
}

let initialised = false;
let deliver: ((credential: string) => void) | null = null;

function initialise(gis: GisId): void {
  if (initialised) return;
  initialised = true;
  gis.initialize({
    client_id: config.googleClientId,
    callback: ({ credential }) => {
      if (credential !== undefined && credential !== "") deliver?.(credential);
    },
  });
}

/**
 * Google's own sign-in button (callback mode). Not configured (`VITE_GOOGLE_CLIENT_ID` empty): nothing is rendered,
 * there is no fake button. Blocked or offline: a plain notice points to the e-mail methods, which always work.
 */
export function GoogleButton({ text, onCredential }: GoogleButtonProps) {
  const [theme] = useTheme();
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    deliver = onCredential;
    return () => {
      deliver = null;
    };
  }, [onCredential]);

  useEffect(() => {
    if (config.googleClientId === "") return;
    let cancelled = false;
    loadGis().then(
      (gis) => {
        if (cancelled || host.current === null) return;
        initialise(gis);
        host.current.replaceChildren();
        gis.renderButton(host.current, {
          type: "standard",
          theme: theme === "dark" ? "filled_black" : "outline",
          size: "large",
          text,
          shape: "rectangular",
          locale: "pl",
          width: Math.min(host.current.clientWidth || 320, 400),
        });
        setState("ready");
      },
      () => {
        if (!cancelled) setState("unavailable");
      },
    );
    return () => {
      cancelled = true;
    };
  }, [theme, text]);

  if (config.googleClientId === "") return null;
  return (
    <div>
      <div ref={host} className={styles["google"]} aria-busy={state === "loading"} />
      {state === "loading" ? <Skeleton height="44px" /> : null}
      {state === "unavailable" ? (
        <InlineNotice tone="info" title="Logowanie przez Google jest niedostępne">
          Użyj adresu e-mail: hasła albo linku wysłanego na skrzynkę.
        </InlineNotice>
      ) : null}
    </div>
  );
}
