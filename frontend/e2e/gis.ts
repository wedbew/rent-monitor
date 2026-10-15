/**
 * A stand-in for Google Identity Services in the browser (the real script is Google's, loads from their servers and
 * renders an iframe). It renders an ordinary button so the app's real code path runs: load -> initialize ->
 * renderButton -> callback with a credential. Install before the page loads (`installFakeGis`).
 */
import type { Page } from "@playwright/test";

export async function installFakeGis(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const state: { callback: ((r: { credential: string }) => void) | null; next: string } = {
      callback: null,
      next: "fake-google-credential-0123456789",
    };
    (window as unknown as { __fakeGis: typeof state }).__fakeGis = state;
    (window as unknown as { google: unknown }).google = {
      accounts: {
        id: {
          initialize(config: { callback: (r: { credential: string }) => void }) {
            state.callback = config.callback;
          },
          renderButton(parent: HTMLElement, options: { text: string }) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent =
              options.text === "signup_with" ? "Zarejestruj się przez Google" : "Zaloguj się przez Google";
            button.addEventListener("click", () => state.callback?.({ credential: state.next }));
            parent.append(button);
          },
          cancel() {},
        },
      },
    };
  });
}

/** The next click on the fake Google button returns this credential. */
export async function nextGoogleCredential(page: Page, credential: string): Promise<void> {
  await page.evaluate((value) => {
    (window as unknown as { __fakeGis: { next: string } }).__fakeGis.next = value;
  }, credential);
}
