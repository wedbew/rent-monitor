/**
 * The app shell: navigation (rail on desktop, sheet on mobile), theme, skip link, 404, focus and layout rules.
 * Every shell element registered in e2e/interactions.ts is exercised here with an asserted outcome.
 */
import { LEGAL, PRIMARY } from "../shell/navigation";
import { exercise, outcome } from "./coverage";
import { expect, expectNoA11yViolations, test } from "./fixtures";

const DESTINATIONS = [...PRIMARY, ...LEGAL];
const startFor = (to: string) => (to === "/app/market" ? "/app" : "/app/market");

test.describe("desktop rail", () => {
  test.skip(({ isMobile }) => isMobile, "the rail exists on desktop only");

  for (const destination of DESTINATIONS) {
    test(`the "${destination.label}" link goes there, marks itself current and focuses the heading`, async ({
      page,
      serve,
    }) => {
      await serve("empty");
      await page.goto(startFor(destination.to));
      const link = page.getByRole("link", { name: destination.label, exact: true });
      await exercise(`shell.nav.${destination.id}`, async () => {
        await link.click();
        return [await outcome.url(page, new RegExp(`${destination.to}$`))];
      });
      await expect(link).toHaveAttribute("aria-current", "page");
      await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
      await expect(page).toHaveTitle(`${destination.label} · renti`);
      await expect(page.locator("[aria-current=page]")).toHaveCount(1);
    });
  }

  test("a report under /app/analyses/:id keeps 'Moje analizy' current, not 'Nowa analiza'", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app/analyses/00000000-0000-4000-8000-000000000001");
    await expect(page.getByRole("link", { name: "Moje analizy", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByRole("link", { name: "Nowa analiza", exact: true })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
    await page.goto("/app/analyses/new");
    await expect(page.getByRole("link", { name: "Nowa analiza", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.getByRole("link", { name: "Moje analizy", exact: true })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("hover changes the border colour but never the size or position of an item", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app");
    const item = page.getByRole("link", { name: "Rynek", exact: true });
    const before = await item.boundingBox();
    const colourBefore = await item.evaluate((el) => getComputedStyle(el).borderTopColor);
    await item.hover();
    const colourAfter = await item.evaluate((el) => getComputedStyle(el).borderTopColor);
    expect(await item.boundingBox()).toEqual(before);
    expect(colourAfter).not.toBe(colourBefore);
    expect(await item.evaluate((el) => getComputedStyle(el).borderTopWidth)).toBe("1px");
  });
});

test.describe("hover motion", () => {
  test.skip(({ isMobile }) => isMobile, "desktop rail");

  test.describe("by default (reduced motion is on in this suite)", () => {
    test("the icon does not animate", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/app");
      const link = page.getByRole("link", { name: "Rynek", exact: true });
      await link.hover();
      expect(
        await link
          .locator("span")
          .first()
          .evaluate((el) => getComputedStyle(el).animationDuration),
      ).toBe("0s");
    });
  });

  test.describe("with motion allowed", () => {
    test.use({ reducedMotion: "no-preference" });

    test("only the icon animates, briefly, on hover", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/app");
      const link = page.getByRole("link", { name: "Rynek", exact: true });
      const before = await link.boundingBox();
      await link.hover();
      const duration = await link
        .locator("span")
        .first()
        .evaluate((el) => getComputedStyle(el).animationDuration);
      expect(duration).toBe("0.24s");
      expect(await link.boundingBox()).toEqual(before);
    });
  });
});

test.describe("mobile sheet", () => {
  test.skip(({ isMobile }) => !isMobile, "the sheet exists on mobile only");

  test("the Menu button opens the sheet", async ({ page, serve }) => {
    await serve("empty");
    await page.goto("/app");
    await exercise("shell.menu", async () => {
      await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
      return [await outcome.dialog(page.getByRole("dialog", { name: "Nawigacja" }), "open")];
    });
  });

  test("the close button closes it and focus returns to the Menu button", async ({ page, serve }) => {
    await serve("empty");
    await page.goto("/app");
    const trigger = page.getByRole("button", { name: "Otwórz menu nawigacji" });
    await trigger.click();
    const dialog = page.getByRole("dialog", { name: "Nawigacja" });
    await exercise("shell.menu.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij nawigację" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await expect(trigger).toBeFocused();
  });

  for (const destination of DESTINATIONS) {
    test(`following "${destination.label}" closes the sheet and focuses the new heading`, async ({
      page,
      serve,
    }) => {
      await serve("empty");
      await page.goto(startFor(destination.to));
      await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
      const dialog = page.getByRole("dialog", { name: "Nawigacja" });
      await exercise(`shell.menu.nav.${destination.id}`, async () => {
        await dialog.getByRole("link", { name: destination.label, exact: true }).click();
        return [await outcome.url(page, new RegExp(`${destination.to}$`))];
      });
      await expect(dialog).toBeHidden();
      await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
      await expect(page).toHaveTitle(`${destination.label} · renti`);
    });
  }

  test("the sheet marks the current page", async ({ page, serve }) => {
    await serve("empty");
    await page.goto("/app/analyses/00000000-0000-4000-8000-000000000001");
    await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
    const dialog = page.getByRole("dialog", { name: "Nawigacja" });
    await expect(dialog.getByRole("link", { name: "Moje analizy", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });
});

test.describe("theme", () => {
  test.describe("first visit with a dark system preference", () => {
    test.use({ colorScheme: "dark" });

    test("is still light", async ({ page, serve }) => {
      await serve("empty");
      await page.goto("/app");
      await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
      expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(
        "rgb(245, 247, 244)",
      );
    });
  });

  test("the control names the mode it switches to, switches it, and the choice persists", async ({
    page,
    serve,
  }) => {
    await serve("empty");
    await page.goto("/app");
    const toDark = page.getByRole("button", { name: "Tryb ciemny" });
    await exercise("shell.theme", async () => {
      await toDark.click();
      return [await outcome.state(page.locator("html"), "data-theme", "dark")];
    });
    await expect(page.getByRole("button", { name: "Tryb jasny" })).toBeVisible();
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await page.getByRole("button", { name: "Tryb jasny" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("an unknown stored value falls back to light", async ({ page, serve }) => {
    await serve("empty");
    await page.addInitScript(() => localStorage.setItem("renti-theme", "sepia"));
    await page.goto("/app");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });

  test("blocked storage does not break rendering or the toggle", async ({ page, serve }) => {
    await serve("empty");
    await page.addInitScript(() => {
      Object.defineProperty(window, "localStorage", {
        get() {
          throw new DOMException("blocked", "SecurityError");
        },
      });
    });
    await page.goto("/app");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.getByRole("button", { name: "Tryb ciemny" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
  });
});

test("the skip link is the first stop and moves focus to the main region", async ({ page, serve }) => {
  await serve("empty");
  await page.goto("/app");
  await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
  const skip = page.getByRole("link", { name: "Przejdź do treści" });
  await exercise("shell.skip", async () => {
    await page.keyboard.press("Tab");
    return [await outcome.focus(skip)];
  });
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});

test("the brand link goes to the dashboard from anywhere", async ({ page, serve }) => {
  await serve("empty");
  await page.goto("/app/market");
  await exercise("shell.brand", async () => {
    await page.getByRole("link", { name: "renti.tech, przejdź do pulpitu" }).click();
    return [await outcome.url(page, /\/app$/)];
  });
  await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
});

test("an unknown path keeps the shell, says so, and leads back", async ({ page, serve }) => {
  await serve("empty");
  await page.goto("/nie-ma-takiej-strony");
  await expect(page.getByRole("heading", { level: 1, name: "Nie znaleziono strony" })).toBeVisible();
  await expect(page).toHaveTitle("Nie znaleziono strony · renti");
  await exercise("not-found.home", async () => {
    await page.getByRole("link", { name: "Wróć do pulpitu" }).click();
    return [await outcome.url(page, /\/app$/)];
  });
});

test("/ redirects to the dashboard", async ({ page, serve }) => {
  await serve("empty");
  await page.goto("/");
  await expect(page).toHaveURL(/\/app$/);
});

test.describe("layout", () => {
  for (const width of [320, 390, 640, 1280]) {
    test(`no page scrolls horizontally at ${width} px (320 px reflow, 200 % zoom)`, async ({
      page,
      serve,
    }) => {
      await serve("empty");
      await page.setViewportSize({ width, height: 700 });
      for (const path of ["/app", "/app/analyses", "/terms", "/nie-ma-takiej-strony"]) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow, `${path} at ${width}px`).toBeLessThanOrEqual(0);
      }
    });
  }
});

test.describe("contrast and accessibility in both themes", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`axe is clean on the shell and the 404 page in the ${theme} theme`, async ({
      page,
      serve,
      isMobile,
    }) => {
      await serve("empty");
      await page.addInitScript((value) => localStorage.setItem("renti-theme", value), theme);
      for (const path of ["/app", "/app/market", "/nie-ma-takiej-strony"]) {
        await page.goto(path);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await expectNoA11yViolations(page);
      }
      if (isMobile) {
        await page.getByRole("button", { name: "Otwórz menu nawigacji" }).click();
        await expect(page.getByRole("dialog", { name: "Nawigacja" })).toBeVisible();
        await expectNoA11yViolations(page, "[role=dialog]");
      }
    });
  }
});
