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

export async function expectDialogContract(page: Page, contract: DialogContract): Promise<void> {
  const { trigger, dialog, backdrop, modal = true } = contract;

  // Opens from the keyboard, not only the mouse.
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(dialog, "opens from the keyboard").toBeVisible();
  await expect(dialog, "has an accessible name").toHaveAccessibleName(/\S/);
  expect(await focusIsInside(dialog), "initial focus is inside the popup").toBe(true);

  if (modal) {
    const stops =
      (await dialog
        .locator("a[href], button, input, select, textarea, [tabindex]:not([tabindex='-1'])")
        .count()) + 2;
    for (let i = 0; i < stops; i += 1) {
      await page.keyboard.press("Tab");
      expect(await focusIsInside(dialog), `Tab ${i + 1} stays inside the popup`).toBe(true);
    }
    for (let i = 0; i < stops; i += 1) {
      await page.keyboard.press("Shift+Tab");
      expect(await focusIsInside(dialog), `Shift+Tab ${i + 1} stays inside the popup`).toBe(true);
    }
  }

  await page.keyboard.press("Escape");
  await expect(dialog, "Escape closes it").toBeHidden();
  await expect(trigger, "focus returns to the trigger").toBeFocused();

  // Backdrop policy: reopen, click outside the popup.
  await trigger.click();
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  const outside =
    box === null || box.x > 24
      ? { x: 4, y: 4 }
      : { x: Math.min(box.x + box.width + 12, page.viewportSize()?.width ?? 1280) - 2, y: 4 };
  await page.mouse.click(outside.x, outside.y);
  if (backdrop === "closes") {
    await expect(dialog, "a click outside closes it").toBeHidden();
    await expect(trigger, "focus returns to the trigger after the backdrop click").toBeFocused();
  } else {
    await expect(dialog, "a click outside leaves it open").toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
  }
  if (contract.id !== undefined) recordPopup(contract.id);
}
