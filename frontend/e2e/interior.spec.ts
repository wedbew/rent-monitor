import type { Locator, Page } from "@playwright/test";

import { createInterior } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, expectNoA11yViolations, test } from "./fixtures";
import { expectDialogContract } from "./popups";

/** The seeded project of every `createInterior` flow (the first id the fake server hands out). */
const PROJECT = "00000000-0000-4000-8000-000000000901";
const WORKSPACE = `/app/interior/${PROJECT}`;
/** The fake server accepts a file whose text starts with FAKEIMG as a photo; anything else is "not an image". */
const photo = (text = "FAKEIMG pokoj") => ({
  name: "pokoj.jpg",
  mimeType: "image/jpeg",
  buffer: Buffer.from(text),
});

async function choose(select: Locator, label: string): Promise<void> {
  await select.click();
  await select.page().getByRole("option", { name: label, exact: true }).click();
}

async function openWorkspace(page: Page) {
  await page.goto(WORKSPACE);
  await expect(page.getByRole("heading", { level: 1, name: "Salon" })).toBeVisible();
  await page.getByRole("button", { name: "Pokaż wszystkie narzędzia" }).click();
}

const section = (page: Page, name: string) => page.getByRole("region", { name });

test.describe("guided interior workspace", () => {
  test("numbered stepper is compact on phones and aligned vertically on desktop", async ({
    page,
    serve,
  }, testInfo) => {
    await serve(createInterior({ rich: true }));
    for (const width of [320, 390, 1280]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(`${WORKSPACE}?step=brief`);
      const nav = page.getByRole("navigation", { name: "Etapy projektu" });
      await expect(page.getByRole("heading", { name: "Jak chcesz się tu czuć?" })).toBeVisible();
      const buttons = nav.getByRole("button");
      await expect(buttons).toHaveCount(4);
      const dots = [];
      for (let i = 0; i < 4; i += 1) {
        const dot = buttons.nth(i).locator("span").first();
        await expect(dot).toHaveText(String(i + 1));
        const bounds = await dot.boundingBox();
        expect(bounds).not.toBeNull();
        dots.push(bounds);
      }
      await expect(buttons.nth(1)).toHaveAttribute("aria-current", "step");
      if (width < 761) {
        expect((await nav.locator("..").boundingBox())?.height).toBeLessThanOrEqual(160);
        expect(new Set(dots.map((dot) => dot?.y)).size).toBe(1);
      } else {
        expect(new Set(dots.map((dot) => dot?.x)).size).toBe(1);
        expect(dots[3]?.y).toBeGreaterThan(dots[0]?.y ?? 0);
      }
      await page.screenshot({
        path: testInfo.outputPath(`stepper-light-${String(width)}.png`),
        fullPage: true,
      });
      await page.getByRole("button", { name: "Tryb ciemny" }).click();
      await page.screenshot({
        path: testInfo.outputPath(`stepper-dark-${String(width)}.png`),
        fullPage: true,
      });
      await page.getByRole("button", { name: "Tryb jasny" }).click();
    }
  });

  test("mobile wizard fills the viewport with one small content gutter", async ({ page, serve }) => {
    await serve(createInterior({ rich: true }));
    for (const width of [320, 390, 640, 760]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto(`${WORKSPACE}?step=brief`);
      await expect(page.getByRole("heading", { name: "Jak chcesz się tu czuć?" })).toBeVisible();
      const wizard = await page.getByRole("navigation", { name: "Etapy projektu" }).evaluate((nav) => {
        const rect = nav.parentElement?.parentElement?.getBoundingClientRect();
        return rect ? { left: rect.left, right: rect.right } : null;
      });
      expect(wizard?.left).toBe(0);
      expect(wizard?.right).toBe(width);
      const field = page.getByRole("textbox", { name: "Nazwa projektu", exact: true });
      const assertGutter = async () => {
        const rect = await field.boundingBox();
        expect(rect?.x).toBeLessThanOrEqual(12);
        expect((rect?.x ?? 0) + (rect?.width ?? 0)).toBeGreaterThanOrEqual(width - 12);
        expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      };
      await assertGutter();
      await page.getByRole("button", { name: "Pokaż wszystkie narzędzia" }).click();
      await assertGutter();
    }
  });

  test("keyboard steps, style choices, saved drafts and optional full view", async ({ page, serve }) => {
    const api = await serve(createInterior({ rich: true }));
    await page.goto(WORKSPACE);
    await expect(section(page, "Zdjęcie pokoju")).toBeVisible();
    await expect(section(page, "Założenia")).toBeHidden();
    await exercise("interior.wizard.previous-photo", async () => {
      await expect(page.getByRole("button", { name: "Wstecz" })).toBeDisabled();
      return outcome.state(page.getByRole("button", { name: "Wstecz" }), "disabled", "");
    });
    await exercise("interior.wizard.next", async () => {
      await page.getByRole("button", { name: "Dalej" }).focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("heading", { name: "Jak chcesz się tu czuć?" })).toBeFocused();
      return outcome.text(
        page.getByRole("heading", { name: "Jak chcesz się tu czuć?" }),
        "Jak chcesz się tu czuć?",
      );
    });
    await choose(page.getByRole("combobox", { name: "Styl", exact: true }), "Własny styl");
    await page.getByRole("textbox", { name: "Nazwa własnego stylu" }).fill("loft z zielenią");
    await expect(page.getByRole("button", { name: "Dalej" })).toBeDisabled();
    await page.getByRole("button", { name: /Krok 4/ }).click();
    await expect(page.getByRole("button", { name: "Zapisz wersję", exact: true })).toBeDisabled();
    await page.getByRole("button", { name: /Krok 2/ }).click();
    await expect(page.getByRole("textbox", { name: "Nazwa własnego stylu" })).toHaveValue("loft z zielenią");
    await page.getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Założenia zapisane.")).toBeVisible();
    await exercise("interior.wizard.next-brief", async () => {
      await page.getByRole("button", { name: "Dalej" }).click();
      return outcome.text(
        page.getByRole("heading", { name: "Zrób miejsce na swoje pomysły." }),
        "Zrób miejsce na swoje pomysły.",
      );
    });
    await exercise("interior.wizard.previous-furniture", async () => {
      await page.getByRole("button", { name: "Wstecz" }).click();
      return outcome.text(
        page.getByRole("heading", { name: "Jak chcesz się tu czuć?" }),
        "Jak chcesz się tu czuć?",
      );
    });
    for (const [step, heading] of [
      [1, "Zacznij od tego, co masz."],
      [2, "Jak chcesz się tu czuć?"],
      [3, "Zrób miejsce na swoje pomysły."],
      [4, "Zobacz nową perspektywę."],
    ] as const) {
      await exercise(`interior.wizard.step${step}`, async () => {
        await page.getByRole("button", { name: new RegExp(`^Krok ${String(step)}`) }).click();
        return outcome.text(page.getByRole("heading", { name: heading }), heading);
      });
    }
    await expect(page.getByRole("button", { name: "Zapisz wersję", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: /Krok 2/ }).click();
    await exercise("interior.wizard.previous", async () => {
      await page.getByRole("button", { name: "Wstecz" }).click();
      return outcome.text(
        page.getByRole("heading", { name: "Zacznij od tego, co masz." }),
        "Zacznij od tego, co masz.",
      );
    });
    await page.getByRole("button", { name: /Krok 3/ }).click();
    await exercise("interior.wizard.review", async () => {
      await page.getByRole("button", { name: "Przejdź do podsumowania" }).click();
      return outcome.text(
        page.getByRole("heading", { name: "Zobacz nową perspektywę." }),
        "Zobacz nową perspektywę.",
      );
    });
    await exercise("interior.wizard.all", async () => {
      const toggle = page.getByRole("button", { name: "Pokaż wszystkie narzędzia" });
      await toggle.click();
      await expect(section(page, "Założenia")).toBeVisible();
      return outcome.state(toggle, "aria-pressed", "true");
    });
    await page.reload();
    await expect(page.getByRole("textbox", { name: "Nazwa własnego stylu" })).toHaveValue("loft z zielenią");
    await page.getByRole("button", { name: "Pokaż wszystkie narzędzia" }).click();
    await expect(section(page, "Założenia")).toBeHidden();
    await expect(section(page, "Wersje")).toBeVisible();
    expect(api.requests.filter((r) => r.method === "POST")).toHaveLength(0);
  });
});

test.describe("the project list", () => {
  test("creates a project from a name and a room and opens it", async ({ page, serve }) => {
    const flow = createInterior({ seeded: false });
    const api = await serve(flow);
    await page.goto("/app/interior");
    await expect(page.getByText("Nie masz jeszcze projektu")).toBeVisible();
    await page.getByRole("button", { name: "Utwórz projekt" }).click();
    await expect(page.getByText("Wpisz nazwę projektu.").first()).toBeVisible();
    expect(api.requests.filter((r) => r.method === "POST")).toEqual([]);
    const name = page.getByRole("textbox", { name: "Nazwa projektu" });
    await exercise("interior.list.name", async () => {
      await name.fill("Sypialnia");
      return [await outcome.value(name, "Sypialnia")];
    });
    const room = page.getByRole("combobox", { name: "Rodzaj pokoju" });
    await exercise("interior.list.room", async () => {
      await choose(room, "Sypialnia");
      return [await outcome.text(room, "Sypialnia")];
    });
    await exercise("interior.list.create", async () => {
      await page.getByRole("button", { name: "Utwórz projekt" }).click();
      return [await outcome.url(page, /\/app\/interior\/[0-9a-f-]{36}$/)];
    });
    await expect(page.getByRole("heading", { level: 1, name: "Sypialnia" })).toBeVisible();
    expect([...flow.projects.values()].map((p) => [p.name, p.brief.room_type])).toEqual([
      ["Sypialnia", "bedroom"],
    ]);
  });

  test("lists projects with expiry and opens one", async ({ page, serve }) => {
    await serve(createInterior({ rich: true }));
    await page.goto("/app/interior");
    const card = page.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "Salon" }) });
    await expect(card.getByText("Ze zdjęciem pokoju")).toBeVisible();
    await expect(card.getByText(/^Wygasa /)).toBeVisible();
    await exercise("interior.list.open", async () => {
      await page.getByRole("link", { name: "Otwórz projekt Salon" }).click();
      return [await outcome.url(page, new RegExp(`${WORKSPACE}$`))];
    });
  });

  test("deleting asks first: close and cancel keep the project, confirming removes it", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await page.goto("/app/interior");
    const trigger = page.getByRole("button", { name: "Usuń projekt Salon" });
    const dialog = page.getByRole("dialog", { name: "Usunąć projekt?" });
    await expectDialogContract(page, {
      id: "interior.delete",
      trigger,
      dialog,
      backdrop: "closes",
      modal: true,
    });
    await exercise("interior.list.delete", async () => {
      await trigger.click();
      return [await outcome.dialog(dialog, "open")];
    });
    await exercise("interior.delete.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await trigger.click();
    await exercise("interior.delete.cancel", async () => {
      await dialog.getByRole("button", { name: "Anuluj" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    expect(flow.projects.size).toBe(1);
    await trigger.click();
    await exercise("interior.delete.confirm", async () => {
      await dialog.getByRole("button", { name: "Usuń projekt", exact: true }).click();
      await expect(page.getByText("Nie masz jeszcze projektu")).toBeVisible();
      return [await outcome.request(api, { method: "DELETE", path: `/api/interior/projects/${PROJECT}` })];
    });
    expect(flow.projects.size).toBe(0);
  });

  test("outside the closed beta the page says so and offers nothing to create", async ({ page, serve }) => {
    await serve("interiorClosed");
    await page.goto("/app/interior");
    await expect(page.getByText("Architekt wnętrz jest w zamkniętej wersji beta")).toBeVisible();
    await expect(page.getByRole("button", { name: "Utwórz projekt" })).toHaveCount(0);
  });

  test("a project that is not the person's is not found", async ({ page, serve }) => {
    await serve(createInterior({ rich: true }));
    await page.goto("/app/interior/00000000-0000-4000-8000-0000000009ff");
    await expect(page.getByText("Nie ma takiego projektu albo wygasł.")).toBeVisible();
    await page.goto("/app/interior/not-a-project");
    await expect(page.getByText("Nie ma takiego projektu albo wygasł.")).toBeVisible();
  });
});

test.describe("the room photo", () => {
  test("uploads a photo through the file chooser and refuses a file that is not an image", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const before = flow.projects.get(PROJECT)?.source?.media_id;
    await exercise("interior.project.photo", async () => {
      const chooser = page.waitForEvent("filechooser");
      await page.getByRole("button", { name: "Wybierz zdjęcie pokoju" }).click();
      await (await chooser).setFiles(photo("to nie jest zdjęcie"));
      await expect(page.getByText("Nie udało się odczytać tego pliku jako zdjęcia.")).toBeVisible();
      return [
        await outcome.request(api, { method: "POST", path: `/api/interior/projects/${PROJECT}/source` }),
      ];
    });
    expect(flow.projects.get(PROJECT)?.source?.media_id).toBe(before);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Wybierz zdjęcie pokoju" }).click();
    await (await chooser).setFiles(photo());
    await expect.poll(() => flow.projects.get(PROJECT)?.source?.media_id).not.toBe(before);
    await expect(
      page.getByRole("img", { name: "Zdjęcie pokoju, z którego powstaje wizualizacja" }),
    ).toBeVisible();
  });

  test("when storage is down the project stays and the person is told", async ({ page, serve }) => {
    await serve(createInterior({ rich: true, storageDown: true }));
    await openWorkspace(page);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Wybierz zdjęcie pokoju" }).click();
    await (await chooser).setFiles(photo());
    await expect(page.getByText("Zdjęcia są chwilowo niedostępne")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Salon" })).toBeVisible();
  });

  test("a file over 10 MB is refused in the browser, nothing is sent", async ({ page, serve }) => {
    const api = await serve(createInterior({ rich: true }));
    await openWorkspace(page);
    const chooser = page.waitForEvent("filechooser");
    await page.getByRole("button", { name: "Wybierz zdjęcie pokoju" }).click();
    await (
      await chooser
    ).setFiles({ name: "duze.jpg", mimeType: "image/jpeg", buffer: Buffer.alloc(10 * 1024 * 1024 + 1) });
    await expect(page.getByText("Plik jest większy niż 10 MB.").first()).toBeVisible();
    expect(api.requests.filter((r) => r.path.endsWith("/source"))).toEqual([]);
  });
});

test.describe("the brief", () => {
  test("all suggested styles save their value and a legacy custom style stays editable", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const project = flow.projects.get(PROJECT);
    if (project === undefined) throw new Error("missing seeded project");
    flow.projects.set(PROJECT, { ...project, brief: { ...project.brief, style: "Moja autorska mieszanka" } });
    const api = await serve(flow);
    await page.goto(`${WORKSPACE}?step=brief`);
    const style = page.getByRole("combobox", { name: "Styl", exact: true });
    const custom = page.getByRole("textbox", { name: "Nazwa własnego stylu" });
    await expect(style).toHaveText("Własny styl");
    await expect(custom).toHaveValue("Moja autorska mieszanka");
    for (const [label, value] of [
      ["Naturalnie", "jasny i naturalny"],
      ["Minimalizm", "spokojny minimalizm"],
      ["Przytulnie", "ciepły i przytulny"],
      ["Loft", "loftowy"],
      ["Skandynawski", "skandynawski"],
      ["Japandi", "japandi"],
      ["Nowoczesny", "nowoczesny"],
      ["Klasyczny", "klasyczny"],
      ["Boho", "boho"],
      ["Art déco", "art déco"],
    ] as const) {
      await choose(style, label);
      await expect(custom).toBeHidden();
      await page.getByRole("button", { name: "Zapisz założenia" }).click();
      await expect(page.getByText("Założenia zapisane.")).toBeVisible();
      expect(api.requests.findLast((request) => request.method === "PUT")?.body).toMatchObject({
        brief: { style: value },
      });
    }
    await page.reload();
    await expect(style).toHaveText("Art déco");
    await expect(custom).toBeHidden();
  });

  test("custom style is explicit, required, retained across choices and saved after reload", async ({
    page,
    serve,
  }, testInfo) => {
    const api = await serve(createInterior({ rich: true }));
    await page.goto(`${WORKSPACE}?step=brief`);
    const style = page.getByRole("combobox", { name: "Styl", exact: true });
    await expect(style).toHaveText("Skandynawski");
    await expect(page.getByRole("textbox", { name: "Nazwa własnego stylu" })).toBeHidden();
    await style.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("listbox", { name: "Styl", exact: true })).toBeVisible();
    await expectNoA11yViolations(page);
    await page.keyboard.press("Home");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(style).toHaveText("Własny styl");
    const custom = page.getByRole("textbox", { name: "Nazwa własnego stylu" });
    await custom.fill("   ");
    await page.getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Wpisz nazwę własnego stylu.").first()).toBeVisible();
    expect(api.requests.filter((request) => request.method === "PUT")).toHaveLength(0);
    await custom.fill("  Japandi z kolorem  ");
    await choose(style, "Loft");
    await expect(custom).toBeHidden();
    await choose(style, "Własny styl");
    await expect(custom).toHaveValue("  Japandi z kolorem  ");
    await page.getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Założenia zapisane.")).toBeVisible();
    expect(api.requests.findLast((request) => request.method === "PUT")?.body).toMatchObject({
      brief: { style: "Japandi z kolorem" },
    });
    await page.reload();
    await expect(style).toHaveText("Własny styl");
    await expect(custom).toHaveValue("Japandi z kolorem");
    await page.screenshot({ path: testInfo.outputPath("custom-style-light.png"), fullPage: true });
    await page.getByRole("button", { name: "Tryb ciemny" }).click();
    await page.screenshot({ path: testInfo.outputPath("custom-style-dark.png"), fullPage: true });
    await choose(style, "Bez określonego stylu");
    await page.getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Założenia zapisane.")).toBeVisible();
    await page.reload();
    await expect(style).toHaveText("Bez określonego stylu");
    await expect(custom).toBeHidden();
  });

  test("every field keeps what is typed and saving sends it, the budget as exact text", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const brief = section(page, "Założenia");
    const fields: [string, string, string][] = [
      ["interior.brief.name", "Nazwa projektu", "Salon po remoncie"],
      ["interior.brief.customStyle", "Nazwa własnego stylu", "loft z zielenią"],
      ["interior.brief.budget", "Budżet na wyposażenie (zł)", "6500,50"],
      ["interior.brief.keep", "Rzeczy, które zostają", "kominek\nstary dywan"],
      ["interior.brief.notes", "Dodatkowe życzenia", "więcej światła"],
    ];
    const style = brief.getByRole("combobox", { name: "Styl", exact: true });
    await exercise("interior.brief.style", async () => {
      await choose(style, "Własny styl");
      return outcome.text(style, "Własny styl");
    });
    for (const [id, label, value] of fields) {
      const field = brief.getByRole("textbox", { name: label });
      await exercise(id, async () => {
        await field.fill(value);
        return [await outcome.value(field, value)];
      });
    }
    const room = brief.getByRole("combobox", { name: "Rodzaj pokoju" });
    await exercise("interior.brief.room", async () => {
      await choose(room, "Gabinet");
      return [await outcome.text(room, "Gabinet")];
    });
    await exercise("interior.brief.save", async () => {
      await brief.getByRole("button", { name: "Zapisz założenia" }).click();
      await expect(page.getByText("Założenia zapisane.")).toBeVisible();
      return [
        await outcome.request(api, {
          method: "PUT",
          path: `/api/interior/projects/${PROJECT}`,
          body: {
            name: "Salon po remoncie",
            brief: {
              room_type: "office",
              style: "loft z zielenią",
              budget_pln: "6500.50",
              keep: ["kominek", "stary dywan"],
              notes: "więcej światła",
            },
          },
        }),
      ];
    });
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Salon po remoncie" })).toBeVisible();
    await expect(page.getByRole("combobox", { name: "Styl", exact: true })).toHaveText("Własny styl");
    await expect(page.getByRole("textbox", { name: "Nazwa własnego stylu" })).toHaveValue("loft z zielenią");
  });

  test("a blank name and a budget that is not an amount are refused before anything is sent", async ({
    page,
    serve,
  }) => {
    const api = await serve(createInterior({ rich: true }));
    await openWorkspace(page);
    const brief = section(page, "Założenia");
    await brief.getByRole("textbox", { name: "Nazwa projektu" }).fill("   ");
    await brief.getByRole("textbox", { name: "Budżet na wyposażenie (zł)" }).fill("dużo");
    await brief.getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Wpisz nazwę projektu.").first()).toBeVisible();
    await expect(page.getByText(/Wpisz kwotę w złotych/).first()).toBeVisible();
    expect(api.requests.filter((r) => r.method === "PUT")).toEqual([]);
  });
});

test.describe("the person's own items", () => {
  test("only a name is needed; the item shows as unknown-price and unverified", async ({ page, serve }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const items = section(page, "Twoje rzeczy");
    for (const [id, label, value] of [
      ["interior.item.name", "Nazwa rzeczy", "Regał"],
      ["interior.item.quantity", "Liczba sztuk", "2"],
      ["interior.item.price", "Cena za sztukę (zł, opcjonalnie)", "199,99"],
      ["interior.item.url", "Link (opcjonalnie)", "https://sklep.example/regal"],
    ] as const) {
      const field = items.getByRole("textbox", { name: label });
      await exercise(id, async () => {
        await field.fill(value);
        return [await outcome.value(field, value)];
      });
    }
    await exercise("interior.item.add", async () => {
      await items.getByRole("button", { name: "Dodaj rzecz" }).click();
      await expect(items.getByRole("heading", { name: "Regał", level: 3 })).toBeVisible();
      return [
        await outcome.request(api, {
          method: "POST",
          path: `/api/interior/projects/${PROJECT}/items`,
          body: { name: "Regał", quantity: 2, price_pln: "199.99", url: "https://sklep.example/regal" },
        }),
      ];
    });
    await items.getByRole("textbox", { name: "Nazwa rzeczy" }).fill("Lampa");
    await items.getByRole("button", { name: "Dodaj rzecz" }).click();
    const lamp = items.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "Lampa" }) });
    await expect(lamp.getByText("Cena nieznana")).toBeVisible();
    await expect(lamp.getByText("Dodane przez Ciebie, niezweryfikowane")).toBeVisible();
    expect(flow.projects.get(PROJECT)?.items.find((i) => i.name === "Lampa")?.price_pln).toBeNull();
  });

  test("a price or link that is not valid is refused before anything is sent", async ({ page, serve }) => {
    const api = await serve(createInterior({ rich: true }));
    await openWorkspace(page);
    const items = section(page, "Twoje rzeczy");
    await items.getByRole("textbox", { name: "Nazwa rzeczy" }).fill("Lampa");
    await items.getByRole("textbox", { name: "Cena za sztukę (zł, opcjonalnie)" }).fill("dużo");
    await items.getByRole("textbox", { name: "Link (opcjonalnie)" }).fill("javascript:alert(1)");
    await items.getByRole("button", { name: "Dodaj rzecz" }).click();
    await expect(items.getByText(/Wpisz kwotę w złotych/).first()).toBeVisible();
    await expect(items.getByText(/zaczynający się od http/).first()).toBeVisible();
    expect(api.requests.filter((r) => r.path.endsWith("/items"))).toEqual([]);
  });

  test("an item can be edited, given a photo and removed", async ({ page, serve }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const items = section(page, "Twoje rzeczy");
    await exercise("interior.item.edit", async () => {
      await items.getByRole("button", { name: "Edytuj: Stary fotel" }).click();
      return [await outcome.text(items.getByRole("button", { name: "Zapisz rzecz" }), "Zapisz rzecz")];
    });
    await exercise("interior.item.cancel", async () => {
      await items.getByRole("button", { name: "Anuluj edycję" }).click();
      return [
        await outcome.text(items.getByRole("heading", { name: "Stary fotel", level: 3 }), "Stary fotel"),
      ];
    });
    await items.getByRole("button", { name: "Edytuj: Stary fotel" }).click();
    await exercise("interior.item.save", async () => {
      await items.getByRole("textbox", { name: "Cena za sztukę (zł, opcjonalnie)" }).first().fill("250");
      await items.getByRole("button", { name: "Zapisz rzecz" }).click();
      await expect(items.getByText(/250,00/)).toBeVisible();
      return [
        await outcome.request(api, {
          method: "PUT",
          path: /\/api\/interior\/projects\/[0-9a-f-]{36}\/items\//,
          body: { name: "Stary fotel", price_pln: "250" },
        }),
      ];
    });
    await exercise("interior.item.photo", async () => {
      const chooser = page.waitForEvent("filechooser");
      await items.getByRole("button", { name: "Dodaj zdjęcie: Stary fotel" }).click();
      await (await chooser).setFiles(photo());
      await expect(items.getByRole("img", { name: "Zdjęcie rzeczy: Stary fotel" })).toBeVisible();
      return [await outcome.request(api, { method: "PUT", path: /\/items\/[0-9a-f-]{36}\/photo$/ })];
    });
    await exercise("interior.item.remove", async () => {
      await items.getByRole("button", { name: "Usuń: Stary fotel" }).click();
      await expect(items.getByText("Nie dodano jeszcze żadnej rzeczy.")).toBeVisible();
      return [await outcome.request(api, { method: "DELETE", path: /\/items\/[0-9a-f-]{36}$/ })];
    });
  });
});

test.describe("the catalogue and the board", () => {
  test("with no source connected it says so and offers no search", async ({ page, serve }) => {
    await serve("interiorNoCatalogue");
    await openWorkspace(page);
    await expect(page.getByText("Katalog produktów nie jest jeszcze podłączony")).toBeVisible();
    await expect(page.getByRole("button", { name: "Szukaj produktów" })).toHaveCount(0);
  });

  test("searches, labels the source as demo, and picks one exact variant", async ({ page, serve }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const catalogue = section(page, "Katalog produktów");
    await expect(catalogue.getByText(/dane przykładowe, nie sklep/)).toBeVisible();
    const query = catalogue.getByRole("textbox", { name: "Czego szukasz" });
    await exercise("interior.catalogue.query", async () => {
      await query.fill("lampa");
      return [await outcome.value(query, "lampa")];
    });
    const category = catalogue.getByRole("combobox", { name: "Kategoria" });
    await exercise("interior.catalogue.category", async () => {
      await choose(category, "Lampy");
      return [await outcome.text(category, "Lampy")];
    });
    const max = catalogue.getByRole("textbox", { name: "Cena najwyżej (zł)" });
    await exercise("interior.catalogue.maxprice", async () => {
      await max.fill("500");
      return [await outcome.value(max, "500")];
    });
    await exercise("interior.catalogue.search", async () => {
      await catalogue.getByRole("button", { name: "Szukaj produktów" }).click();
      await expect(catalogue.getByRole("list", { name: "Znalezione produkty" })).toBeVisible();
      return [
        await outcome.request(api, {
          method: "GET",
          path: `/api/interior/projects/${PROJECT}/catalogue/search`,
        }),
      ];
    });
    const results = catalogue.getByRole("list", { name: "Znalezione produkty" });
    await expect(results.getByText("Cena nieznana").first()).toBeVisible(); // a lamp without a price
    await expect(results.getByText(/^0,00/)).toHaveCount(0);
    await exercise("interior.offer.link", async () => {
      const link = results.getByRole("link", { name: /^Otwórz stronę produktu: Lampa/ }).first();
      return [await outcome.state(link, "target", "_blank")];
    });
    await exercise("interior.catalogue.pick", async () => {
      await results.getByRole("button", { name: /^Wybierz: Lampa podłogowa Arc \(czarny/ }).click();
      await expect(
        section(page, "Tablica produktów").getByRole("heading", { name: "Lampa podłogowa Arc" }),
      ).toBeVisible();
      return [
        await outcome.request(api, {
          method: "POST",
          path: `/api/interior/projects/${PROJECT}/selections`,
          body: { variant_id: "black" },
        }),
      ];
    });
    await expect(
      results.getByRole("button", { name: /^Wybierz: Lampa podłogowa Arc \(czarny/ }),
    ).toBeDisabled();
  });

  test("the board changes quantity, re-checks an offer and removes a line; the sums are the server's", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const board = section(page, "Tablica produktów");
    await expect(board.getByText("Aktualna oferta")).toBeVisible();
    await expect(board.getByText(/Razem: 2\s?499,00/)).toBeVisible();
    await exercise("interior.board.increase", async () => {
      await board.getByRole("button", { name: /^Zwiększ liczbę sztuk: Sofa Nordic/ }).click();
      await expect(board.getByText(/Razem: 4\s?998,00/)).toBeVisible();
      return [
        await outcome.request(api, {
          method: "PUT",
          path: /\/selections\/[0-9a-f-]{36}$/,
          body: { quantity: 2 },
        }),
      ];
    });
    await exercise("interior.board.decrease", async () => {
      await board.getByRole("button", { name: /^Zmniejsz liczbę sztuk: Sofa Nordic/ }).click();
      await expect(board.getByText(/Razem: 2\s?499,00/)).toBeVisible();
      return [
        await outcome.request(api, {
          method: "PUT",
          path: /\/selections\/[0-9a-f-]{36}$/,
          body: { quantity: 1 },
        }),
      ];
    });
    flow.setOfferState("grey", "expired");
    await page.reload();
    await expect(board.getByText("Oferta wygasła")).toBeVisible();
    await expect(board.getByText("Razem: nie obliczamy")).toBeVisible();
    await expect(board.getByText(/Oferty wygasłe lub niedostępne \(poza sumą\): 1/)).toBeVisible();
    await expect(board.getByText(/Suma znanych cen: 0,00/)).toBeVisible();
    await exercise("interior.board.refresh", async () => {
      await board.getByRole("button", { name: /^Sprawdź ponownie: Sofa Nordic/ }).click();
      await expect(board.getByText("Aktualna oferta")).toBeVisible();
      return [await outcome.request(api, { method: "POST", path: /\/selections\/[0-9a-f-]{36}\/refresh$/ })];
    });
    await exercise("interior.board.remove", async () => {
      await board.getByRole("button", { name: /^Usuń z tablicy: Sofa Nordic/ }).click();
      await expect(board.getByText("Nie wybrano jeszcze produktów.")).toBeVisible();
      return [await outcome.request(api, { method: "DELETE", path: /\/selections\/[0-9a-f-]{36}$/ })];
    });
  });

  test("a variant that cannot be bought is refused with words and the board is unchanged", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    await serve(flow);
    await openWorkspace(page);
    flow.setOfferState("beige", "unavailable");
    const catalogue = section(page, "Katalog produktów");
    await catalogue.getByRole("textbox", { name: "Czego szukasz" }).fill("sofa");
    await catalogue.getByRole("button", { name: "Szukaj produktów" }).click();
    await catalogue.getByRole("button", { name: /^Wybierz: Sofa Nordic 3-osobowa \(beżowy/ }).click();
    await expect(page.getByText("Tego wariantu nie można teraz kupić")).toBeVisible();
    expect(flow.projects.get(PROJECT)?.selections).toHaveLength(1);
  });
});

test.describe("versions and visualisations", () => {
  test("saving a version lists it with the prices of that moment", async ({ page, serve }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    await expect(page.getByRole("heading", { name: "Wersja 1", level: 3 })).toBeVisible();
    await exercise("interior.revision.save", async () => {
      await section(page, "Wersje").getByRole("button", { name: "Zapisz wersję" }).click();
      await expect(page.getByText("Wersja zapisana.")).toBeVisible();
      return [
        await outcome.request(api, { method: "POST", path: `/api/interior/projects/${PROJECT}/revisions` }),
      ];
    });
    await expect(page.getByRole("heading", { name: "Wersja 2", level: 3 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Stan ofert w chwili zapisu" }).first()).toBeVisible();
  });

  test("a visualisation runs to a stored picture beside the original; a reload sends nothing new", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true });
    const api = await serve(flow);
    await openWorkspace(page);
    await exercise("interior.generation.start", async () => {
      await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
      return [
        await outcome.request(api, { method: "POST", path: `/api/interior/projects/${PROJECT}/generations` }),
      ];
    });
    await expect(page.getByText("Gotowa")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Przed: oryginalne zdjęcie")).toBeVisible();
    await expect(page.getByText("Po: ilustracja")).toBeVisible();
    await expect(page.getByText("Ilustracja, nie dokładny wygląd produktów")).toBeVisible();
    await expect(page.getByText(/Koszt: 0,034 USD/)).toBeVisible();
    const posts = () =>
      api.requests.filter((r) => r.method === "POST" && r.path.endsWith("/generations")).length;
    expect(posts()).toBe(1);
    await page.reload();
    await expect(page.getByText("Gotowa")).toBeVisible();
    await expect(page.getByRole("img", { name: "Ilustracja pokoju z wybranymi rzeczami" })).toBeVisible();
    expect(posts()).toBe(1);
  });

  test("a repeated click sends one generation", async ({ page, serve }) => {
    const flow = createInterior({ rich: true, hold: true });
    const api = await serve(flow);
    await openWorkspace(page);
    const start = page.getByRole("button", { name: "Generuj wizualizację z wersji 1" });
    await start.dblclick();
    await expect(page.getByText("W kolejce")).toBeVisible();
    expect(api.requests.filter((r) => r.method === "POST" && r.path.endsWith("/generations"))).toHaveLength(
      1,
    );
    await expect(start).toBeDisabled();
  });

  test("a queued visualisation can be cancelled, and then started again", async ({ page, serve }) => {
    const flow = createInterior({ rich: true, hold: true });
    const api = await serve(flow);
    await openWorkspace(page);
    await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
    await exercise("interior.generation.cancel", async () => {
      await page.getByRole("button", { name: "Anuluj wizualizację" }).click();
      await expect(page.getByText("Wizualizacja anulowana.")).toBeVisible();
      return [await outcome.request(api, { method: "POST", path: /\/generations\/[0-9a-f-]{36}\/cancel$/ })];
    });
    await expect(page.getByText("Anulowana", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
    await expect(page.getByText("W kolejce")).toBeVisible();
    expect(api.requests.filter((r) => r.method === "POST" && r.path.endsWith("/generations"))).toHaveLength(
      2,
    );
  });

  test("a failed visualisation says why, keeps the original and offers a new attempt", async ({
    page,
    serve,
  }) => {
    const flow = createInterior({ rich: true, failWith: "AMBIGUOUS" });
    const api = await serve(flow);
    await openWorkspace(page);
    await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
    await expect(page.getByText(/nie dostaliśmy odpowiedzi/)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/Koszt szacunkowy: 0,1 USD/)).toBeVisible();
    await expect(
      page.getByRole("img", { name: "Zdjęcie pokoju, z którego powstaje wizualizacja" }),
    ).toBeVisible();
    await exercise("interior.generation.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      await expect
        .poll(() => api.requests.filter((r) => r.method === "POST" && r.path.endsWith("/generations")).length)
        .toBe(2);
      return [
        await outcome.request(api, { method: "POST", path: `/api/interior/projects/${PROJECT}/generations` }),
      ];
    });
  });

  test("when generation is switched off the rest of the project keeps working", async ({ page, serve }) => {
    await serve(createInterior({ rich: true, generationOff: true }));
    await openWorkspace(page);
    await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
    await expect(page.getByText(/Generowanie obrazów jest wyłączone/).first()).toBeVisible();
    await expect(section(page, "Wersje").getByRole("button", { name: "Zapisz wersję" })).toBeEnabled();
  });
});

test.describe("navigation", () => {
  test("the way back to the list", async ({ page, serve }) => {
    await serve(createInterior({ rich: true }));
    await openWorkspace(page);
    await exercise("interior.project.back", async () => {
      await page.getByRole("link", { name: "Wszystkie projekty" }).click();
      return [await outcome.url(page, /\/app\/interior$/)];
    });
  });
});
