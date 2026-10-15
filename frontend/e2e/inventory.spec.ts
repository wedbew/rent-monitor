import { expect, type Page } from "@playwright/test";

import { expectNoA11yViolations, test } from "./fixtures";
import { exercise } from "./coverage";
import { EVERY_PAGE, EVERY_PUBLIC_PAGE, INTERACTIONS, PAGES, POPUPS, type Viewport } from "./interactions";
import { inventory } from "./inventory";
import { expectDialogContract } from "./popups";

const viewportOf = (page: Page): Viewport =>
  (page.viewportSize()?.width ?? 1280) <= 760 ? "mobile" : "desktop";

async function checkPopups(
  page: Page,
  appPage: (typeof PAGES)[number],
  scenario: string,
  viewport: Viewport,
  popups: readonly (typeof POPUPS)[number][],
  state?: string,
): Promise<void> {
  for (const popup of popups) {
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
      (
        await inventory(
          page,
          {
            page: appPage.id,
            scenario,
            viewport,
            layout: appPage.layout ?? "app",
            within: popup.id,
            ...(state !== undefined ? { state } : {}),
          },
          INTERACTIONS,
          dialog,
        )
      ).map((v) => v.message),
    ).toEqual([]);
    await expectNoA11yViolations(page, "[role=dialog], [role=alertdialog], [role=menu], [role=listbox]");
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expectDialogContract(page, {
      id: popup.id,
      trigger: triggerLocator,
      dialog,
      backdrop: popup.backdrop,
      modal: popup.modal ?? true,
    });
  }
}

for (const appPage of PAGES) {
  for (const scenario of appPage.scenarios) {
    test(`${appPage.id} / ${scenario}: every interactive element is named and registered, and axe is clean`, async ({
      page,
      serve,
    }) => {
      const viewport = viewportOf(page);
      await serve(scenario);
      await page.goto(appPage.path);
      await expect(page.getByRole("heading", { level: 1, name: appPage.heading })).toBeVisible();
      await expect(
        page.locator("[aria-busy=true]"),
        "loading regions settle before the inventory",
      ).toHaveCount(0);

      expect(
        (
          await inventory(page, { page: appPage.id, scenario, viewport, layout: appPage.layout ?? "app" })
        ).map((v) => v.message),
      ).toEqual([]);
      await expectNoA11yViolations(page);

      await checkPopups(
        page,
        appPage,
        scenario,
        viewport,
        POPUPS.filter(
          (p) =>
            p.state === undefined &&
            (p.page === appPage.id || (p.page === EVERY_PAGE && appPage === PAGES[0])) &&
            (p.viewport === undefined || p.viewport === viewport) &&
            (p.scenarios === undefined || p.scenarios.includes(scenario)),
        ),
      );
    });
  }
}

for (const appPage of PAGES) {
  for (const pageState of appPage.states ?? []) {
    test(`${appPage.id} / ${pageState.name}: every interactive element is named and registered, and axe is clean`, async ({
      page,
      serve,
    }) => {
      const viewport = viewportOf(page);
      await serve(typeof pageState.scenario === "string" ? pageState.scenario : pageState.scenario());
      await page.goto(pageState.path ?? appPage.path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await pageState.prepare(page);
      await expect(page.locator("[aria-busy=true]")).toHaveCount(0);
      const scope = {
        page: appPage.id,
        scenario: String(pageState.scenario),
        viewport,
        layout: appPage.layout ?? "app",
        state: pageState.name,
      };
      expect((await inventory(page, scope)).map((v) => v.message)).toEqual([]);
      await expectNoA11yViolations(page);
      await checkPopups(
        page,
        appPage,
        String(pageState.scenario),
        viewport,
        POPUPS.filter(
          (p) =>
            p.page === appPage.id &&
            p.state === pageState.name &&
            (p.viewport === undefined || p.viewport === viewport),
        ),
        pageState.name,
      );
    });
  }
}

test("the registry only names pages, popups and triggers that exist", () => {
  const pages = new Set(PAGES.map((p) => p.id));
  const ids = INTERACTIONS.map((i) => i.id);
  expect(new Set(ids).size, "interaction ids are unique").toBe(ids.length);
  const known = (page: string) => page === EVERY_PAGE || page === EVERY_PUBLIC_PAGE || pages.has(page);
  expect(
    INTERACTIONS.filter((i) => !known(i.page)).map((i) => i.id),
    "interactions on unknown pages",
  ).toEqual([]);
  expect(
    POPUPS.filter((p) => !known(p.page)).map((p) => p.id),
    "popups on unknown pages",
  ).toEqual([]);
  expect(
    POPUPS.filter((p) => !ids.includes(p.trigger)).map((p) => p.id),
    "popups with an unregistered trigger",
  ).toEqual([]);
  const stateNames = new Set(PAGES.flatMap((p) => (p.states ?? []).map((s) => `${p.id}:${s.name}`)));
  expect(
    INTERACTIONS.filter(
      (i) =>
        i.state !== undefined &&
        i.page !== EVERY_PAGE &&
        i.page !== EVERY_PUBLIC_PAGE &&
        !stateNames.has(`${i.page}:${i.state}`),
    ).map((i) => i.id),
    "elements in unknown page states",
  ).toEqual([]);
  expect(
    POPUPS.filter((p) => p.state !== undefined && !stateNames.has(`${p.page}:${p.state}`)).map((p) => p.id),
    "popups in unknown page states",
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
