import type { Locator, Page } from "@playwright/test";

import { createCollection } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const rows = (page: Page) => page.getByRole("list", { name: "Analizy" }).getByRole("listitem");
const more = (page: Page) => page.getByRole("button", { name: "Załaduj więcej" });
const shown = (page: Page) => page.getByRole("status").filter({ hasText: /Wyświetlono|Odświeżam/ });
const status = (page: Page) => page.getByRole("combobox", { name: "Status" });
const grade = (page: Page) => page.getByRole("combobox", { name: "Ocena" });

/** Choose from a styled select the way a person does: open it, pick the option. */
async function choose(select: Locator, label: string): Promise<void> {
  await select.click();
  await select.page().getByRole("option", { name: label, exact: true }).click();
}
const search = (page: Page) => page.getByRole("textbox", { name: "Numer ogłoszenia (początek)" });

test.describe("the collection", () => {
  test("a first visit shows an honest empty state and no paging control", async ({ page, serve }) => {
    await serve("empty");
    await page.goto("/app/analyses");
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toBeVisible();
    await expect(more(page)).toHaveCount(0);
    await exercise("analyses.first", async () => {
      await page.getByRole("link", { name: "Sprawdź pierwsze mieszkanie" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("while the list loads there is a status, not the empty state", async ({ page, serve }) => {
    await serve("slow");
    await page.goto("/app/analyses");
    await expect(page.getByRole("status", { name: "Wczytuję analizy" })).toBeVisible();
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toHaveCount(0);
    await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toBeVisible();
  });

  test("a failed list says so and can be retried", async ({ page, serve }) => {
    const api = await serve("auditsFailing");
    await page.goto("/app/analyses");
    await expect(page.getByRole("alert").filter({ hasText: "Nie udało się wczytać analiz" })).toBeVisible();
    await exercise("analyses.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/audits" })];
    });
  });

  test("120 analyses come page by page: each once, newest first, the end only when the server says so", async ({
    page,
    serve,
  }) => {
    const collection = createCollection({ count: 120 });
    const api = await serve(collection);
    await page.goto("/app/analyses");
    await expect(rows(page)).toHaveCount(24);
    await expect(shown(page)).toContainText("Wyświetlono 24 analizy");
    await exercise("analyses.more", async () => {
      await more(page).click();
      return [await outcome.request(api, { method: "GET", path: "/api/audits" })];
    });
    await expect(rows(page)).toHaveCount(48);
    while ((await more(page).count()) > 0) {
      const before = await rows(page).count();
      await more(page).click();
      await expect.poll(() => rows(page).count()).toBeGreaterThan(before);
    }
    await expect(rows(page)).toHaveCount(120);
    await expect(page.getByText("To wszystkie analizy (120).")).toBeVisible();
    const names = await rows(page)
      .getByRole("link")
      .evaluateAll((links) => links.map((a) => a.textContent));
    expect(new Set(names).size).toBe(120);
    expect(names[0]).toBe("Ogłoszenie IDLST0000");
    expect(names[119]).toBe("Ogłoszenie IDLST0119");
    const cursors = collection.state.requests.map((r) => new URLSearchParams(r).get("cursor"));
    expect(cursors.filter((c) => c !== null)).toHaveLength(4); // 24 x 5: the fifth page ends the list
    expect(new Set(cursors).size).toBe(5);
  });

  test("a list that is exactly one page long shows no 'load more'", async ({ page, serve }) => {
    await serve(createCollection({ count: 24 }));
    await page.goto("/app/analyses");
    await expect(rows(page)).toHaveCount(24);
    await expect(more(page)).toHaveCount(0);
    await expect(page.getByText("To wszystkie analizy (24).")).toBeVisible();
  });

  test("a failed next page keeps what is shown and offers the same button again", async ({ page, serve }) => {
    const collection = createCollection({ count: 120, failPage: 1 });
    await serve(collection);
    await page.goto("/app/analyses");
    await expect(rows(page)).toHaveCount(24);
    await more(page).click();
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać kolejnych analiz" }),
    ).toBeVisible();
    await expect(rows(page)).toHaveCount(24);
    collection.state.failing = false;
    await more(page).click();
    await expect(rows(page)).toHaveCount(48);
  });

  test("a row opens its report", async ({ page, serve }) => {
    await serve("collection");
    await page.goto("/app/analyses");
    await exercise("analyses.row", async () => {
      await rows(page).first().getByRole("link").click();
      return [await outcome.url(page, /\/app\/analyses\/00000000-0000-4000-8000-000000100000$/)];
    });
  });

  test("a row says what it is: date, status, grade and both prices, or 'nie obliczono'", async ({
    page,
    serve,
  }) => {
    await serve("collection");
    await page.goto("/app/analyses");
    const first = rows(page).first();
    await expect(first).toContainText("Cena ofertowa");
    await expect(first).toContainText("Cena progowa");
    await expect(first).toContainText(
      /Analiza gotowa|W kolejce|Gotowa|Odrzucona|nie udało|zablokował|nieaktywne|wynajmu/i,
    );
    await expect(page.getByRole("list", { name: "Analizy" })).toContainText("nie obliczono");
  });

  test.describe("filters live in the address", () => {
    test("status, grade and search are requests; Back and Refresh restore them", async ({ page, serve }) => {
      const collection = createCollection({ count: 120 });
      await serve(collection);
      await page.goto("/app/analyses");
      await expect(rows(page)).toHaveCount(24);

      await exercise("analyses.option.ready", async () => {
        await choose(status(page), "Gotowe");
        return [await outcome.url(page, /\?status=ready$/)];
      });
      await expect(page.getByRole("list", { name: "Analizy" })).not.toContainText("W kolejce");
      const sent = collection.state.requests.at(-1) ?? "";
      expect(new URLSearchParams(sent).getAll("status").sort()).toEqual(["succeeded", "succeeded_degraded"]);

      await exercise("analyses.status", async () => {
        await expect(status(page)).toHaveText("Gotowe");
        return [await outcome.url(page, /status=ready/)];
      });
      await exercise("analyses.grade", async () => {
        await choose(grade(page), "E");
        return [await outcome.url(page, /status=ready&grade=E$/)];
      });

      await page.reload();
      await expect(status(page)).toHaveText("Gotowe");
      await expect(grade(page)).toHaveText("E");
      await expect(rows(page).first()).toBeVisible();

      await page.goBack();
      await expect(page).toHaveURL(/\?status=ready$/);
      await expect(grade(page)).toHaveText("Wszystkie");
      await page.goBack();
      await expect(page).toHaveURL(/\/app\/analyses$/);
      await expect(status(page)).toHaveText("Wszystkie");
    });

    for (const [id, label, expected] of [
      ["active", "W toku", /status=active$/],
      ["rejected", "Odrzucone", /status=rejected$/],
      ["failed", "Nieudane", /status=failed$/],
    ] as const) {
      test(`the "${label}" status option filters`, async ({ page, serve }) => {
        await serve("collection");
        await page.goto("/app/analyses");
        await exercise(`analyses.option.${id}`, async () => {
          await choose(status(page), label);
          return [await outcome.url(page, expected)];
        });
      });
    }

    for (const g of ["A", "B", "C", "D", "E", "N"] as const) {
      test(`the grade ${g} option filters`, async ({ page, serve }) => {
        await serve("collection");
        await page.goto("/app/analyses");
        await exercise(`analyses.option.grade-${g}`, async () => {
          await choose(grade(page), g === "N" ? "Bez oceny" : g);
          return [await outcome.url(page, new RegExp(`grade=${g}$`))];
        });
      });
    }

    test("each select opens a labelled list of choices", async ({ page, serve }) => {
      await serve("collection");
      await page.goto("/app/analyses");
      for (const [id, select, name] of [
        ["status", status(page), "Status"],
        ["grade", grade(page), "Ocena"],
      ] as const) {
        await exercise(`analyses.${id}.listbox`, async () => {
          await select.click();
          await expect(page.getByRole("listbox", { name })).toBeVisible();
          const opened = await outcome.state(select, "aria-expanded", "true");
          await page.keyboard.press("Escape");
          return [opened];
        });
      }
    });

    test("'Wszystkie' removes the filter again", async ({ page, serve }) => {
      await serve("collection");
      await page.goto("/app/analyses?status=ready&grade=E");
      await exercise("analyses.option.all", async () => {
        await choose(status(page), "Wszystkie");
        return [await outcome.url(page, /\?grade=E$/)];
      });
    });

    test("'Wszystkie' in the grade list removes the grade filter again", async ({ page, serve }) => {
      await serve("collection");
      await page.goto("/app/analyses?status=ready&grade=E");
      await exercise("analyses.option.grade-all", async () => {
        await choose(grade(page), "Wszystkie");
        return [await outcome.url(page, /\?status=ready$/)];
      });
    });

    test("a search by listing id prefix is sent to the API and finds one row", async ({ page, serve }) => {
      const collection = createCollection({ count: 120 });
      await serve(collection);
      await page.goto("/app/analyses");
      await exercise("analyses.search", async () => {
        await search(page).fill("IDLST0011");
        return [await outcome.value(search(page), "IDLST0011")];
      });
      await exercise("analyses.search.submit", async () => {
        await page.getByRole("button", { name: "Szukaj" }).click();
        return [await outcome.url(page, /\?q=IDLST0011$/)];
      });
      await expect(rows(page)).toHaveCount(1);
      await expect(rows(page).first()).toContainText("IDLST0011");
      expect(new URLSearchParams(collection.state.requests.at(-1) ?? "").get("q")).toBe("IDLST0011");
    });

    test("Enter submits the search; hostile or unknown values in the address are ignored, not sent", async ({
      page,
      serve,
    }) => {
      const collection = createCollection({ count: 30 });
      await serve(collection);
      await page.goto("/app/analyses?status=bogus&grade=Z&q=%3Cscript%3E&view=weird");
      await expect(rows(page)).toHaveCount(24);
      const sent = new URLSearchParams(collection.state.requests[0] ?? "");
      expect([sent.getAll("status"), sent.get("grade"), sent.get("q")]).toEqual([[], null, null]);
      await search(page).fill("IDLST0003");
      await search(page).press("Enter");
      await expect(page).toHaveURL(/\?q=IDLST0003$/);
    });

    test("nothing matching says so and 'Wyczyść filtry' brings everything back", async ({ page, serve }) => {
      await serve("collection");
      await page.goto("/app/analyses");
      await search(page).fill("ZZZ");
      await page.getByRole("button", { name: "Szukaj" }).click();
      await expect(page.getByText("Żadna analiza nie pasuje do filtrów")).toBeVisible();
      await expect(page.getByText("Nie masz jeszcze żadnej analizy")).toHaveCount(0);
      await exercise("analyses.clear", async () => {
        await page.getByRole("button", { name: "Wyczyść filtry" }).click();
        return [await outcome.url(page, /\/app\/analyses$/)];
      });
      await expect(rows(page)).toHaveCount(24);
    });
  });

  test.describe("views", () => {
    test("cards and table are one choice kept in the address, with the same rows", async ({
      page,
      serve,
    }) => {
      await serve("collection");
      await page.goto("/app/analyses");
      const cards = page.getByRole("button", { name: "Karty" });
      await expect(cards).toHaveAttribute("aria-pressed", "true");
      await exercise("analyses.view.table", async () => {
        await page.getByRole("button", { name: "Tabela" }).click();
        return [await outcome.url(page, /\?view=table$/)];
      });
      await expect(page.getByRole("table")).toBeVisible();
      await expect(page.getByRole("row")).toHaveCount(25); // header and 24
      await expect(page.getByRole("button", { name: "Tabela" })).toHaveAttribute("aria-pressed", "true");
      await page.reload();
      await expect(page.getByRole("table")).toBeVisible();
      await exercise("analyses.view.cards", async () => {
        await cards.click();
        return [await outcome.state(cards, "aria-pressed", "true")];
      });
      await expect(page.getByRole("table")).toHaveCount(0);
      await expect(rows(page)).toHaveCount(24);
    });

    test("the table has native semantics and scrolls inside its own labelled region at 320 px", async ({
      page,
      serve,
    }) => {
      await serve("collection");
      await page.setViewportSize({ width: 320, height: 800 });
      await page.goto("/app/analyses?view=table");
      const table = page.getByRole("table");
      await expect(table).toBeVisible();
      await expect(page.getByRole("columnheader")).toHaveText([
        "Ogłoszenie",
        "Data",
        "Status",
        "Ocena",
        "Cena ofertowa",
        "Cena progowa",
        "Zapisane",
      ]);
      await expect(page.getByRole("rowheader").first()).toContainText("Ogłoszenie IDLST0000");
      const region = page.getByRole("region", { name: "Tabela analiz" });
      const scrolls = await region.evaluate((el) => el.scrollWidth > el.clientWidth);
      expect(scrolls).toBe(true);
      const pageOverflow = await page.evaluate(
        () => (document.scrollingElement?.scrollWidth ?? 0) > (document.scrollingElement?.clientWidth ?? 0),
      );
      expect(pageOverflow).toBe(false);
      await region.focus();
      await expect(region).toBeFocused(); // reachable by keyboard
      await expect(region).toHaveCSS("outline-style", "solid");
      await expect(region).toHaveCSS("outline-width", "2px");
      // The order is the server's (newest first) and is said so; no header offers a sort the API cannot do.
      await expect(page.getByRole("columnheader", { name: "Data" })).toHaveAttribute(
        "aria-sort",
        "descending",
      );
      await expect(page.getByRole("columnheader").getByRole("button")).toHaveCount(0);
    });
  });

  test("coming back to a stale list keeps its rows and says it is refreshing", async ({ page, serve }) => {
    await page.clock.install();
    await serve(createCollection({ count: 60, refreshDelayMs: 1500 }));
    await page.goto("/app/analyses");
    await expect(rows(page)).toHaveCount(24);
    await rows(page).first().getByRole("link").click();
    await expect(page.getByRole("heading", { level: 1, name: /^Ogłoszenie / })).toBeVisible();
    await page.clock.fastForward(60_000); // the cached list is stale by now
    await page.goBack();
    await expect(page.getByRole("heading", { level: 1, name: "Moje analizy" })).toBeVisible();
    await expect(shown(page)).toContainText("Odświeżam listę");
    await expect(rows(page)).toHaveCount(24);
    await page.clock.resume();
    await expect(shown(page)).toContainText("Wyświetlono 24 analizy");
  });
});
