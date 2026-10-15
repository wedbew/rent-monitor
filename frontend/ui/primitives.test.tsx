import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { Button, IconButton, LinkButton } from "./Button";
import { InlineNotice } from "./Status";

describe("Button", () => {
  it("is a native button with an explicit type", () => {
    render(<Button type="submit">Zapisz</Button>);
    expect(screen.getByRole("button", { name: "Zapisz" })).toHaveAttribute("type", "submit");
  });

  it("ignores clicks while busy, says so, and keeps its label (no layout jump)", async () => {
    const onClick = vi.fn();
    render(
      <Button type="button" busy onClick={onClick}>
        Kup pakiet
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Kup pakiet" });
    expect(button).toHaveAttribute("aria-busy", "true");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("does not click when disabled", async () => {
    const onClick = vi.fn();
    render(
      <Button type="button" disabled onClick={onClick}>
        Usuń
      </Button>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Usuń" }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("IconButton", () => {
  it("takes its accessible name from the label, never from the icon", () => {
    render(<IconButton type="button" label="Zamknij" icon="close" />);
    const button = screen.getByRole("button", { name: "Zamknij" });
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("LinkButton", () => {
  it("is a real link with a destination, not a button that navigates", () => {
    render(
      <MemoryRouter>
        <LinkButton to="/app/analyses" icon="arrow">
          Moje analizy
        </LinkButton>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Moje analizy" })).toHaveAttribute("href", "/app/analyses");
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("InlineNotice", () => {
  it("carries meaning in words and an icon, and only interrupts when asked to", () => {
    const { rerender } = render(
      <InlineNotice tone="danger" title="Błąd">
        Spróbuj ponownie.
      </InlineNotice>,
    );
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Błąd")).toBeInTheDocument();
    rerender(
      <InlineNotice tone="danger" title="Błąd" live="alert">
        Spróbuj ponownie.
      </InlineNotice>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Błąd");
  });
});
