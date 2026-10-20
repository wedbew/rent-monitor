import type { Locator, Page } from "@playwright/test";

import { createMarket } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

/**
 * Rynek (RM-439): the tabs, the filters, the map with real marker activation, the comparison journey, a place, a
 * district and the GUS ranking. Every registered interaction is exercised here with an asserted outcome; a click on
 * an SVG is never the evidence, the content or address that follows is.
 */

const OTODOM = "/app/market/otodom";
const frame = (page: Page) => page.getByTestId("market-map");
const mapSvg = (page: Page) => frame(page).locator("svg[role=img]").first();
const viewBox = async (page: Page) => (await mapSvg(page).getAttribute("viewBox")) ?? "";
/** The view once its animation has finished: two reads a moment apart agree. */
async function settled(page: Page): Promise<string> {
  let last = await viewBox(page);
  for (let i = 0; i < 20; i += 1) {
    await page.waitForTimeout(120);
    const now = await viewBox(page);
    if (now === last) return now;
    last = now;
  }
  return last;
}
const notEqual = (value: string) => new RegExp(`^(?!${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$)`);

async function choose(select: Locator, label: string): Promise<void> {
  await select.click();
  await select.page().getByRole("option", { name: label, exact: true }).click();
}

/** A marker whose centre is inside the frame (one at its edge is clipped and cannot be hit). */
async function visibleMarker(page: Page, pattern: RegExp, selector = "[data-place]"): Promise<Locator> {
  const box = await frame(page).boundingBox();
  if (box === null) throw new Error("the map has no box");
  const markers = await frame(page).locator(selector).all();
  for (const marker of markers) {
    const b = await marker.boundingBox();
    const label = (await marker.getAttribute("aria-label")) ?? "";
    const inside =
      b !== null &&
      b.x > box.x + 30 &&
      b.x + b.width < box.x + box.width - 30 &&
      b.y > box.y + 30 &&
      b.y + b.height < box.y + box.height - 30;
    const underControls = b !== null && b.x + b.width > box.x + box.width - 160 && b.y < box.y + 190;
    if (inside && !underControls && pattern.test(label)) return marker;
  }
  throw new Error(`no visible marker matching ${String(pattern)}`);
}

/** Zoom in through the first clusters until single places can be hit. */
async function zoomToPlaces(page: Page): Promise<void> {
  for (let i = 0; i < 6; i += 1) {
    const clusters = frame(page).locator("[data-cluster]");
    if ((await clusters.count()) === 0) return;
    const before = await viewBox(page);
    await (await visibleMarker(page, /^Skupisko/, "[data-cluster]")).click();
    await expect.poll(() => viewBox(page)).not.toBe(before);
  }
}

test.describe("Rynek tabs", () => {
  test("two tabs, each a path of its own; the current one is marked and the place travels with the switch", async ({
    page,
    serve,
  }) => {
    await serve("market");
    for (const [id, path, heading] of [
      ["rynek.otodom", OTODOM, "Rynek"],
      ["rynek.place", `${OTODOM}/bialystok`, "Białystok"],
      ["rynek.district", `${OTODOM}/bialystok/centrum`, "Centrum"],
      ["rynek.gus", "/app/market/gus/bialystok", "Białystok"],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      const target = id === "rynek.gus" ? "otodom" : "gus";
      await exercise(`${id}.tab.${target}`, async () => {
        await page.locator(`[data-tab=${target}]`).click();
        return [
          await outcome.url(
            page,
            target === "gus"
              ? id === "rynek.otodom"
                ? /\/app\/market\/gus$/
                : /\/app\/market\/gus\/bialystok$/
              : /\/app\/market\/otodom\/bialystok$/,
          ),
        ];
      });
      await page.goto(path);
      const other = id === "rynek.gus" ? "gus" : "otodom";
      await exercise(`${id}.tab.${other}`, async () => {
        await page.locator(`[data-tab=${other}]`).click();
        return [await outcome.url(page, other === "gus" ? /\/app\/market\/gus/ : /\/app\/market\/otodom/)];
      });
    }
  });

  test("the bare address and the old place address go to the Otodom tab; every tab names its source, period and grain", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market?cohort=rooms_2");
    await expect(page).toHaveURL(/\/app\/market\/otodom\?cohort=rooms_2$/);
    await page.goto("/app/market/torun");
    await expect(page).toHaveURL(/\/app\/market\/otodom\/torun$/);
    await expect(page.locator("[data-tab=otodom]")).toHaveAttribute("aria-current", "true");
    await expect(page.getByText("Źródło: ogłoszenia najmu na Otodom").first()).toBeVisible();
    await page.goto("/app/market/gus");
    await expect(page.locator("[data-tab=gus]")).toHaveAttribute("aria-current", "true");
    await expect(page.getByText("Źródło: GUS, Bank Danych Lokalnych").first()).toBeVisible();
    await expect(page.getByText("Poziom: gmina, powiat, województwo").first()).toBeVisible();
  });
});

test.describe("Rynek filters", () => {
  test("a group of flats changes the request, the data and the address, survives reload and Back, and resets alone", async ({
    page,
    serve,
  }) => {
    const api = await serve("market");
    await page.goto(`${OTODOM}?view=list&sort=ppm2`);
    const filters = page.getByTestId("cohort-filters");
    await expect(filters.getByRole("group", { name: "Powierzchnia mieszkania" })).toBeVisible();
    await expect(filters.getByRole("group", { name: "Liczba pokoi" })).toBeVisible();
    const topBefore = await page.getByRole("row").nth(1).innerText();
    await exercise("rynek.otodom.filter.rooms", async () => {
      await filters.getByRole("radio", { name: "2 pokoje" }).click();
      return [await outcome.url(page, /cohort=rooms_2/)];
    });
    await expect
      .poll(() =>
        api.requests.some((r) => r.path === "/api/market/overview" && r.query.includes("cohort=rooms_2")),
      )
      .toBe(true);
    await expect(filters.getByText("Aktywny filtr: 2 pokoje")).toBeVisible();
    await expect(page.getByText("Liczby dotyczą grupy: 2 pokoje.")).toBeVisible();
    await expect.poll(async () => page.getByRole("row").nth(1).innerText()).not.toBe(topBefore);
    await exercise("rynek.otodom.filter.area", async () => {
      await filters.getByRole("radio", { name: "45 do 60 m²" }).click();
      return [await outcome.url(page, /cohort=size_45_60/)];
    });
    await expect(filters.getByText(/Zastąpiono filtr „2 pokoje” filtrem „45 do 60 m²”/)).toBeVisible();
    await expect(filters.getByRole("radio", { name: "2 pokoje" })).not.toBeChecked();
    await page.reload();
    await expect(filters.getByRole("radio", { name: "45 do 60 m²" })).toBeChecked();
    await page.goBack();
    await expect(page).toHaveURL(/cohort=rooms_2/);
    await expect(filters.getByRole("radio", { name: "2 pokoje" })).toBeChecked();
    await page.goto(`${OTODOM}?view=list&sort=ppm2&cohort=rooms_2`);
    await expect(filters.getByRole("button", { name: "Wyczyść filtr" })).toBeVisible();
  });

  test("the reset clears the filter and nothing else", async ({ page, serve }) => {
    await serve("market");
    await page.goto(`${OTODOM}?view=list&sort=ppm2&cohort=rooms_2`);
    await exercise("rynek.otodom.filter.reset", async () => {
      await page.getByRole("button", { name: "Wyczyść filtr" }).click();
      return [await outcome.url(page, /^(?!.*cohort=).*sort=ppm2/)];
    });
    await expect(page.getByText("Brak filtra: wszystkie mieszkania")).toBeVisible();
  });

  test("the filter is on the place and district pages too and keeps the group when moving between them", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}/bialystok`);
    await exercise("rynek.place.filter.rooms", async () => {
      await page.getByTestId("cohort-filters").getByRole("radio", { name: "3 pokoje" }).click();
      return [await outcome.url(page, /cohort=rooms_3/)];
    });
    await exercise("rynek.place.filter.area", async () => {
      await page.getByTestId("cohort-filters").getByRole("radio", { name: "60 do 80 m²" }).click();
      return [await outcome.url(page, /cohort=size_60_80/)];
    });
    await page.goto(`${OTODOM}/bialystok/centrum`);
    await exercise("rynek.district.filter.rooms", async () => {
      await page.getByTestId("cohort-filters").getByRole("radio", { name: "1 pokój" }).click();
      return [await outcome.url(page, /cohort=rooms_1/)];
    });
    await exercise("rynek.district.filter.area", async () => {
      await page.getByTestId("cohort-filters").getByRole("radio", { name: "Poniżej 30 m²" }).click();
      return [await outcome.url(page, /cohort=size_lt30/)];
    });
  });

  test("a restricted account sees the rule and an upgrade link; an unlimited one is told so and nothing is disabled", async ({
    page,
    serve,
  }) => {
    await serve("marketFree");
    await page.goto(OTODOM);
    await expect(page.getByText(/Konto darmowe: widzisz 20 z 38 miejsc/)).toBeVisible();
    await exercise("rynek.otodom.upgrade", async () => {
      await page.getByRole("link", { name: "Kup pakiet raportów" }).click();
      return [await outcome.url(page, /\/app\/credits$/)];
    });
    await serve("marketUnlimited");
    await page.goto(OTODOM);
    await expect(page.getByText("Pełny dostęp do rynku")).toBeVisible();
    await expect(page.getByText("Raporty: bez limitu")).toBeAttached(); // in the account block (a menu on a phone)
    await expect(page.getByRole("radio", { name: "4 pokoje i więcej" })).toBeEnabled();
    await page.getByRole("radio", { name: "4 pokoje i więcej" }).click();
    await expect(page).toHaveURL(/cohort=rooms_4plus/);
  });
});

test.describe("Rynek map", () => {
  test("markers are 44 px targets, named, and activating one opens a preview with the figures and the way to open the place", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    await expect(frame(page)).toBeVisible();
    await zoomToPlaces(page);
    const marker = await visibleMarker(page, /: \d.*ofert$/);
    const box = await marker.boundingBox();
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    const name = ((await marker.getAttribute("aria-label")) ?? "").split(":")[0] ?? "";
    await marker.hover();
    await expect(frame(page).getByRole("tooltip")).toContainText(name); // the name and the figures, on hover
    await exercise("rynek.map.marker", async () => {
      await marker.click();
      return [await outcome.url(page, /sel=/)];
    });
    const preview = page.getByTestId("map-preview");
    await expect(preview).toContainText(name);
    await expect(preview).toContainText("Mediana za m²");
    await expect(preview).toContainText("Oferty z ceną");
    await expect(preview).toContainText("Ostatnie odświeżenie");
    await expect(marker).toHaveAttribute("aria-pressed", "true");
    // the same place is selected in the table (one selection for the map, the preview and the table)
    await expect(page.getByRole("row", { selected: true })).toContainText(name);
    await exercise("rynek.preview.open", async () => {
      await preview.getByRole("link", { name: "Otwórz miejsce" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom\/[a-z-]+$/)];
    });
    await expect(page.getByRole("heading", { level: 1 })).toContainText(name);
  });

  test("a marker works from the keyboard and Escape closes the preview", async ({ page, serve }) => {
    await serve("market");
    await page.goto(OTODOM);
    await zoomToPlaces(page);
    const marker = await visibleMarker(page, /: \d.*ofert$/);
    await marker.focus();
    await expect(frame(page).getByRole("tooltip")).toBeVisible(); // focus reveals what hover does
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("map-preview")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("map-preview")).toBeHidden();
    await expect(page).not.toHaveURL(/sel=/);
  });

  test("a cluster zooms into its places; the preview can be closed, compared and the place chosen from the table", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    const whole = await viewBox(page);
    await exercise("rynek.map.cluster", async () => {
      await (await visibleMarker(page, /^Skupisko/, "[data-cluster]")).click();
      return [await outcome.state(mapSvg(page), "viewBox", notEqual(whole))];
    });
    await zoomToPlaces(page);
    const marker = await visibleMarker(page, /: \d.*ofert$/);
    await marker.click();
    const preview = page.getByTestId("map-preview");
    await exercise("rynek.preview.compare", async () => {
      await preview.getByRole("button", { name: "Dodaj do porównania" }).click();
      return [await outcome.url(page, /ids=/)];
    });
    await expect(page.getByRole("button", { name: /^Porównaj miejsca \(1\)/ })).toBeVisible();
    await expect(preview.getByRole("button", { name: "Usuń z porównania" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await exercise("rynek.preview.close", async () => {
      await preview.getByRole("button", { name: "Zamknij podgląd" }).click();
      return [await outcome.url(page, /^(?!.*sel=)/)];
    });
  });

  test("zoom in, zoom out and the whole-country reset animate the view and the reset keeps the filters", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}?cohort=rooms_2&metric=rent`);
    const whole = await viewBox(page);
    await exercise("rynek.map.zoom-in", async () => {
      await page.getByRole("button", { name: "Przybliż mapę" }).click();
      return [await outcome.state(mapSvg(page), "viewBox", notEqual(whole))];
    });
    const closer = await viewBox(page);
    await exercise("rynek.map.zoom-out", async () => {
      await page.getByRole("button", { name: "Oddal mapę" }).click();
      return [await outcome.state(mapSvg(page), "viewBox", notEqual(closer))];
    });
    await page.getByRole("button", { name: "Przybliż mapę" }).click();
    await exercise("rynek.map.reset", async () => {
      await page.getByRole("button", { name: "Pokaż całą Polskę" }).click();
      return [await outcome.state(mapSvg(page), "viewBox", whole)];
    });
    await expect(page).toHaveURL(/cohort=rooms_2/); // the reset is the map's, not the filters'
    // the controls are inside the map frame
    const f = await frame(page).boundingBox();
    const c = await page.getByRole("button", { name: "Przybliż mapę" }).boundingBox();
    expect(c !== null && f !== null && c.x >= f.x && c.x + c.width <= f.x + f.width && c.y >= f.y).toBe(true);
  });

  test("dragging pans, a pinch zooms, the wheel zooms only with Ctrl or after the map was clicked, and reduced motion jumps", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    const f = (await frame(page).boundingBox()) ?? { x: 0, y: 0, width: 800, height: 500 };
    const cx = f.x + f.width / 2;
    const cy = f.y + f.height / 2;
    const whole = await viewBox(page);
    // a plain wheel over a map that was not clicked scrolls the page and leaves the map alone
    await page.mouse.move(cx, cy);
    await page.mouse.wheel(0, -400);
    await page.waitForTimeout(300);
    expect(await viewBox(page)).toBe(whole);
    // Ctrl + wheel (a trackpad pinch) zooms
    await frame(page).evaluate(
      (el, [x, y]) =>
        el.dispatchEvent(
          new WheelEvent("wheel", {
            deltaY: -120,
            ctrlKey: true,
            clientX: x ?? 0,
            clientY: y ?? 0,
            bubbles: true,
            cancelable: true,
          }),
        ),
      [cx, cy],
    );
    await expect.poll(() => viewBox(page)).not.toBe(whole);
    const zoomed = await settled(page);
    // dragging pans
    // a point of the map that is not under a marker or a control (those take the pointer for themselves)
    await frame(page).scrollIntoViewIfNeeded(); // the plain wheel above scrolled the page
    const g = (await frame(page).boundingBox()) ?? f;
    const [gx = g.x + 14, gy = g.y + 60] = await page.evaluate(
      ([x0, y0, w, h]) => {
        for (let ix = 0; ix < 20; ix += 1)
          for (let iy = 0; iy < 14; iy += 1) {
            const x = (x0 ?? 0) + 12 + ((w ?? 0) - 24) * (ix / 19);
            const y = (y0 ?? 0) + 12 + ((h ?? 0) - 24) * (iy / 13);
            if (document.elementFromPoint(x, y)?.closest("[data-map-ui]") === null) return [x, y];
          }
        return [];
      },
      [g.x, g.y, g.width, g.height],
    );
    await page.mouse.move(gx, gy);
    await page.mouse.down();
    await page.mouse.move(gx + 120, gy + 60, { steps: 6 });
    await page.mouse.up();
    await expect.poll(() => viewBox(page)).not.toBe(zoomed);
    // after a click the plain wheel zooms
    const panned = await settled(page);
    await page.mouse.wheel(0, 300);
    await expect.poll(() => viewBox(page)).not.toBe(panned);
    // two touch pointers pinching apart zoom in
    await page.getByRole("button", { name: "Pokaż całą Polskę" }).click();
    await expect.poll(() => viewBox(page)).toBe(whole);
    await frame(page).evaluate(
      (el, [x, y]) => {
        const fire = (type: string, id: number, dx: number) =>
          el.dispatchEvent(
            new PointerEvent(type, {
              pointerId: id,
              pointerType: "touch",
              clientX: (x ?? 0) + dx,
              clientY: y ?? 0,
              bubbles: true,
              isPrimary: id === 1,
            }),
          );
        fire("pointerdown", 1, -20);
        fire("pointerdown", 2, 20);
        for (let i = 1; i <= 6; i += 1) {
          fire("pointermove", 1, -20 - i * 15);
          fire("pointermove", 2, 20 + i * 15);
        }
        fire("pointerup", 1, -110);
        fire("pointerup", 2, 110);
      },
      [cx, cy],
    );
    await expect.poll(() => viewBox(page)).not.toBe(whole);
  });

  test("with reduced motion the zoom is immediate", async ({ page, serve }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await serve("market");
    await page.goto(OTODOM);
    const whole = await viewBox(page);
    await page.getByRole("button", { name: "Przybliż mapę" }).click();
    expect(await viewBox(page)).not.toBe(whole); // no frames in between: the new view is there at once
  });

  test("the map frame is keyboard operable: arrows pan, plus and minus zoom, Home resets", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    const whole = await viewBox(page);
    await frame(page).focus();
    await page.keyboard.press("+");
    await expect.poll(() => viewBox(page)).not.toBe(whole);
    const zoomed = await settled(page);
    await page.keyboard.press("ArrowLeft");
    await expect.poll(() => viewBox(page)).not.toBe(zoomed);
    await page.keyboard.press("Home");
    await expect.poll(() => viewBox(page)).toBe(whole);
  });
});

test.describe("Rynek explorer", () => {
  test("view, colour measure, order and search are in the address; the list and the map share the selection", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    await exercise("rynek.otodom.metric", async () => {
      await choose(page.getByRole("combobox", { name: "Co pokazuje kolor" }), "Mediana czynszu");
      return [await outcome.url(page, /metric=rent/)];
    });
    await exercise("rynek.otodom.sort", async () => {
      await choose(page.getByRole("combobox", { name: "Kolejność na liście" }), "Mediana ceny za m²");
      return [await outcome.url(page, /sort=ppm2/)];
    });
    await exercise("rynek.otodom.view.list", async () => {
      await page.getByRole("button", { name: "Lista", exact: true }).click();
      return [await outcome.url(page, /view=list/)];
    });
    await expect(frame(page)).toHaveCount(0);
    await exercise("rynek.otodom.view.map", async () => {
      await page.getByRole("button", { name: "Mapa", exact: true }).click();
      return [await outcome.url(page, /^(?!.*view=)/)];
    });
    const search = page.getByRole("textbox", { name: "Szukaj miejsca na liście" });
    await exercise("rynek.otodom.search", async () => {
      await search.fill("torun");
      return [await outcome.value(search, "torun")];
    });
    await expect(page.getByRole("button", { name: /^Wybierz miejsce /, includeHidden: false })).toHaveCount(
      1,
    ); // "Toruń" found without the diacritic
    await page.goto(OTODOM);
    await search.fill("Białystok");
    const first = page.getByRole("button", { name: "Wybierz miejsce Białystok" });
    await exercise("rynek.otodom.pick", async () => {
      await first.click();
      return [await outcome.url(page, /sel=bialystok/)];
    });
    await expect(page.getByTestId("map-preview")).toContainText("Białystok");
    await exercise("rynek.otodom.open", async () => {
      await page.getByRole("link", { name: "Otwórz miejsce Białystok" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom\/bialystok$/)];
    });
  });

  test("the table shows more places on request and withholds figures it has no right to show", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}?view=list`);
    const rows = page.getByRole("row");
    const before = await rows.count();
    await exercise("rynek.otodom.more", async () => {
      await page.getByRole("button", { name: "Pokaż więcej miejsc" }).click();
      return [
        await outcome.state(
          page.getByRole("button", { name: "Pokaż więcej miejsc" }).or(page.getByRole("table")),
          "class",
          /./,
        ),
      ];
    });
    expect(await rows.count()).toBeGreaterThan(before);
    await expect(page.getByText(/Za mało ofert z ceną \(\d+\), by podać medianę/).first()).toBeVisible();
    await expect(page.getByText(/Brak danych: pierwsze zbieranie/).first()).toBeVisible();
  });

  test("an overview that cannot be read says so and retries", async ({ page, serve }) => {
    const api = await serve(createMarket({ overviewFails: true }));
    await page.goto(OTODOM);
    await expect(page.getByRole("alert").filter({ hasText: "Nie udało się wczytać miejsc" })).toBeVisible();
    await exercise("rynek.otodom.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/overview" })];
    });
  });
});

test.describe("Rynek comparison", () => {
  test("the call to action opens the comparison directly, carries the places and leads to a populated table", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}?view=list`);
    await page.getByRole("button", { name: /^Dodaj do porównania Białystok/ }).click();
    await page.getByRole("button", { name: /^Dodaj do porównania Bydgoszcz/ }).click();
    await expect(page.getByTestId("compare-cta")).toContainText("(2)");
    await exercise("rynek.otodom.compare-toggle", async () => {
      await page.getByRole("button", { name: /^Dodaj do porównania Bytom/ }).click();
      return [await outcome.url(page, /ids=bialystok(,|%2C)bydgoszcz(,|%2C)bytom/)];
    });
    await exercise("rynek.otodom.compare-cta", async () => {
      await page.getByTestId("compare-cta").click();
      return [await outcome.url(page, /view=compare/)];
    });
    const table = page.getByRole("table", { name: "Porównanie miejsc" });
    await expect(table).toBeVisible();
    for (const name of ["Białystok", "Bydgoszcz", "Bytom"])
      await expect(table.getByRole("columnheader", { name })).toBeVisible();
    await expect(table.getByText(/Ceny ofertowe najmu \(Otodom\)/)).toBeVisible();
    await expect(table.getByText(/Kontekst z GUS/)).toBeVisible();
    await expect(page.getByRole("row", { name: /Mediana ceny za m²/ }).first()).toContainText("zł/m²");
    await exercise("rynek.compare.place", async () => {
      await table.getByRole("link", { name: "Białystok" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom\/bialystok/)];
    });
    await page.goBack();
    await exercise("rynek.compare.search", async () => {
      const search = page.getByRole("textbox", { name: "Szukaj miejsca do dodania" });
      await search.fill("Chor");
      return [await outcome.value(search, "Chor")];
    });
    await exercise("rynek.compare.clear", async () => {
      await page.getByRole("button", { name: "Wyczyść porównanie" }).click();
      return [await outcome.url(page, /^(?!.*ids=)/)];
    });
    await exercise("rynek.compare.back", async () => {
      await page.getByRole("button", { name: "Wróć do mapy" }).click();
      return [await outcome.url(page, /^(?!.*view=compare)/)];
    });
  });

  test("with nothing chosen the comparison explains the requirement and offers a picker; additions and the limit are announced", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(OTODOM);
    await page.getByTestId("compare-cta").click();
    await expect(page.getByText("Wybierz co najmniej dwa miejsca")).toBeVisible();
    const search = page.getByRole("textbox", { name: "Szukaj miejsca do dodania" });
    await exercise("rynek.compare.search-empty", async () => {
      await search.fill("Byt");
      return [await outcome.value(search, "Byt")];
    });
    const message = page.getByTestId("compare-message");
    await exercise("rynek.compare.add-empty", async () => {
      await page.getByRole("button", { name: "Dodaj do porównania Bytom" }).click();
      return [await outcome.url(page, /ids=bytom/)];
    });
    await expect(message).toHaveText("Dodano Bytom do porównania (1 z 4).");
    await search.fill("");
    for (const name of ["Białystok", "Bydgoszcz", "Chorzów"])
      await page.getByRole("button", { name: `Dodaj do porównania ${name}` }).click();
    await expect(page.getByText("Osiągnięto limit 4 miejsc. Usuń jedno, aby dodać inne.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Dodaj do porównania Gdańsk" })).toBeDisabled();
    await page.getByRole("button", { name: "Usuń z porównania Bytom" }).click();
    await expect(message).toHaveText("Usunięto Bytom z porównania (3 z 4).");
    await page.reload();
    await expect(page.getByRole("table", { name: "Porównanie miejsc" })).toBeVisible(); // the comparison survives a reload
    await exercise("rynek.compare.back-empty", async () => {
      await page.getByRole("button", { name: "Wróć do mapy" }).click();
      return [await outcome.url(page, /^(?!.*view=compare)/)];
    });
  });
});

test.describe("Rynek place and district", () => {
  test("a place shows cards with their five answers, the median over time, the districts and a way to every other page", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}/bialystok`);
    await expect(page.getByRole("heading", { level: 1, name: "Białystok" })).toBeVisible();
    const card = page.getByRole("article").first();
    for (const word of ["Jednostka", "Źródło", "Próba"])
      await expect(card.getByText(word, { exact: true })).toBeVisible();
    await expect(page.getByRole("figure").first()).toBeVisible();
    await expect(page.getByText("Dzielnicę wskazano przy")).toBeVisible();
    await exercise("rynek.place.series.additions", async () => {
      await page.getByRole("button", { name: "Nowe ogłoszenia dnia" }).click();
      return [await outcome.url(page, /series=additions/)];
    });
    await exercise("rynek.place.series.cohort", async () => {
      await page.getByRole("button", { name: "Okno 90 dób" }).click();
      return [await outcome.url(page, /^(?!.*series=)/)];
    });
    for (const days of [30, 365, 90]) {
      await exercise(`rynek.place.period.${days}`, async () => {
        await page.getByRole("button", { name: `${days} dni`, exact: true }).click();
        return [await outcome.url(page, days === 90 ? /^(?!.*days=)/ : new RegExp(`days=${days}`))];
      });
    }
    await exercise("rynek.place.group", async () => {
      await page
        .getByRole("button", { name: /^Pokaż tylko grupę /, includeHidden: false })
        .first()
        .click();
      return [await outcome.url(page, /cohort=/)];
    });
    await exercise("rynek.place.district-bar", async () => {
      await page.getByRole("link", { name: "Centrum", exact: true }).first().click();
      return [await outcome.url(page, /\/bialystok\/centrum/)];
    });
    await expect(page.getByRole("heading", { level: 1, name: "Centrum" })).toBeVisible();
    await exercise("rynek.district.back", async () => {
      await page.getByRole("link", { name: /^Wróć do: / }).click();
      return [await outcome.url(page, /\/app\/market\/otodom\/bialystok(\?.*)?$/)];
    });
    await exercise("rynek.place.gus", async () => {
      await page.getByRole("link", { name: "Zobacz profil GUS" }).click();
      return [await outcome.url(page, /\/app\/market\/gus\/bialystok$/)];
    });
    await page.goto(`${OTODOM}/bialystok`);
    await exercise("rynek.place.back", async () => {
      await page.getByRole("link", { name: "Wszystkie miejsca" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom(\?.*sel=bialystok.*)?$/)];
    });
    await page.goto(`${OTODOM}/bialystok`);
    await exercise("rynek.place.crumb", async () => {
      await page.getByRole("navigation", { name: "Ścieżka" }).getByRole("link", { name: "Otodom" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom$/)];
    });
  });

  test("the districts are the source's own: withheld ones show counts and no median, a place without any says why", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}/bialystok`);
    const districts = page
      .getByRole("region")
      .or(page.locator("section"))
      .filter({ has: page.getByRole("heading", { name: "Dzielnice" }) });
    await expect(districts.getByText("Za mało ofert z ceną, by podać medianę").first()).toBeVisible();
    await expect(districts.getByText("Dzielnice to podział z ogłoszeń Otodom")).toBeVisible();
    await page.goto(`${OTODOM}/bydgoszcz`);
    await expect(page.getByText("Otodom nie wskazuje dzielnic dla tego miejsca")).toBeVisible();
    await page.goto(`${OTODOM}/bydgoszcz/centrum`);
    await expect(page.getByText("Otodom nie wskazuje dzielnic dla tego miejsca").first()).toBeVisible();
  });

  test("a district shows its own figures, a way back and the other districts; there is no history to draw", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto(`${OTODOM}/bialystok/centrum`);
    await expect(page.getByText(/nie prowadzimy historii/)).toBeVisible();
    await expect(page.getByText("Dzielnica według ogłoszeń Otodom")).toBeVisible();
    await exercise("rynek.district.other", async () => {
      await page.getByRole("link", { name: "Północ", exact: true }).click();
      return [await outcome.url(page, /\/bialystok\/polnoc/)];
    });
    await exercise("rynek.district.crumb-place", async () => {
      await page
        .getByRole("navigation", { name: "Ścieżka" })
        .getByRole("link", { name: "Białystok" })
        .click();
      return [await outcome.url(page, /\/app\/market\/otodom\/bialystok/)];
    });
    await page.goto(`${OTODOM}/bialystok/centrum`);
    await exercise("rynek.district.crumb", async () => {
      await page.getByRole("navigation", { name: "Ścieżka" }).getByRole("link", { name: "Otodom" }).click();
      return [await outcome.url(page, /\/app\/market\/otodom$/)];
    });
    await page.goto(`${OTODOM}/bialystok/rubinkowo`);
    await expect(
      page.getByText("Za mało ofert z ceną, by podać medianę", { exact: true }).first(),
    ).toBeVisible();
    await page.goto(`${OTODOM}/bialystok/nigdzie`);
    await expect(page.getByText("Nie ma takiej dzielnicy w tym miejscu")).toBeVisible();
  });

  test("states that cannot be shown say so and offer a retry or the way back", async ({ page, serve }) => {
    await serve("market");
    for (const [id, path] of [
      ["rynek.place.back-nodistricts", `${OTODOM}/bydgoszcz`],
      ["rynek.place.back-unavailable", `${OTODOM}/kielce`],
      ["rynek.place.back-notfound", `${OTODOM}/nie-ma-takiej`],
    ] as const) {
      await page.goto(path);
      await exercise(id, async () => {
        await page.getByRole("link", { name: "Wszystkie miejsca" }).click();
        return [await outcome.url(page, /\/app\/market\/otodom/)];
      });
    }
    for (const [id, options, alert, request] of [
      [
        "rynek.place.retry-detail",
        { detailFails: true },
        "Nie udało się wczytać miejsca",
        /\/api\/market\/locations\/bialystok$/,
      ],
      [
        "rynek.place.retry-history",
        { historyFails: true },
        "Nie udało się wczytać historii odczytów",
        /history$/,
      ],
      [
        "rynek.place.retry-districts",
        { districtsFail: true },
        "Nie udało się wczytać dzielnic",
        /districts$/,
      ],
    ] as const) {
      const api = await serve(createMarket(options));
      await page.goto(`${OTODOM}/bialystok`);
      await expect(page.getByRole("alert").filter({ hasText: alert })).toBeVisible();
      await exercise(id, async () => {
        await page
          .getByRole("alert")
          .filter({ hasText: alert })
          .getByRole("button", { name: "Spróbuj ponownie" })
          .click();
        return [await outcome.request(api, { method: "GET", path: request })];
      });
    }
  });
});

test.describe("GUS ranking", () => {
  test("the card shows the score, the position with its denominator and cohort, what higher means, every component and the exclusions", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/gus/bialystok");
    const card = page.getByTestId("ranking-card");
    await expect(card.getByText("Eksperymentalny", { exact: true })).toBeVisible();
    await expect(card.getByTestId("index-score")).toContainText("z 100");
    await expect(card.getByTestId("index-position")).toContainText(/miejsce \d+ z 2\s479/);
    await expect(card.getByText(/wśród: gminy w Polsce z kompletnym indeksem/)).toBeVisible();
    await expect(card.getByText("Wyższy wynik = korzystniejsze statystyki lokalne")).toBeVisible();
    await expect(card.getByText(/Nie jest wyceną nieruchomości/)).toBeVisible();
    await expect(card.getByText(/Wersja metody: 1/)).toBeVisible();
    await expect(
      card.getByRole("table", { name: /Wskaźniki wchodzące do wyniku/ }).getByRole("row"),
    ).toHaveCount(7);
    await exercise("rynek.gus.component", async () => {
      await card
        .getByRole("link", { name: /^Szczegóły wskaźnika: / })
        .first()
        .click();
      return [await outcome.url(page, /#metric-/)];
    });
  });

  test("a place that cannot be scored gets an honest unavailable state with the reason and no number", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/gus/chorzow");
    const card = page.getByTestId("ranking-card");
    await expect(card).toBeVisible();
    await expect(card.getByTestId("index-score")).toHaveCount(0);
    await expect(
      card.getByText(/Powody|Za mało danych|Nie podajemy wyniku|Wynik jest, ale bez pozycji/).first(),
    ).toBeVisible();
  });

  test("the leaderboard ranks places, picks one, compares up to four and loads more", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/gus");
    await expect(page.getByRole("table", { name: /Mianownik pozycji to 2\s400/ })).toBeVisible();
    const search = page.getByRole("textbox", { name: "Miejsce" });
    await exercise("rynek.gus.picker.search", async () => {
      await search.fill("Byd");
      return [await outcome.value(search, "Byd")];
    });
    await exercise("rynek.gus.picker.pick", async () => {
      await page.getByRole("button", { name: "Bydgoszcz", exact: true }).click();
      return [await outcome.url(page, /\/app\/market\/gus\/bydgoszcz/)];
    });
    await exercise("rynek.gus.leaderboard.pick", async () => {
      await page
        .getByRole("button", { name: /^Pokaż wynik /, includeHidden: false })
        .first()
        .click();
      return [await outcome.url(page, /\/app\/market\/gus\/[a-z-]+/)];
    });
    await exercise("rynek.gus.leaderboard.compare", async () => {
      await page.getByRole("button", { name: /^Dodaj do porównania Białystok/ }).click();
      return [await outcome.url(page, /ids=bialystok/)];
    });
    await page.getByRole("button", { name: /^Dodaj do porównania Bydgoszcz/ }).click();
    await expect(page.getByRole("table", { name: "Porównanie wskaźników" })).toBeVisible();
    await expect(page.getByRole("row", { name: /Wynik indeksu/ })).toContainText("z 100");
    const before = await page
      .getByRole("table", { name: /Mianownik pozycji/ })
      .getByRole("row")
      .count();
    await exercise("rynek.gus.leaderboard.more", async () => {
      await page.getByRole("button", { name: "Pokaż więcej miejsc" }).click();
      return [await outcome.state(page.getByRole("table", { name: /Mianownik pozycji/ }), "class", /./)];
    });
    expect(
      await page
        .getByRole("table", { name: /Mianownik pozycji/ })
        .getByRole("row")
        .count(),
    ).toBeGreaterThan(before);
  });

  test("the profile shows each indicator with its unit, level and year, and an annual chart with a table on request", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/gus/bialystok");
    const profile = page.locator("#metric-population_total");
    await expect(profile).toBeVisible();
    await expect(profile.getByText("Jednostka", { exact: true })).toBeVisible();
    await profile.getByText("Pokaż przebieg w latach").click();
    await expect(profile.getByRole("group", { name: /Przebieg: / })).toBeVisible();
    await expect(profile.getByRole("table")).toBeVisible();
  });

  test("a ranking that cannot be read says so and retries; the account's restricted list is respected", async ({
    page,
    serve,
  }) => {
    const api = await serve(createMarket({ rankingFails: true }));
    await page.goto("/app/market/gus/bialystok");
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się wczytać rankingu" }).first(),
    ).toBeVisible();
    await exercise("rynek.gus.retry", async () => {
      await page
        .getByRole("alert")
        .filter({ hasText: "Nie udało się wczytać rankingu" })
        .first()
        .getByRole("button", { name: "Spróbuj ponownie" })
        .click();
      return [await outcome.request(api, { method: "GET", path: /\/ranking$/ })];
    });
    await serve("marketFree");
    await page.goto("/app/market/gus");
    await expect(page.getByRole("table", { name: /Mianownik pozycji/ }).getByRole("row")).toHaveCount(21); // 20 places and the header
  });
});
