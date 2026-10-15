import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button busy", () => {
  it("does not submit its form while busy, on a click or on Enter in a field", () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <input aria-label="pole" />
        <Button type="submit" busy>
          Wyślij
        </Button>
      </form>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Wyślij" }));
    expect(onSubmit).not.toHaveBeenCalled();
    // Enter in a field is implicit submission: the browser clicks the default button, and that click is cancelled.
    const click = new MouseEvent("click", { bubbles: true, cancelable: true });
    screen.getByRole("button", { name: "Wyślij" }).dispatchEvent(click);
    expect(click.defaultPrevented).toBe(true);
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Wyślij" })).toHaveAttribute("aria-busy", "true");
  });

  it("submits normally when not busy", () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button type="submit">Wyślij</Button>
      </form>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Wyślij" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
