import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { InfoTip } from "./InfoTip";

function Harness() {
  return (
    <div>
      <span>Roczna stopa zwrotu</span>
      <InfoTip label="Co oznacza: roczna stopa zwrotu" title="IRR, czyli wewnętrzna stopa zwrotu">
        <p>Stała roczna stopa.</p>
      </InfoTip>
      <button type="button">Inny przycisk</button>
    </div>
  );
}

describe("InfoTip", () => {
  it("is a button named for what it explains, closed at first", () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Co oznacza: roczna stopa zwrotu" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Stała roczna stopa.")).toBeNull();
  });

  it("opens on click or tap with its title and text", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Co oznacza: roczna stopa zwrotu" }));
    expect(await screen.findByText("Stała roczna stopa.")).toBeVisible();
    expect(screen.getByText("IRR, czyli wewnętrzna stopa zwrotu")).toBeVisible();
  });

  it("opens from the keyboard with Enter or Space and closes on Escape, returning focus", async () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Co oznacza: roczna stopa zwrotu" });
    trigger.focus();
    await userEvent.keyboard("{Enter}");
    expect(await screen.findByText("Stała roczna stopa.")).toBeVisible();
    await userEvent.keyboard("{Escape}");
    await screen.findByRole("button", { name: "Co oznacza: roczna stopa zwrotu", expanded: false });
    expect(screen.queryByText("Stała roczna stopa.")).toBeNull();
    expect(trigger).toHaveFocus();
    await userEvent.keyboard(" ");
    expect(await screen.findByText("Stała roczna stopa.")).toBeVisible();
  });

  it("closes when the person presses outside it", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Co oznacza: roczna stopa zwrotu" }));
    await screen.findByText("Stała roczna stopa.");
    await userEvent.click(document.body);
    await screen.findByRole("button", { name: "Co oznacza: roczna stopa zwrotu", expanded: false });
  });

  it("keeps its icon decorative", () => {
    const { container } = render(<Harness />);
    expect(container.querySelector("button svg")).toHaveAttribute("aria-hidden", "true");
  });
});
