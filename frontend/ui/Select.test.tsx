import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Select } from "./Select";

const OPTIONS = [
  { value: "", label: "Wszystkie" },
  { value: "ready", label: "Gotowe" },
  { value: "active", label: "W toku" },
  { value: "failed", label: "Nieudane" },
];

function Harness({
  onChange = () => undefined,
  error,
  disabled,
}: {
  onChange?: (v: string) => void;
  error?: string;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  return (
    <>
      <Select
        label="Status"
        value={value}
        options={OPTIONS}
        error={error}
        disabled={disabled ?? false}
        onValueChange={(v) => {
          setValue(v);
          onChange(v);
        }}
      />
      <button type="button">Dalej</button>
    </>
  );
}

describe("Select", () => {
  it("is a labelled combobox that shows the chosen option's label, not its value", () => {
    render(<Harness />);
    const trigger = screen.getByRole("combobox", { name: "Status" });
    expect(trigger).toHaveTextContent("Wszystkie");
  });

  it("opens a styled listbox on click, selects by click, closes and keeps the choice", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.click(screen.getByRole("combobox", { name: "Status" }));
    const list = await screen.findByRole("listbox");
    expect(list).toBeInTheDocument();
    expect(screen.getAllByRole("option")).toHaveLength(4);
    await userEvent.click(screen.getByRole("option", { name: "Gotowe" }));
    expect(onChange).toHaveBeenCalledWith("ready");
    await vi.waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
    expect(screen.getByRole("combobox", { name: "Status" })).toHaveTextContent("Gotowe");
  });

  it("works from the keyboard: arrows move, Enter selects, focus returns to the trigger", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "Status" });
    trigger.focus();
    await userEvent.keyboard("{ArrowDown}");
    await screen.findByRole("listbox");
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenCalledTimes(1);
    await vi.waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
    expect(trigger).toHaveFocus();
  });

  it("Escape closes without changing the value and returns focus to the trigger", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    const trigger = screen.getByRole("combobox", { name: "Status" });
    await userEvent.click(trigger);
    await screen.findByRole("listbox");
    await userEvent.keyboard("{Escape}");
    await vi.waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
    expect(onChange).not.toHaveBeenCalled();
    expect(trigger).toHaveFocus();
  });

  it("typeahead moves to the option that starts with the typed letters", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.click(screen.getByRole("combobox", { name: "Status" }));
    const list = await screen.findByRole("listbox");
    // Typeahead listens once focus has moved into the list: wait for that, as a person would.
    await vi.waitFor(() => expect(list.contains(document.activeElement)).toBe(true));
    await userEvent.keyboard("Ni");
    await vi.waitFor(() =>
      expect(screen.getByRole("option", { name: "Nieudane" })).toHaveAttribute("data-highlighted"),
    );
    await userEvent.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith("failed");
  });

  it("marks the selected option and says so to assistive technology", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("combobox", { name: "Status" }));
    await screen.findByRole("listbox");
    expect(screen.getByRole("option", { name: "Wszystkie" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("option", { name: "Gotowe" })).toHaveAttribute("aria-selected", "false");
  });

  it("an error marks the field invalid, is announced with it, and is not colour alone", () => {
    render(<Harness error="Wybierz status." />);
    const trigger = screen.getByRole("combobox", { name: "Status" });
    expect(trigger).toHaveAttribute("aria-invalid", "true");
    expect(trigger).toHaveAccessibleDescription(/Wybierz status\./);
    expect(screen.getByText("Wybierz status.")).toBeVisible();
    expect(screen.getByText("Błąd:", { exact: false })).toBeInTheDocument();
  });

  it("a disabled select does not open", async () => {
    render(<Harness disabled />);
    const trigger = screen.getByRole("combobox", { name: "Status" });
    await userEvent.click(trigger);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("the popup is portalled out of its container, so no scrolling parent can clip it", async () => {
    const { container } = render(
      <div style={{ overflow: "hidden", height: 40 }}>
        <Harness />
      </div>,
    );
    await userEvent.click(screen.getByRole("combobox", { name: "Status" }));
    const list = await screen.findByRole("listbox");
    expect(container.contains(list)).toBe(false);
  });
});
