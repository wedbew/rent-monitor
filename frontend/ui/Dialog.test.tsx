import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRef, useState } from "react";
import { describe, expect, it } from "vitest";

import { Dialog } from "./Dialog";

/**
 * A dialog the app opens itself (an API answer, not a focused trigger) returns focus to `finalFocus` on close. In
 * Safari a clicked button never takes focus, so without it focus fell back to whatever had it before (RM-311).
 */
function Harness({ withFinalFocus }: { readonly withFinalFocus: boolean }) {
  const [open, setOpen] = useState(false);
  const target = useRef<HTMLButtonElement>(null);
  return (
    <>
      <input aria-label="pole" />
      <button ref={target} type="button">
        cel
      </button>
      <button type="button" onClick={() => setOpen(true)} tabIndex={-1}>
        otwórz
      </button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Okno"
        closeLabel="Zamknij okno"
        {...(withFinalFocus ? { finalFocus: target } : {})}
      >
        <p>treść</p>
      </Dialog>
    </>
  );
}

describe("Dialog finalFocus", () => {
  it("returns focus to the given element on close, whatever had focus before", async () => {
    const user = userEvent.setup();
    render(<Harness withFinalFocus />);
    screen.getByRole("textbox", { name: "pole" }).focus();
    await user.click(screen.getByRole("button", { name: "otwórz" }));
    await screen.findByRole("dialog", { name: "Okno" });
    await user.click(screen.getByRole("button", { name: "Zamknij okno" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "cel" })).toHaveFocus());
  });

  it("without it, focus goes back to where it was", async () => {
    const user = userEvent.setup();
    render(<Harness withFinalFocus={false} />);
    const field = screen.getByRole("textbox", { name: "pole" });
    field.focus();
    await user.click(screen.getByRole("button", { name: "otwórz" }));
    await screen.findByRole("dialog", { name: "Okno" });
    await user.click(screen.getByRole("button", { name: "Zamknij okno" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByRole("button", { name: "cel" })).not.toHaveFocus();
  });
});
