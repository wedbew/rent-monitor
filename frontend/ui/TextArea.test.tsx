import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { TextArea } from "./TextArea";

function Harness({ error }: { readonly error?: string }) {
  const [value, setValue] = useState("");
  return (
    <TextArea
      label="Notatka"
      hint="Tylko dla Ciebie"
      meta="0 z 10 znaków"
      value={value}
      onValueChange={setValue}
      error={error}
    />
  );
}

describe("TextArea", () => {
  it("is named by its label and described by the hint and the counter", () => {
    render(<Harness />);
    const field = screen.getByRole("textbox", { name: "Notatka" });
    expect(field).toHaveAccessibleDescription("Tylko dla Ciebie 0 z 10 znaków");
    expect(field).not.toHaveAttribute("aria-invalid");
  });

  it("passes what is typed to the caller, line breaks included, and keeps it", async () => {
    render(<Harness />);
    const field = screen.getByRole("textbox", { name: "Notatka" });
    await userEvent.type(field, "a{Enter}b");
    expect(field).toHaveValue("a\nb");
  });

  it("an error marks the field invalid and is part of its description", () => {
    render(<Harness error="Za długa" />);
    const field = screen.getByRole("textbox", { name: "Notatka" });
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(field).toHaveAccessibleDescription(/Za długa/);
  });
});
