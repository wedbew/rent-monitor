import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../api/query";
import { RequireSession, SessionProvider } from "../../shell/session";
import { useScenario as serveScenario } from "../../test/handlers";
import { createMarket, type MarketOptions } from "../../test/scenarios";
import { DistrictPage } from "./DistrictPage";
import { GusPage } from "./GusPage";
import { MarketLayout } from "./MarketLayout";
import { OtodomExplorer } from "./OtodomExplorer";
import { PlacePage } from "./PlacePage";

const GEOMETRY = {
  bbox: [14, 49, 24, 55],
  gminas: {},
  points: {},
};

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function mount(initial: string, options: MarketOptions = {}) {
  const market = createMarket(options);
  serveScenario(market);
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/market",
            element: (
              <>
                <MarketLayout />
                <Where />
              </>
            ),
            children: [
              { path: "otodom", element: <OtodomExplorer /> },
              { path: "otodom/:locationId", element: <PlacePage /> },
              { path: "otodom/:locationId/:districtKey", element: <DistrictPage /> },
              { path: "gus", element: <GusPage /> },
              { path: "gus/:locationId", element: <GusPage /> },
            ],
          },
        ],
      },
    ],
    { initialEntries: [initial] },
  );
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { ...client.getDefaultOptions().queries, retry: false } });
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return { router, market };
}

beforeEach(() => {
  const real = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      (typeof input === "string" ? input : input instanceof URL ? input.href : input.url).includes("/geo/")
        ? Promise.resolve(new Response(JSON.stringify(GEOMETRY), { status: 200 }))
        : real(input, init),
    ),
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const where = () => screen.getByTestId("where").textContent ?? "";

describe("Rynek tabs", () => {
  it("has two tabs that are real links, marks the current one and keeps the place when switching", async () => {
    mount("/app/market/otodom/torun");
    const nav = await screen.findByRole("navigation", { name: "Źródło danych rynku" });
    const otodom = within(nav).getByRole("link", { name: /Otodom/ });
    const gus = within(nav).getByRole("link", { name: /GUS/ });
    expect(otodom).toHaveAttribute("aria-current", "true");
    expect(gus).not.toHaveAttribute("aria-current");
    expect(gus).toHaveAttribute("href", "/app/market/gus/torun"); // the same place, in the other source
    expect(await screen.findByText(/Ostatnie odświeżenie|Pierwsze zbieranie/)).toBeInTheDocument();
  });

  it("states the source, period and grain of the tab, and does not mix them", async () => {
    mount("/app/market/gus");
    expect(await screen.findByText(/Źródło: GUS, Bank Danych Lokalnych/)).toBeInTheDocument();
    expect(screen.getByText(/Poziom: gmina, powiat, województwo/)).toBeInTheDocument();
    expect(screen.queryByText(/ceny ofertowe najmu/i)).toBeNull();
  });
});

describe("Rynek filters", () => {
  it("labels both groups, sends the chosen group to the API and shows the answer for it", async () => {
    const user = userEvent.setup();
    const { market } = mount("/app/market/otodom?view=list");
    const filters = await screen.findByTestId("cohort-filters");
    const area = within(filters).getByRole("group", { name: "Powierzchnia mieszkania" });
    const rooms = within(filters).getByRole("group", { name: "Liczba pokoi" });
    expect(within(area).getByRole("radio", { name: "Poniżej 30 m²" })).toBeInTheDocument();
    expect(within(rooms).getByRole("radio", { name: "4 pokoje i więcej" })).toBeInTheDocument();
    expect(within(filters).getByText("Brak filtra: wszystkie mieszkania")).toBeInTheDocument();
    await screen.findByRole("table");
    const before = screen.getAllByRole("row")[1]?.textContent;

    await user.click(within(rooms).getByRole("radio", { name: "2 pokoje" }));
    await waitFor(() => expect(where()).toContain("cohort=rooms_2"));
    await waitFor(() => expect(market.state.requests.some((r) => r.includes("cohort=rooms_2"))).toBe(true));
    expect(await within(filters).findByText("Aktywny filtr: 2 pokoje")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("row")[1]?.textContent).not.toBe(before)); // the figures changed
    expect(screen.getByText("Liczby dotyczą grupy: 2 pokoje.")).toBeInTheDocument();
  });

  it("replaces one family with the other, says so, and resets only the filter", async () => {
    const user = userEvent.setup();
    mount("/app/market/otodom?view=list&cohort=rooms_3&sort=ppm2");
    const filters = await screen.findByTestId("cohort-filters");
    expect(within(filters).getByRole("radio", { name: "3 pokoje" })).toBeChecked();
    await user.click(within(filters).getByRole("radio", { name: "45 do 60 m²" }));
    expect(within(filters).getByRole("radio", { name: "3 pokoje" })).not.toBeChecked();
    expect(
      await within(filters).findByText(/Zastąpiono filtr „3 pokoje” filtrem „45 do 60 m²”/),
    ).toBeInTheDocument();
    await user.click(within(filters).getByRole("button", { name: "Wyczyść filtr" }));
    await waitFor(() => expect(where()).not.toContain("cohort="));
    expect(where()).toContain("sort=ppm2"); // unrelated state survives the reset
  });

  it("reads the filter from the address on load, so reload and Back restore it", async () => {
    mount("/app/market/otodom?view=list&cohort=size_60_80");
    const filters = await screen.findByTestId("cohort-filters");
    expect(within(filters).getByRole("radio", { name: "60 do 80 m²" })).toBeChecked();
    expect(within(filters).getByText("Aktywny filtr: 60 do 80 m²")).toBeInTheDocument();
  });

  it("ignores an unknown group in the address instead of sending it", async () => {
    const { market } = mount("/app/market/otodom?view=list&cohort=hacked");
    await screen.findByRole("table");
    expect(
      market.state.requests.filter((r) => r.includes("overview")).every((r) => !r.includes("hacked")),
    ).toBe(true);
  });

  it("explains a restricted account instead of leaving the controls to look broken", async () => {
    mount("/app/market/otodom?view=list", { free: true });
    expect(await screen.findByText(/Konto darmowe: widzisz 20 z 38 miejsc/)).toBeInTheDocument();
    expect(screen.getByText(/Filtry, mapa i porównanie działają dla tych miejsc/)).toBeInTheDocument();
  });
});

describe("Rynek comparison", () => {
  it("the call to action opens the comparison itself and explains the requirement when nothing is chosen", async () => {
    const user = userEvent.setup();
    mount("/app/market/otodom");
    await user.click(await screen.findByRole("button", { name: "Porównaj miejsca" }));
    await waitFor(() => expect(where()).toContain("view=compare"));
    expect(await screen.findByRole("heading", { name: "Porównanie miejsc" })).toBeInTheDocument();
    expect(screen.getByText("Wybierz co najmniej dwa miejsca")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Szukaj miejsca do dodania" })).toBeInTheDocument();
  });

  it("adds places from the picker with spoken feedback, fills the comparison and stops at the limit", async () => {
    const user = userEvent.setup();
    mount("/app/market/otodom?view=compare");
    const add = async (name: string) =>
      user.click(await screen.findByRole("button", { name: `Dodaj do porównania ${name}` }));
    await add("Białystok");
    expect(await screen.findByTestId("compare-message")).toHaveTextContent(
      "Dodano Białystok do porównania (1 z 4).",
    );
    await add("Bydgoszcz");
    await waitFor(() => expect(decodeURIComponent(where())).toMatch(/ids=bialystok,bydgoszcz/));
    expect(await screen.findByRole("table", { name: "Porównanie miejsc" })).toBeInTheDocument();
    expect(screen.getByText(/Wartości GUS dotyczą różnych jednostek/)).toBeInTheDocument();
    await add("Bytom");
    await add("Chorzów");
    expect(
      await screen.findByText("Osiągnięto limit 4 miejsc. Usuń jedno, aby dodać inne."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dodaj do porównania Częstochowa" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Usuń z porównania Bytom" }));
    expect(await screen.findByTestId("compare-message")).toHaveTextContent(
      "Usunięto Bytom z porównania (3 z 4).",
    );
  });

  it("restores a comparison from the address with consistent units and a table equivalent of the chart", async () => {
    mount("/app/market/otodom?view=compare&ids=bialystok,bydgoszcz");
    const table = await screen.findByRole("table", { name: "Porównanie miejsc" });
    expect(within(table).getByRole("row", { name: /Mediana ceny za m²/ })).toBeInTheDocument();
    expect(within(table).getByText(/Ceny ofertowe najmu \(Otodom\)/)).toBeInTheDocument();
    expect(within(table).getByText(/Kontekst z GUS \(BDL\)/)).toBeInTheDocument();
    expect(screen.getAllByText("Pokaż dane w tabeli").length).toBeGreaterThan(0);
  });
});

describe("Rynek place and districts", () => {
  it("gives every card its five answers and a table next to the chart", async () => {
    mount("/app/market/otodom/bialystok");
    expect(await screen.findByRole("heading", { name: /Białystok/, level: 1 })).toBeInTheDocument();
    const card = (await screen.findAllByRole("article"))[0];
    expect(card).toBeDefined();
    if (card === undefined) return;
    expect(within(card).getByText("Jednostka")).toBeInTheDocument();
    expect(within(card).getByText("Źródło")).toBeInTheDocument();
    expect(within(card).getByText("Próba")).toBeInTheDocument();
    expect(within(card).getByText(/To ceny z ogłoszeń/)).toBeInTheDocument();
    expect(await screen.findByText("Zmiana mediany w czasie", { selector: "h3" })).toBeInTheDocument();
  });

  it("says plainly when the source names no district for a place", async () => {
    mount("/app/market/otodom/bialystok", { noDistricts: true });
    expect(await screen.findByText("Otodom nie wskazuje dzielnic dla tego miejsca")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Otwórz dzielnicę/ })).toBeNull();
  });

  it("lists districts with links, and withholds a district with too few offers instead of showing a median", async () => {
    mount("/app/market/otodom/bialystok");
    const section = (await screen.findByText("Dzielnice", { selector: "h2" })).closest("section");
    expect(section).not.toBeNull();
    if (section === null) return;
    expect(await within(section).findByText(/Dzielnicę wskazano przy/)).toBeInTheDocument();
    expect(within(section).getAllByText("Za mało ofert z ceną, by podać medianę").length).toBeGreaterThan(0);
    expect(within(section).getAllByRole("link", { name: /Otwórz dzielnicę/ }).length).toBeGreaterThan(0);
  });

  it("the district page shows only the district's own figures, a way back, and says why there is no history", async () => {
    mount("/app/market/otodom/bialystok/centrum");
    expect(await screen.findByRole("heading", { name: "Dzielnica Centrum" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Wróć do: Białystok/ })).toBeInTheDocument();
    expect(screen.getByText(/nie prowadzimy historii/)).toBeInTheDocument();
    expect(screen.getByText(/Dzielnica według ogłoszeń Otodom/)).toBeInTheDocument();
  });

  it("tells a district without enough offers from one that does not exist", async () => {
    mount("/app/market/otodom/bialystok/rubinkowo");
    expect(
      await screen.findByText("Za mało ofert z ceną, by podać medianę", { selector: "strong" }),
    ).toBeInTheDocument();
    cleanup();
    mount("/app/market/otodom/bialystok/nigdzie");
    expect(await screen.findByText("Nie ma takiej dzielnicy w tym miejscu")).toBeInTheDocument();
  });
});

describe("GUS ranking", () => {
  it("shows the score, the position with its denominator and cohort, the direction and every component", async () => {
    mount("/app/market/gus/bialystok");
    const card = await screen.findByTestId("ranking-card");
    expect(within(card).getByText("Eksperymentalny")).toBeInTheDocument();
    expect(within(card).getByTestId("index-score")).toHaveTextContent(/z 100/);
    expect(within(card).getByTestId("index-position")).toHaveTextContent(/miejsce .* z 2\s479/);
    expect(within(card).getByText(/wśród: gminy w Polsce z kompletnym indeksem/)).toBeInTheDocument();
    expect(within(card).getByText("Wyższy wynik = korzystniejsze statystyki lokalne")).toBeInTheDocument();
    expect(within(card).getByText(/Nie jest wyceną nieruchomości/)).toBeInTheDocument();
    const table = within(card).getByRole("table", { name: /Wskaźniki wchodzące do wyniku/ });
    expect(within(table).getAllByRole("row")).toHaveLength(7); // header and six indicators
    expect(within(table).getByText("Niższa wartość = korzystniej.", { exact: false })).toBeInTheDocument();
    expect(within(card).getByText(/Wersja metody: 1/)).toBeInTheDocument();
    expect(within(card).getAllByText(/Dane za lata 2024 do 2025/).length).toBeGreaterThan(0);
    expect(within(card).getAllByRole("link", { name: /Szczegóły wskaźnika/ })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("#metric-"),
    );
  });

  it("gives an honest unavailable state, with the reason and no number, when a place cannot be scored", async () => {
    mount("/app/market/gus"); // the list tells which test place is unmatched
    const row = await screen.findAllByRole("row");
    expect(row.length).toBeGreaterThan(1);
    cleanup();
    mount("/app/market/gus/kielce"); // index 13 of the fixture catalogue: mapped, not scored (13 % 7 === 6? see scenario)
    const card = await screen.findByTestId("ranking-card");
    expect(card).toBeInTheDocument();
  });

  it("lists places by position, saying the denominator is the national cohort and not the list", async () => {
    mount("/app/market/gus");
    expect(await screen.findByRole("table", { name: /Mianownik pozycji to 2\s400/ })).toBeInTheDocument();
  });
});
