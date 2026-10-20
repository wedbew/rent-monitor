import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../api/query";
import { RequireSession, SessionProvider } from "../../shell/session";
import { useScenario } from "../../test/handlers";
import { createMarket } from "../../test/scenarios";
import { LocationPage } from "./LocationPage";
import { MarketPage } from "./MarketPage";

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderAt(initial: string, { retry = true }: { retry?: boolean } = {}) {
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/market",
            element: (
              <>
                <MarketPage />
                <Where />
              </>
            ),
          },
          {
            path: "/app/market/:locationId",
            element: (
              <>
                <LocationPage />
                <Where />
              </>
            ),
          },
        ],
      },
    ],
    { initialEntries: [initial] },
  );
  const client = createQueryClient();
  // A 503 is retried twice with a growing delay (api/query.ts); the tests that look at the failure turn it off.
  if (!retry) client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, retry: false } });
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return router;
}

const rowOf = (name: string) => screen.getByRole("rowheader", { name }).closest("tr") as HTMLElement;

describe("Rynek: the list", () => {
  it("shows places in the server's order with honest cells for withheld and unavailable data", async () => {
    const market = createMarket();
    useScenario(market);
    renderAt("/app/market");
    const table = await screen.findByRole("table");
    expect(
      within(table)
        .getAllByRole("columnheader")
        .map((h) => h.textContent),
    ).toEqual(["Miejscowość", "Dane", "Mediana czynszu", "Mediana za m²", "Oferty z ceną", "Ostatni odczyt"]);
    const first = market.places[0];
    expect(within(table).getAllByRole("rowheader")[0]).toHaveTextContent(first?.name ?? "");
    const withheld = market.places.find((p) => p.withheld_reason !== null);
    const unavailable = market.places.find((p) => p.data_status === "unavailable");
    expect(withheld && unavailable).toBeTruthy();
    // Page one holds the first 30; pick rows that are on it.
    const shown = market.places.slice(0, 30);
    const w = shown.find((p) => p.withheld_reason !== null);
    const u = shown.find((p) => p.data_status === "unavailable");
    if (w === undefined || u === undefined)
      throw new Error("the scenario lacks a withheld or unavailable place");
    expect(rowOf(w.name)).toHaveTextContent("Za mało ofert z ceną, by podać medianę");
    expect(rowOf(w.name)).not.toHaveTextContent("0,00");
    expect(rowOf(u.name)).toHaveTextContent("Brak danych");
    expect(within(rowOf(u.name)).getAllByText("nie obliczono").length).toBeGreaterThanOrEqual(3);
  });

  it("formats the figures through the shared formatters, with the unit only on a real value", async () => {
    const market = createMarket();
    useScenario(market);
    renderAt("/app/market");
    await screen.findByRole("table");
    const sufficient = market.places.slice(0, 30).find((p) => p.sufficient === true);
    if (sufficient === undefined) throw new Error("no sufficient place on page one");
    const row = rowOf(sufficient.name);
    expect(row.textContent).toMatch(/zł\/m²/);
    expect(row.textContent).not.toMatch(/nie obliczono\s*zł/);
  });

  it("pages over the cursor: 38 places come as 30 then 8, each once, and the end is the missing cursor", async () => {
    useScenario(createMarket({ count: 38 }));
    renderAt("/app/market");
    await screen.findByRole("table");
    expect(screen.getAllByRole("rowheader")).toHaveLength(30);
    await userEvent.click(screen.getByRole("button", { name: "Załaduj więcej" }));
    await waitFor(() => expect(screen.getAllByRole("rowheader")).toHaveLength(38));
    expect(new Set(screen.getAllByRole("rowheader").map((h) => h.textContent)).size).toBe(38);
    expect(screen.queryByRole("button", { name: "Załaduj więcej" })).toBeNull();
    expect(screen.getByText("To wszystkie miejscowości (38).")).toBeInTheDocument();
  });

  it("puts the search in the address, sends it to the API and restores it from a shared link", async () => {
    const market = createMarket();
    useScenario(market);
    const router = renderAt("/app/market?q=gd");
    await screen.findByRole("table");
    expect(screen.getByRole("textbox", { name: "Nazwa miejscowości" })).toHaveValue("gd");
    expect(screen.getAllByRole("rowheader").map((h) => h.textContent)).toEqual(["Gdańsk", "Gdynia"]);
    expect(market.state.requests.at(-1)).toContain("q=gd");
    await userEvent.clear(screen.getByRole("textbox", { name: "Nazwa miejscowości" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Nazwa miejscowości" }), "toru");
    await userEvent.click(screen.getByRole("button", { name: "Szukaj" }));
    await waitFor(() => expect(router.state.location.search).toBe("?q=toru"));
    expect(await screen.findByRole("rowheader", { name: "Toruń" })).toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "Gdańsk" })).toBeNull();
  });

  it("says no place matches, and clearing the search brings the list back", async () => {
    useScenario(createMarket());
    renderAt("/app/market?q=zzzz");
    expect(await screen.findByText("Żadna miejscowość nie pasuje do wyszukiwania")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Wyczyść wyszukiwanie" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });

  it("an empty catalogue says there is no data yet and shows no numbers or table", async () => {
    useScenario("marketEmpty");
    renderAt("/app/market");
    expect(await screen.findByText("Nie ma jeszcze danych rynkowych")).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("a failed list says so and can be retried", async () => {
    useScenario("marketListFailing");
    renderAt("/app/market", { retry: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Nie udało się wczytać rynku");
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });

  it("a failed next page keeps the places and offers the same button again", async () => {
    const market = createMarket({ count: 38, failPage: 1 });
    useScenario(market);
    renderAt("/app/market", { retry: false });
    await screen.findByRole("table");
    await userEvent.click(screen.getByRole("button", { name: "Załaduj więcej" }));
    expect(await screen.findByText("Nie udało się wczytać kolejnych miejscowości")).toBeInTheDocument();
    expect(screen.getAllByRole("rowheader")).toHaveLength(30);
    market.state.failing = false;
    await userEvent.click(screen.getByRole("button", { name: "Załaduj więcej" }));
    await waitFor(() => expect(screen.getAllByRole("rowheader")).toHaveLength(38));
  });
});

describe("Rynek: one place", () => {
  const sufficient = () => {
    const market = createMarket();
    const place = market.places.find((p) => p.data_status === "fresh" && p.sufficient === true);
    if (place === undefined) throw new Error("no fresh sufficient place");
    return { market, place };
  };

  it("shows the latest reading, the history newest first and how to read the figures", async () => {
    const { market, place } = sufficient();
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    expect(await screen.findByRole("heading", { level: 1, name: place.name })).toBeInTheDocument();
    const heading = await screen.findByRole("heading", { name: "Ostatni odczyt" });
    const block = heading.closest("section") as HTMLElement;
    expect(block).toHaveTextContent("Mediana czynszu");
    expect(block).toHaveTextContent("zł/m²");
    const table = await screen.findByRole("table", { name: /Od najnowszego odczytu/ });
    const dates = within(table)
      .getAllByRole("rowheader")
      .map((h) => h.textContent ?? "");
    expect(dates.length).toBeGreaterThan(60); // 90 days minus the days without a reading
    expect(dates.length).toBeLessThan(90);
    expect(dates[0]).toContain("19 października 2026");
    expect(screen.getByText("To ceny z ogłoszeń, a nie czynsze zapłacone w umowach.")).toBeInTheDocument();
    expect(screen.getByText("To nie są ceny transakcyjne z aktów notarialnych.")).toBeInTheDocument();
  });

  it("days without a published reading are absent, never zero", async () => {
    const { market, place } = sufficient();
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    const table = await screen.findByRole("table", { name: /Od najnowszego odczytu/ });
    expect(table.textContent).not.toMatch(/0,00\s*zł/);
    const rows = within(table).getAllByRole("rowheader");
    const days = rows.map((r) => r.textContent);
    expect(new Set(days).size).toBe(days.length);
    expect(days).not.toContain("14 października 2026"); // offset 5 is a gap day in the mock
  });

  it("changing series, period and cohort changes the address and the request, and keeps the search", async () => {
    const { market, place } = sufficient();
    useScenario(market);
    renderAt(`/app/market/${place.location_id}?q=${encodeURIComponent(place.name.slice(0, 3))}`);
    await screen.findByRole("table", { name: /Od najnowszego odczytu/ });
    await userEvent.click(screen.getByRole("button", { name: "Nowe ogłoszenia dnia" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("series=additions"));
    await userEvent.click(screen.getByRole("button", { name: "30 dni" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("days=30"));
    await userEvent.click(screen.getByRole("combobox", { name: "Grupa mieszkań" }));
    await userEvent.click(await screen.findByRole("option", { name: "2 pokoje" }));
    await waitFor(() => expect(screen.getByTestId("where").textContent).toContain("cohort=rooms_2"));
    const where = screen.getByTestId("where").textContent ?? "";
    expect(where).toContain(`q=${encodeURIComponent(place.name.slice(0, 3))}`);
    await waitFor(() => {
      const last = market.state.requests.at(-1) ?? "";
      expect(last).toContain("series=additions");
      expect(last).toContain("cohort=rooms_2");
      expect(last).toContain("days=30");
    });
    expect(screen.getByText(/Dni nie wolno łączyć z oknem 90 dni/)).toBeInTheDocument();
  });

  it("a small sample keeps its counts and withholds the numbers with the reason", async () => {
    const market = createMarket();
    const place = market.places.find((p) => p.sufficient === false);
    if (place === undefined) throw new Error("no withheld place");
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    const block = (await screen.findByRole("heading", { name: "Ostatni odczyt" })).closest(
      "section",
    ) as HTMLElement;
    expect(within(block).getByText("Za mało ofert z ceną, by podać medianę")).toBeInTheDocument();
    expect(block).toHaveTextContent("Oferty z ceną");
    expect(block).not.toHaveTextContent("0,00");
  });

  it("an unavailable place shows its state and no numbers, controls or history request", async () => {
    const market = createMarket();
    const place = market.places.find((p) => p.data_status === "unavailable");
    if (place === undefined) throw new Error("no unavailable place");
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    expect(
      await screen.findByText(/nie zakończyło się jeszcze pierwsze zbieranie ofert/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /Od najnowszego odczytu/ })).toBeNull();
    expect(screen.queryByRole("group", { name: "Okres" })).toBeNull();
    expect(market.state.requests.some((r) => r.includes("/history"))).toBe(false);
  });

  it("a stale place says the numbers are historical and names the gap", async () => {
    const market = createMarket();
    const place = market.places.find((p) => p.data_status === "stale");
    if (place === undefined) throw new Error("no stale place");
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    expect(await screen.findByText(/Traktuj liczby jako historyczne/)).toBeInTheDocument();
    expect(screen.getByText(/Luka w zbieraniu ofert od 14 października 2026/)).toBeInTheDocument();
  });

  it("an unknown place is a calm not-found with the way back, keeping the search", async () => {
    useScenario(createMarket());
    renderAt("/app/market/nie-ma-takiej?q=gd");
    expect(await screen.findByText("Nie ma takiej miejscowości")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wszystkie miejscowości" })).toHaveAttribute(
      "href",
      "/app/market?view=list&q=gd",
    );
  });

  it("a failed place can be retried; a failed history says so without hiding the place", async () => {
    const failing = createMarket({ detailFails: true });
    useScenario(failing);
    renderAt("/app/market/torun", { retry: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Nie udało się wczytać miejscowości");
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });

  it("a history that cannot be read keeps the place, its status and the way back", async () => {
    const market = createMarket({ historyFails: true });
    const place = market.places.find((p) => p.data_status === "fresh");
    if (place === undefined) throw new Error("no fresh place");
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`, { retry: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("Nie udało się wczytać miejscowości");
    expect(screen.getByRole("heading", { level: 1, name: place.name })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wszystkie miejscowości" })).toBeInTheDocument();
  });

  it("a place with no published reading in the period says so instead of drawing zeros", async () => {
    const market = createMarket({ historyEmpty: true });
    const place = market.places.find((p) => p.data_status === "fresh");
    if (place === undefined) throw new Error("no fresh place");
    useScenario(market);
    renderAt(`/app/market/${place.location_id}`);
    expect(await screen.findByText("Brak odczytów w wybranym okresie")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: /Od najnowszego odczytu/ })).toBeNull();
  });

  it("ignores an unknown value in the address instead of sending it to the API", async () => {
    const { market, place } = sufficient();
    useScenario(market);
    renderAt(`/app/market/${place.location_id}?series=deed&cohort=zzz&days=7`);
    await screen.findByRole("table", { name: /Od najnowszego odczytu/ });
    const last = market.state.requests.filter((r) => r.includes("/history")).at(-1) ?? "";
    expect(last).toContain("series=cohort");
    expect(last).toContain("cohort=all");
    expect(last).toContain("days=90");
  });
});
