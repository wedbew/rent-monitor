/**
 * The popup contract (docs/FRONTEND-PLAN.md section 4): every dialog, sheet, menu and popover must open from the
 * keyboard, put focus inside, keep Tab and Shift+Tab inside while modal, close on Escape, give focus back to its
 * trigger, have a name, and follow the backdrop policy registered for it.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { recordPopup } from "./coverage";

export interface DialogContract {
  readonly trigger: Locator;
  readonly dialog: Locator;
  readonly backdrop: "closes" | "stays";
  /** Registered popup id; the contract counts for the coverage gate when given. */
  readonly id?: string;
  /** Modal popups trap focus; a non-modal menu or popover only needs focus inside on open. */
  readonly modal?: boolean;
}

/**
 * Focus is in the popup. A native modal `<dialog>` makes the rest of the page inert, so when Tab runs off its last
 * control focus moves to the browser's own UI (document.body here): that cannot reach the page behind and counts
 * as inside. A custom popup has no such guarantee and must keep focus on its own controls.
 */
async function focusIsInside(dialog: Locator): Promise<boolean> {
  return dialog.evaluate((element) => {
    const active = document.activeElement;
    if (active !== null && element.contains(active)) return true;
    return element.matches(":modal") && (active === null || active === document.body);
  });
}

/**
 * A spot on the page that is outside the popup and not on anything a person could mean to press, so the click tests
 * "press outside" and not "press the menu button that happens to sit in the corner". A spot on plain page is
 * preferred. When the whole visible page is a focus target (`main`, which the skip link focuses, covers a phone
 * screen), a click there legitimately moves focus to that region; `takesFocus` says so and the caller accepts it.
 */
async function pointOutside(dialog: Locator): Promise<{ x: number; y: number; takesFocus: boolean }> {
  const point = await dialog.evaluate((popup) => {
    const interactive = "a, button, input, select, textarea, summary, label, [role=button], [role=link]";
    const width = window.innerWidth;
    const height = window.innerHeight;
    let fallback: { x: number; y: number; takesFocus: boolean } | null = null;
    for (let y = 6; y < height; y += 24) {
      for (let x = 6; x < width; x += 24) {
        const hit = document.elementFromPoint(x, y);
        if (hit === null || popup.contains(hit) || hit.closest(interactive) !== null) continue;
        if (hit.closest("[tabindex]") === null) return { x, y, takesFocus: false };
        fallback ??= { x, y, takesFocus: true };
      }
    }
    return fallback;
  });
  // A native modal dialog paints its backdrop as part of itself, so nothing "outside" is ever hit: any corner will do.
  return point ?? { x: 4, y: 4, takesFocus: false };
}

export async function expectDialogContract(page: Page, contract: DialogContract): Promise<void> {
  const { trigger, dialog, backdrop, modal = true } = contract;

  // Opens from the keyboard, not only the mouse.
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(dialog, "opens from the keyboard").toBeVisible();
  await expect(dialog, "has an accessible name").toHaveAccessibleName(/\S/);
  // Focus moves in once the popup has mounted: wait for it, as a person would, instead of sampling it once.
  await expect
    .poll(() => focusIsInside(dialog), { message: "initial focus is inside the popup", timeout: 2000 })
    .toBe(true);

  if (modal) {
    const stops =
      (await dialog
        .locator("a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])")
        .count()) + 2;
    for (let i = 0; i < stops; i += 1) {
      await page.keyboard.press("Tab");
      await expect
        .poll(() => focusIsInside(dialog), { message: `Tab ${i + 1} stays inside the popup`, timeout: 1500 })
        .toBe(true);
    }
    for (let i = 0; i < stops; i += 1) {
      await page.keyboard.press("Shift+Tab");
      await expect
        .poll(() => focusIsInside(dialog), {
          message: `Shift+Tab ${i + 1} stays inside the popup`,
          timeout: 1500,
        })
        .toBe(true);
    }
  }

  await page.keyboard.press("Escape");
  await expect(dialog, "Escape closes it").toBeHidden();
  await expect(trigger, "focus returns to the trigger").toBeFocused();

  // Backdrop policy: reopen, click outside the popup.
  await trigger.click();
  await expect(dialog).toBeVisible();
  // A popup ignores outside presses until its enter transition has started: wait for it like a person would.
  await expect(dialog).not.toHaveAttribute("data-starting-style", /.*/);
  const outside = await pointOutside(dialog);
  await page.mouse.click(outside.x, outside.y);
  if (backdrop === "closes") {
    await expect(dialog, "a click outside closes it").toBeHidden();
    if (outside.takesFocus) {
      // The press landed on a focus target (a region the page moves focus to): focus is there, not lost.
      await expect
        .poll(
          () =>
            page.evaluate(() => document.activeElement !== null && document.activeElement !== document.body),
          {
            message: "focus is on the pressed region, not lost",
          },
        )
        .toBe(true);
    } else {
      await expect(trigger, "focus returns to the trigger after the backdrop click").toBeFocused();
    }
  } else {
    await expect(dialog, "a click outside leaves it open").toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  }
  if (contract.id !== undefined) recordPopup(contract.id);
}
