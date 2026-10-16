import { config } from "../../config";

/**
 * Paddle.js, loaded only when a purchase is started or `/pay` opens, with the public client-side token only (never an
 * API key). Tests and the browser lanes put a stub on `window.Paddle` first; the loader then makes no request.
 * GDPR[processor]: Paddle receives the buyer's details in its own checkout, not through this app (RM-277).
 */
export const PADDLE_SCRIPT = "https://cdn.paddle.com/paddle/v2/paddle.js";
const LOAD_TIMEOUT_MS = 10_000;

interface CheckoutOptions {
  readonly transactionId: string;
  readonly settings?: { readonly successUrl?: string; readonly displayMode?: "overlay" };
}

export interface PaddleGlobal {
  readonly Environment?: { set(environment: "sandbox"): void };
  Initialize(options: { token: string; eventCallback?: (event: { name?: string }) => void }): void;
  readonly Checkout: { open(options: CheckoutOptions): void };
}

declare global {
  interface Window {
    Paddle?: PaddleGlobal;
  }
}

export type PaddleFailure = "not-configured" | "load-failed";
export class PaddleError extends Error {
  readonly kind: PaddleFailure;
  constructor(kind: PaddleFailure) {
    super(kind);
    this.name = "PaddleError";
    this.kind = kind;
  }
}

export const paddleConfigured = (): boolean => config.paddleClientToken !== "";

let loading: Promise<PaddleGlobal> | null = null;
let initialised = false;

function injectScript(): Promise<PaddleGlobal> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = PADDLE_SCRIPT;
    script.async = true;
    const timer = setTimeout(() => {
      script.remove();
      reject(new PaddleError("load-failed"));
    }, LOAD_TIMEOUT_MS);
    script.onload = () => {
      clearTimeout(timer);
      if (window.Paddle === undefined) reject(new PaddleError("load-failed"));
      else resolve(window.Paddle);
    };
    script.onerror = () => {
      clearTimeout(timer);
      script.remove();
      reject(new PaddleError("load-failed"));
    };
    document.head.append(script);
  });
}

/** Paddle.js, initialised once with the public token. A failed load may be tried again. */
export async function loadPaddle(): Promise<PaddleGlobal> {
  if (!paddleConfigured()) throw new PaddleError("not-configured");
  loading ??= (window.Paddle !== undefined ? Promise.resolve(window.Paddle) : injectScript()).catch(
    (error: unknown) => {
      loading = null;
      throw error;
    },
  );
  const paddle = await loading;
  if (!initialised) {
    if (config.paddleEnvironment === "sandbox") paddle.Environment?.set("sandbox");
    paddle.Initialize({ token: config.paddleClientToken });
    initialised = true;
  }
  return paddle;
}

/** For tests: forget the loaded script and the initialisation. */
export function resetPaddleForTests(): void {
  loading = null;
  initialised = false;
}

/**
 * Open the overlay for a transaction the server created. The success address only brings the person back to the
 * page that polls the server: the browser's own "success" never grants anything.
 */
export async function openCheckout(transactionId: string, successPath: string): Promise<void> {
  const paddle = await loadPaddle();
  paddle.Checkout.open({
    transactionId,
    settings: { displayMode: "overlay", successUrl: new URL(successPath, window.location.origin).toString() },
  });
}
