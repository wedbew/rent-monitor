import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ThemeControl } from "./ThemeControl";
import { applyTheme, THEME_KEY } from "./theme";

const html = document.documentElement;

/** Reduced motion: the static lucide icon is rendered at once (the animated one loads lazily and would race the test). */
function preferReducedMotion() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("reduce"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

beforeEach(() => {
  preferReducedMotion();
  html.dataset["theme"] = "light";
  localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ThemeControl", () => {
  it("names the mode it switches to, with the matching icon, and switches it", async () => {
    render(<ThemeControl />);
    const toDark = screen.getByRole("button", { name: "Tryb ciemny" });
    expect(toDark.querySelector("svg")).toHaveClass("lucide-moon");
    await userEvent.click(toDark);
    expect(html.dataset["theme"]).toBe("dark");
    const toLight = screen.getByRole("button", { name: "Tryb jasny" });
    expect(toLight.querySelector("svg")).toHaveClass("lucide-sun");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  });

  it("keeps working when storage throws", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("blocked", "SecurityError");
    });
    render(<ThemeControl />);
    await userEvent.click(screen.getByRole("button", { name: "Tryb ciemny" }));
    expect(html.dataset["theme"]).toBe("dark");
    expect(screen.getByRole("button", { name: "Tryb jasny" })).toBeInTheDocument();
  });

  it("follows a change made in another tab", () => {
    render(<ThemeControl />);
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: "dark" }));
    });
    expect(html.dataset["theme"]).toBe("dark");
    expect(screen.getByRole("button", { name: "Tryb jasny" })).toBeInTheDocument();
    act(() => {
      window.dispatchEvent(new StorageEvent("storage", { key: THEME_KEY, newValue: "something-else" }));
    });
    expect(html.dataset["theme"]).toBe("light");
  });

  it("applyTheme announces the change to subscribers", () => {
    const seen = vi.fn();
    window.addEventListener("renti-theme-change", seen);
    applyTheme("dark");
    expect(seen).toHaveBeenCalledOnce();
    window.removeEventListener("renti-theme-change", seen);
  });
});
