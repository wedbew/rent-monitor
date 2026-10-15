import { expect } from "@playwright/test";

import { expectNoA11yViolations, test } from "./fixtures";
import { exercise } from "./coverage";
import { INTERACTIONS, PAGES, POPUPS } from "./interactions";
import { inventory } from "./inventory";
import { expectDialogContract } from "./popups";

for (const appPage of PAGES) {
  for (const scenario of appPage.scenarios) {
    test(`${appPage.id} / ${scenario}: every interactive element is named and registered, and axe is clean`, async ({
      page,
      serve,
    }) => {
      await serve(scenario);
      await page.goto(appPage.path);
      await expect(page.getByRole("heading", { level: 1, name: appPage.heading })).toBeVisible();

      expect((await inventory(page, { page: appPage.id, scenario })).map((v) => v.message)).toEqual([]);
      await expectNoA11yViolations(page);

      for (const popup of POPUPS.filter(
        (p) => p.page === appPage.id && (p.scenarios === undefined || p.scenarios.includes(scenario)),
      )) {
        const trigger = INTERACTIONS.find((i) => i.id === popup.trigger);
        if (trigger === undefined)
          throw new Error(`popup ${popup.id}: trigger ${popup.trigger} is not registered`);
        const triggerLocator = page.getByRole(trigger.role, {
          name: trigger.name,
          exact: typeof trigger.name === "string",
        });
        const dialog = page.getByRole(popup.role, { name: popup.name });
        await triggerLocator.click();
        await expect(dialog).toBeVisible();
        expect(
          (await inventory(page, { page: appPage.id, scenario, within: popup.id }, INTERACTIONS, dialog)).map(
            (v) => v.message,
          ),
        ).toEqual([]);
        await expectNoA11yViolations(page, "[role=dialog], [role=alertdialog], [role=menu], [role=listbox]");
        await page.keyboard.press("Escape");
        await expectDialogContract(page, {
          id: popup.id,
          trigger: triggerLocator,
          dialog,
          backdrop: popup.backdrop,
        });
      }
    });
  }
}

test("the registry only names pages, popups and triggers that exist", () => {
  const pages = new Set(PAGES.map((p) => p.id));
  const ids = INTERACTIONS.map((i) => i.id);
  expect(new Set(ids).size, "interaction ids are unique").toBe(ids.length);
  expect(
    INTERACTIONS.filter((i) => !pages.has(i.page)).map((i) => i.id),
    "interactions on unknown pages",
  ).toEqual([]);
  expect(
    POPUPS.filter((p) => !pages.has(p.page)).map((p) => p.id),
    "popups on unknown pages",
  ).toEqual([]);
  expect(
    POPUPS.filter((p) => !ids.includes(p.trigger)).map((p) => p.id),
    "popups with an unregistered trigger",
  ).toEqual([]);
  const popupIds = new Set(POPUPS.map((p) => p.id));
  expect(
    INTERACTIONS.filter((i) => i.within !== undefined && !popupIds.has(i.within)).map((i) => i.id),
    "elements in unknown popups",
  ).toEqual([]);
  expect([...new Set(PAGES.map((p) => p.path))].length, "page paths are unique").toBe(PAGES.length);
});

test("exercise() refuses an id that is not registered", async () => {
  await expect(exercise("no.such.thing", () => Promise.resolve({ kind: "url" }))).rejects.toThrow(
    "not registered",
  );
});
