import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../api/query";
import { RequireSession, SessionProvider } from "../../shell/session";
import { useScenario } from "../../test/handlers";
import { createMarket } from "../../test/scenarios";
import { LocationPage } from "./LocationPage";
import { MarketExplorer } from "./MarketExplorer";

const RING = [
  [20, 50],
  [21, 50],
  [21, 51],
  [20, 50],
];
const GEOMETRY = {
  bbox: [14, 49, 24, 55],
  gminas: { "0201011": [RING], "0209062": [RING] },
  points: { "0201011": [20.5, 50.4], "0209062": [20.4, 50.3] },
};

function Where() {
  const location = useLocation();
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>;
}

function renderAt(initial: string) {
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/market",
            element: (
              <>
                <MarketExplorer />
                <Where />
              </>
            ),
          },
          { path: "/app/market/:locationId", element: <LocationPage /> },
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
  return router;
}

function geometryServes(body: unknown, ok = true) {
  const real = globalThis.fetch;
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      (typeof input === "string" ? input : input instanceof URL ? input.href : input.url).includes(
        "/geo/gminas.json",
      )
        ? Promise.resolve(new Response(JSON.stringify(body), { status: ok ? 200 : 500 }))
        : real(input, init),
    ),
  );
}

beforeEach(() => geometryServes(GEOMETRY));
afterEach(() => vi.unstubAllGlobals());

describe("Rynek: the explorer", () => {
  it("opens on the map, names the unit a colour stands for and keeps a table as the same data", async () => {
    useScenario(createMarket());
    renderAt("/app/market");
    expect(await screen.findByRole("img", { name: /Mapa miejsc/ })).toBeInTheDocument();
    expect(screen.getByText(/nie położenie ogłoszeń/)).toBeInTheDocument();
    expect(screen.getByText(/Państwowy Rejestr Granic/)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Widok rynku" })).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: /Miejsca widoczne na mapie/ })).toBeInTheDocument();
  });

  it("selecting from the table puts the place in the address and the panel, and a reload keeps it", async () => {
    const user = userEvent.setup();
    const market = createMarket();
    useScenario(market);
    renderAt("/app/market");
    const first = market.places[0];
    await user.click(await screen.findByRole("button", { name: `Wybierz miejsce ${first?.name}` }));
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(`sel=${first?.location_id}`));
    const panel = screen.getByRole("region", { name: "Wybrane miejsce" });
    expect(within(panel).getByText(first?.name ?? "")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: "Otwórz miejsce" })).toBeInTheDocument();
  });

  it("an unreadable boundary file falls back to the table with a plain notice", async () => {
    geometryServes({ broken: true });
    useScenario(createMarket());
    renderAt("/app/market");
    expect(await screen.findByText(/Nie udało się wczytać granic gmin/)).toBeInTheDocument();
    expect(await screen.findByRole("table", { name: /Miejsca widoczne na mapie/ })).toBeInTheDocument();
  });

  it("a free account sees the cap, its reason and the way to full access", async () => {
    useScenario(createMarket({ free: true }));
    renderAt("/app/market");
    expect(await screen.findByText("Konto darmowe: widzisz 20 z 38 miejsc")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kup pakiet raportów" })).toHaveAttribute("href", "/app/credits");
    const rows = within(await screen.findByRole("table", { name: /Miejsca widoczne/ })).getAllByRole(
      "rowheader",
    );
    expect(rows).toHaveLength(20);
  });

  it("the comparison holds at most four places and says what cannot be compared", async () => {
    const user = userEvent.setup();
    const market = createMarket();
    useScenario(market);
    renderAt("/app/market?view=compare");
    await screen.findByRole("table", { name: /Miejsca widoczne/ });
    expect(screen.getByText(/Wybierz od 2 do 4 miejsc/)).toBeInTheDocument();
    for (const place of market.places.slice(0, 4))
      await user.click(screen.getByRole("button", { name: `Dodaj do porównania ${place.name}` }));
    const fifth = market.places[4];
    expect(screen.getByRole("button", { name: `Dodaj do porównania ${fifth?.name}` })).toBeDisabled();
    expect(await screen.findByText(/nie są porównywalne wprost/)).toBeInTheDocument();
    const compare = await screen.findByRole("table", { name: "Porównanie miejsc" });
    expect(within(compare).getAllByRole("columnheader")).toHaveLength(5);
    expect(await within(compare).findAllByText(/Powiat testowy, 2025/)).not.toHaveLength(0);
  });

  it("a failing overview offers a retry and shows no numbers", async () => {
    useScenario(createMarket({ overviewFails: true }));
    renderAt("/app/market");
    expect(await screen.findByText("Nie udało się wczytać rynku")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("Rynek: the place context", () => {
  it("shows value, unit, year, proxy label, trend, parents and a table of the series", async () => {
    const market = createMarket();
    useScenario(market);
    renderAt(`/app/market/${market.places[0]?.location_id}`);
    const heading = await screen.findByRole("heading", { name: "Kontekst lokalizacji (GUS)" });
    const section = heading.closest("section") as HTMLElement;
    const population = await within(section).findByRole("article", { name: "Ludność ogółem" });
    expect(population).toHaveTextContent("Dane tej jednostki");
    expect(population).toHaveTextContent("rok 2025");
    expect(population).toHaveTextContent("Od 2016 do 2025: rośnie");
    expect(population.textContent).toMatch(/miejsce 120 z 2\s479/u);
    expect(population).toHaveTextContent("Za mało danych, by podać pozycję"); // the peer group is thin
    const price = within(section).getByRole("article", { name: /Mediana cen za 1 m²/ });
    expect(price).toHaveTextContent("Dane szerszej jednostki");
    expect(within(population).getByRole("table", { name: "" })).toBeInTheDocument();
  });

  it("an unmatched place says it has no gmina and shows no figure", async () => {
    const market = createMarket();
    useScenario(market);
    renderAt(`/app/market/${market.places[10]?.location_id}`);
    expect(await screen.findByText("Miejsce nie ma przypisanej gminy")).toBeInTheDocument();
    expect(screen.queryByRole("article")).toBeNull();
  });

  it("an ambiguous place names its candidates and does not pick one", async () => {
    const market = createMarket();
    useScenario(market);
    renderAt(`/app/market/${market.places[6]?.location_id}`);
    expect(await screen.findByText("Kilka gmin pasuje do nazwy")).toBeInTheDocument();
    expect(screen.getByText(/Gmina A, Gmina B/)).toBeInTheDocument();
  });

  it("a closed place for a free account explains the cap", async () => {
    useScenario(createMarket({ free: true }));
    renderAt(`/app/market/${createMarket().places[30]?.location_id}`);
    expect(await screen.findByText("To miejsce nie należy do darmowej listy")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kup pakiet raportów" })).toHaveAttribute("href", "/app/credits");
    expect(screen.queryByRole("heading", { name: "Kontekst lokalizacji (GUS)" })).toBeNull();
  });

  it("a failing context keeps the rent figures and offers a retry", async () => {
    const market = createMarket({ contextFails: true });
    useScenario(market);
    renderAt(`/app/market/${market.places[0]?.location_id}`);
    expect(await screen.findByText("Nie udało się wczytać kontekstu")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Spróbuj ponownie" }).length).toBeGreaterThan(0);
    expect(await screen.findByRole("heading", { name: "Ostatni odczyt" })).toBeInTheDocument();
  });
});
