import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { captureFragmentToken, clearCapturedToken, readCapturedToken } from "./token";

const TOKEN = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";

function openLink(path: string, hash: string) {
  window.history.replaceState(null, "", `${path}${hash}`);
}

beforeEach(() => {
  clearCapturedToken();
  window.history.replaceState(null, "", "/");
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe("a token in the link's fragment", () => {
  it("is taken once, removed from the address bar and kept in memory only", () => {
    openLink("/login/email", `#t=${TOKEN}`);
    const replace = vi.spyOn(window.history, "replaceState");
    captureFragmentToken();
    expect(readCapturedToken()).toBe(TOKEN);
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/login/email");
    expect(replace).toHaveBeenCalledOnce();
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain(TOKEN);
  });

  it("keeps the query string when it strips the fragment", () => {
    openLink("/password/reset?next=%2Fapp", `#t=${TOKEN}`);
    captureFragmentToken();
    expect(window.location.search).toBe("?next=%2Fapp");
    expect(window.location.hash).toBe("");
  });

  it("can be read again (React may render twice) until it is cleared", () => {
    openLink("/signup/verify", `#t=${TOKEN}`);
    captureFragmentToken();
    expect(readCapturedToken()).toBe(TOKEN);
    expect(readCapturedToken()).toBe(TOKEN);
    clearCapturedToken();
    expect(readCapturedToken()).toBeNull();
  });

  it.each([
    "#t=short",
    "#t=has spaces and is long enough to pass length",
    "#other=1",
    "#t=",
    `#t=${"x".repeat(129)}`,
  ])("does not accept %s but still removes the fragment", (hash) => {
    openLink("/login/email", hash);
    captureFragmentToken();
    expect(readCapturedToken()).toBeNull();
    expect(window.location.hash).toBe("");
  });

  it("leaves a page without a fragment alone", () => {
    const replace = vi.spyOn(window.history, "replaceState");
    captureFragmentToken();
    expect(replace).not.toHaveBeenCalled();
    expect(readCapturedToken()).toBeNull();
  });
});
