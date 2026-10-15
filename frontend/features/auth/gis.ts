/**
 * Google Identity Services, callback mode (no redirect URI, no client secret): the script renders Google's own
 * button and hands back a signed ID token that the API verifies (docs/GOOGLE-AUTH-SPEC.md).
 *
 * GDPR[processor]: loading the script and clicking the button sends the person's browser data and Google account
 * choice to Google (RM-271). It is loaded only on the sign-in pages, only when `VITE_GOOGLE_CLIENT_ID` is set.
 */
export interface GisCredentialResponse {
  readonly credential?: string;
}

export interface GisButtonOptions {
  readonly type: "standard";
  readonly theme: "outline" | "filled_blue" | "filled_black";
  readonly size: "large";
  readonly text: "signin_with" | "signup_with" | "continue_with";
  readonly shape: "rectangular";
  readonly locale: "pl";
  readonly width: number;
}

export interface GisId {
  initialize(config: { client_id: string; callback: (response: GisCredentialResponse) => void }): void;
  renderButton(parent: HTMLElement, options: GisButtonOptions): void;
  cancel(): void;
}

interface GoogleGlobal {
  readonly accounts: { readonly id: GisId };
}

declare global {
  interface Window {
    google?: GoogleGlobal;
  }
}

const SCRIPT_URL = "https://accounts.google.com/gsi/client";
const LOAD_TIMEOUT_MS = 10_000;
let pending: Promise<GisId> | null = null;

/** The GIS API, loading the script once. Rejects (never hangs) when it is blocked, offline or too slow. */
export function loadGis(): Promise<GisId> {
  const existing = window.google?.accounts.id;
  if (existing !== undefined) return Promise.resolve(existing);
  pending ??= new Promise<GisId>((resolve, reject) => {
    const script = document.createElement("script");
    const timer = window.setTimeout(() => fail(new Error("Google script timed out")), LOAD_TIMEOUT_MS);
    const fail = (error: Error) => {
      window.clearTimeout(timer);
      script.remove();
      pending = null;
      reject(error);
    };
    script.src = SCRIPT_URL;
    script.async = true;
    script.onload = () => {
      window.clearTimeout(timer);
      const loaded = window.google?.accounts.id;
      if (loaded === undefined) fail(new Error("Google script loaded without the API"));
      else resolve(loaded);
    };
    script.onerror = () => fail(new Error("Google script failed to load"));
    document.head.append(script);
  });
  return pending;
}
