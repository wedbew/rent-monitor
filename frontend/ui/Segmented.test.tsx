import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

const OPTIONS = [
  { value: "cards", label: "Karty", icon: "cards" },
  { value: "table", label: "Tabela", icon: "table" },
] as const;

describe("Segmented", () => {
  it("is a named group of buttons, and the current one says it is pressed", () => {
    render(<Segmented label="Widok" value="cards" options={OPTIONS} onValueChange={() => undefined} />);
    expect(screen.getByRole("group", { name: "Widok" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Karty" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Tabela" })).toHaveAttribute("aria-pressed", "false");
  });

  it("reports a new choice once, and nothing for the one already chosen", async () => {
    const onValueChange = vi.fn();
    render(<Segmented label="Widok" value="cards" options={OPTIONS} onValueChange={onValueChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Karty" }));
    expect(onValueChange).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Tabela" }));
    expect(onValueChange).toHaveBeenCalledExactlyOnceWith("table");
  });

  it("works from the keyboard", async () => {
    const onValueChange = vi.fn();
    render(<Segmented label="Widok" value="cards" options={OPTIONS} onValueChange={onValueChange} />);
    await userEvent.tab();
    await userEvent.tab();
    await userEvent.keyboard("{Enter}");
    expect(onValueChange).toHaveBeenCalledWith("table");
  });
});
