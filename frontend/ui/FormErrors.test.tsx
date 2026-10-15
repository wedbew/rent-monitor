import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { FormErrorSummary } from "./FormErrors";

describe("FormErrorSummary", () => {
  it("one problem is a single compact alert that names it and links to the field", async () => {
    render(
      <>
        <input id="ref" aria-label="Adres" />
        <FormErrorSummary attempt={1} errors={[{ fieldId: "ref", message: "Wklej adres ogłoszenia." }]} />
      </>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).toHaveTextContent("Popraw 1 pole");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    await userEvent.click(screen.getByRole("link", { name: "Wklej adres ogłoszenia." }));
    expect(screen.getByLabelText("Adres")).toHaveFocus();
  });

  it("several problems are a list with a count, and typing does not steal focus back", () => {
    const { rerender } = render(
      <>
        <input aria-label="Pole" />
        <FormErrorSummary
          attempt={1}
          errors={[
            { fieldId: "a", message: "A jest wymagane." },
            { fieldId: "b", message: "B jest wymagane." },
          ]}
        />
      </>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Popraw pola: 2");
    expect(screen.getAllByRole("link")).toHaveLength(2);
    screen.getByLabelText("Pole").focus();
    rerender(
      <>
        <input aria-label="Pole" />
        <FormErrorSummary attempt={1} errors={[{ fieldId: "b", message: "B jest wymagane." }]} />
      </>,
    );
    expect(screen.getByLabelText("Pole")).toHaveFocus();
  });

  it("renders nothing when there is nothing to fix", () => {
    render(<FormErrorSummary attempt={3} errors={[]} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
