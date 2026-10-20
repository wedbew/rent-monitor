import type { Locator, Page } from "@playwright/test";

import { createMarket } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const map = (page: Page) => page.getByRole("img", { name: /Mapa miejsc/ });
const box = async (svg: Locator) => (await svg.getAttribute("viewBox")) ?? "";
const notEqual = (value: string) => new RegExp(`^(?!${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$)`);

async function choose(select: Locator, label: string): Promise<void> {
  await select.click();
  await select.page().getByRole("option", { name: label, exact: true }).click();
}

test.describe("Rynek: map, list and comparison", () => {
  test("opens on a map of areas coloured by a published figure, with the legend, the source and an honest note", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market");
    await expect(map(page)).toBeVisible();
    await expect(page.getByRole("list", { name: "Legenda" })).toContainText("Brak danych lub za mało ofert");
    await expect(page.getByText(/nie położenie ogłoszeń/)).toBeVisible();
    await expect(page.getByText("Granice: Państwowy Rejestr Granic, GUGiK.")).toBeVisible();
    await expect(page.locator("path[data-place]").first()).toBeVisible(); // at least one place has an area
    // a place with no gmina is only in the table, never invented on the map
    await expect(page.getByText("Miejsca bez przypisanej gminy są tylko w tabeli.")).toBeVisible();
  });

  test("the view, the colour measure, the order and the selection are in the address", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market");
    await exercise("market.explore.metric", async () => {
      await choose(page.getByRole("combobox", { name: "Kolor mapy" }), "Mediana czynszu");
      return [await outcome.url(page, /metric=rent/)];
    });
    await exercise("market.explore.sort", async () => {
      await choose(page.getByRole("combobox", { name: "Kolejność miejsc" }), "Mediana za m²");
      return [await outcome.url(page, /sort=ppm2/)];
    });
    await page.reload();
    await expect(page.getByRole("combobox", { name: "Kolor mapy" })).toContainText("Mediana czynszu");
    await expect(page.getByRole("combobox", { name: "Kolejność miejsc" })).toContainText("Mediana za m²");
  });

  test("zoom, zoom out and reset change the view of the map and never leave the country", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market");
    const svg = map(page);
    const whole = await box(svg);
    await exercise("market.explore.zoom-in", async () => {
      await page.getByRole("button", { name: "Przybliż" }).click();
      return [await outcome.state(svg, "viewBox", notEqual(whole))];
    });
    const closer = await box(svg);
    await exercise("market.explore.zoom-out", async () => {
      await page.getByRole("button", { name: "Oddal" }).click();
      return [await outcome.state(svg, "viewBox", notEqual(closer))];
    });
    await page.getByRole("button", { name: "Przybliż" }).click();
    await exercise("market.explore.reset", async () => {
      await page.getByRole("button", { name: "Cała Polska" }).click();
      return [await outcome.state(svg, "viewBox", whole)];
    });
  });

  test("choosing a place from the table selects it in the panel and the address, the link opens it", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market");
    const first = page.getByRole("button", { name: /^Wybierz miejsce / }).first();
    await exercise("market.explore.pick", async () => {
      await first.click();
      return [await outcome.url(page, /sel=bialystok/)];
    });
    await expect(first).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByRole("region", { name: "Wybrane miejsce" })).toContainText("Białystok");
    await expect(page.locator("path[data-place=bialystok], circle[data-place=bialystok]")).toHaveClass(
      /selected/,
    );
    await exercise("market.explore.open", async () => {
      await page.getByRole("link", { name: "Otwórz miejsce" }).click();
      return [await outcome.url(page, /\/app\/market\/bialystok$/)];
    });
    await expect(page.getByRole("heading", { level: 1, name: "Białystok" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Kontekst lokalizacji (GUS)" })).toBeVisible();
  });

  test("a place is also selectable from the keyboard alone, through the table", async ({ page, serve }) => {
    await serve("market");
    await page.goto("/app/market");
    const target = page.getByRole("button", { name: "Wybierz miejsce Bydgoszcz" });
    await target.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/sel=bydgoszcz/);
    await expect(target).toHaveAttribute("aria-pressed", "true");
  });

  test("the comparison holds up to four places, shows the unit and year of each figure and can be edited", async ({
    page,
    serve,
  }) => {
    const api = await serve("market");
    await page.goto("/app/market");
    await exercise("market.explore.compare.add", async () => {
      await page.getByRole("button", { name: "Dodaj do porównania Białystok" }).click();
      return [await outcome.url(page, /ids=bialystok$/)];
    });
    for (const name of ["Bydgoszcz", "Bytom", "Chorzów"])
      await page.getByRole("button", { name: `Dodaj do porównania ${name}` }).click();
    await expect(page.getByRole("button", { name: "Dodaj do porównania Elbląg" })).toBeDisabled();
    await page.getByRole("button", { name: "Porównanie" }).click();
    const table = page.getByRole("table", { name: "Porównanie miejsc" });
    await expect(table).toBeVisible();
    await expect(page.getByText(/nie są porównywalne wprost/)).toBeVisible();
    await expect(table.getByRole("row", { name: /Ludność ogółem/ })).toContainText("Białystok, 2025");
    await expect(table.getByRole("row", { name: /Mediana cen za 1 m²/ })).toContainText(
      "Powiat testowy, 2025",
    );
    expect(api.requests.filter((r) => r.path.endsWith("/context"))).toHaveLength(4);
    await exercise("market.explore.compare.remove", async () => {
      await page.getByRole("button", { name: "Usuń z porównania Chorzów" }).click();
      return [await outcome.url(page, /ids=bialystok%2Cbydgoszcz%2Cbytom$/)];
    });
    await exercise("market.explore.compare.place", async () => {
      await table.getByRole("link", { name: "Bytom" }).click();
      return [await outcome.url(page, /\/app\/market\/bytom$/)];
    });
  });

  test("the view switch works from the map and from the list and survives reload, Back and Forward", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market");
    await exercise("market.explore.view.list", async () => {
      await page.getByRole("button", { name: "Lista" }).click();
      return [await outcome.url(page, /view=list/)];
    });
    await exercise("market.explore.view.compare", async () => {
      await page.getByRole("button", { name: "Porównanie" }).click();
      return [await outcome.url(page, /view=compare/)];
    });
    await exercise("market.explore.view.map", async () => {
      await page.getByRole("button", { name: "Mapa" }).click();
      return [await outcome.url(page, /^(?!.*view=).*$/)];
    });
    await page.goBack();
    await expect(page).toHaveURL(/view=compare/);
    await page.getByRole("button", { name: "Lista" }).click();
    await exercise("market.list.view.map", async () => {
      await page.getByRole("button", { name: "Mapa" }).click();
      return [await outcome.url(page, /^(?!.*view=).*$/)];
    });
    await page.getByRole("button", { name: "Lista" }).click();
    await exercise("market.list.view.compare", async () => {
      await page.getByRole("button", { name: "Porównanie" }).click();
      return [await outcome.url(page, /view=compare/)];
    });
    await page.getByRole("button", { name: "Lista" }).click();
    await exercise("market.list.view.list", async () => {
      await page.getByRole("button", { name: "Lista" }).click();
      return [await outcome.url(page, /view=list/)];
    });
    await page.reload();
    await expect(page.getByRole("table")).toBeVisible();
  });

  test("a free account sees the cap and the way to unlock; a closed place offers the same, not an error", async ({
    page,
    serve,
  }) => {
    await serve("marketFree");
    await page.goto("/app/market");
    await expect(page.getByText("Konto darmowe: widzisz 20 z 38 miejsc")).toBeVisible();
    await expect(page.getByRole("table").getByRole("rowheader")).toHaveCount(20);
    const closed = createMarket().places[30]?.location_id ?? "";
    await page.goto(`/app/market/${closed}`);
    await expect(page.getByText("To miejsce nie należy do darmowej listy")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Kontekst lokalizacji (GUS)" })).toHaveCount(0);
    await page.goto("/app/market");
    await exercise("market.explore.upgrade", async () => {
      await page.getByRole("link", { name: "Kup pakiet raportów" }).click();
      return [await outcome.url(page, /\/app\/credits$/)];
    });
  });

  test("an overview that cannot be read keeps the page, says so and can be retried", async ({
    page,
    serve,
  }) => {
    const api = await serve(createMarket({ overviewFails: true }));
    await page.goto("/app/market");
    await expect(page.getByRole("alert").filter({ hasText: "Nie udało się wczytać rynku" })).toBeVisible();
    await expect(page.getByRole("table")).toHaveCount(0);
    await exercise("market.explore.retry", async () => {
      await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
      return [await outcome.request(api, { method: "GET", path: "/api/market/overview" })];
    });
  });

  test("an unmatched place and an ambiguous place say what is missing and never show a made-up figure", async ({
    page,
    serve,
  }) => {
    await serve("market");
    const places = createMarket().places;
    await page.goto(`/app/market/${places[10]?.location_id}`);
    await expect(page.getByText("Miejsce nie ma przypisanej gminy")).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(0);
    await page.goto(`/app/market/${places[6]?.location_id}`);
    await expect(page.getByText("Kilka gmin pasuje do nazwy")).toBeVisible();
    await expect(page.getByText(/Gmina A, Gmina B/)).toBeVisible();
  });

  test("the context shows the unit and year of each figure, a proxy label and the values as a table", async ({
    page,
    serve,
  }) => {
    await serve("market");
    await page.goto("/app/market/bialystok");
    const population = page.getByRole("article", { name: "Ludność ogółem" });
    await expect(population).toContainText("Białystok, rok 2025");
    await expect(population).toContainText("Dane tej jednostki");
    await expect(population).toContainText("Za mało danych, by podać pozycję");
    await population.getByText("Wartości w kolejnych latach").click();
    await expect(population.getByRole("row")).toHaveCount(11);
    await expect(page.getByRole("article", { name: /Mediana cen za 1 m²/ })).toContainText(
      "Dane szerszej jednostki",
    );
  });
});
