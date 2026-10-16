/**
 * A stand-in for Paddle.js in the mocked lane, installed for EVERY mocked test (e2e/fixtures.ts): a test never reaches
 * Paddle. `window.Paddle` is defined before the app starts, so the loader finds
 * it and never fetches the CDN script; any request to Paddle's hosts is aborted and recorded so a test can prove none
 * was made. `Checkout.open` records what it was given. Nothing here talks to Paddle: this is a stub, not evidence.
 */
import type { Page } from "@playwright/test";

export interface PaddleOpen {
  readonly transactionId: string;
  readonly settings?: { readonly successUrl?: string; readonly displayMode?: string };
}

export interface FakePaddle {
  opened(): Promise<PaddleOpen[]>;
  /** Requests to a Paddle host the page tried to make. */
  readonly hostRequests: string[];
}

export interface FakePaddleHandle extends FakePaddle {
  /** Make `Checkout.open` throw (a blocked or crashed payment window) from now on. */
  failOpen(on: boolean): Promise<void>;
}

export async function installFakePaddle(page: Page): Promise<FakePaddleHandle> {
  const hostRequests: string[] = [];
  await page.route(/\/\/[^/]*paddle\.com\//, async (route) => {
    hostRequests.push(route.request().url());
    await route.abort();
  });
  await page.addInitScript(() => {
    const opened: unknown[] = [];
    (window as unknown as { __paddleOpened: unknown[] }).__paddleOpened = opened;
    (window as unknown as { Paddle: unknown }).Paddle = {
      Environment: { set: () => undefined },
      Initialize: () => undefined,
      Checkout: {
        open: (options: unknown) => {
          if ((window as unknown as { __paddleFailOpen?: boolean }).__paddleFailOpen === true)
            throw new Error("blocked");
          opened.push(options);
        },
      },
    };
  });
  return {
    hostRequests,
    failOpen: async (on: boolean) => {
      // For pages loaded from now on, and for the one already open.
      await page.addInitScript((value) => {
        (window as unknown as { __paddleFailOpen?: boolean }).__paddleFailOpen = value;
      }, on);
      await page.evaluate((value) => {
        (window as unknown as { __paddleFailOpen?: boolean }).__paddleFailOpen = value;
      }, on);
    },
    opened: () =>
      page.evaluate(() => (window as unknown as { __paddleOpened?: PaddleOpen[] }).__paddleOpened ?? []),
  };
}
