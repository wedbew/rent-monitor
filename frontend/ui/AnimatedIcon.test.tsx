import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnimatedIcon } from "./AnimatedIcon";

function stubMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AnimatedIcon", () => {
  it("renders the static lucide icon, hidden from assistive technology, under reduced motion", () => {
    stubMotion(true);
    const { container } = render(
      <button type="button" aria-label="Tryb ciemny">
        <AnimatedIcon name="moon" />
      </button>,
    );
    const svg = container.querySelector("svg");
    expect(svg).toHaveClass("lucide-moon");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("button", { name: "Tryb ciemny" })).toBeInTheDocument();
  });

  it("an icon without an animated form stays a static lucide icon", () => {
    stubMotion(false);
    const { container } = render(
      <button type="button" aria-label="Dalej">
        <AnimatedIcon name="arrow" />
      </button>,
    );
    expect(container.querySelector("svg")).toHaveClass("lucide-arrow-right");
  });

  it("does not fetch or start the animation before the person points at the control", () => {
    stubMotion(false);
    const { container } = render(
      <button type="button" aria-label="Odśwież">
        <AnimatedIcon name="refresh" />
      </button>,
    );
    // Static until first hover or focus; the animation library loads on demand.
    expect(container.querySelector("svg")).toHaveClass("lucide-refresh-cw");
  });

  it("swaps in the animated icon on first hover, and it stays decorative", async () => {
    stubMotion(false);
    const { container } = render(
      <button type="button" aria-label="Odśwież">
        <AnimatedIcon name="refresh" />
      </button>,
    );
    await userEvent.hover(screen.getByRole("button", { name: "Odśwież" }));
    await vi.waitFor(() => expect(container.querySelector("svg.lucide-refresh-cw")).toBeNull());
    const hidden = container.querySelector("[aria-hidden=true]");
    expect(hidden).not.toBeNull();
    expect(screen.getByRole("button", { name: "Odśwież" })).toBeInTheDocument();
  });
});
