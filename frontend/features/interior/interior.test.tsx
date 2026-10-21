import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { createQueryClient } from "../../api/query";
import { RequireSession, SessionProvider } from "../../shell/session";
import { useScenario as serveScenario } from "../../test/handlers";
import { createInterior, type InteriorOptions } from "../../test/scenarios";
import { generationPoll } from "./hooks";
import { InteriorPage } from "./InteriorPage";
import { ProjectPage } from "./ProjectPage";

beforeEach(() => {
  generationPoll.ms = 30;
});
afterEach(() => {
  generationPoll.ms = 2_500;
});

function mount(path: string, options: InteriorOptions = {}) {
  const flow = createInterior(options);
  serveScenario(flow);
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          { path: "/app/interior", element: <InteriorPage /> },
          { path: "/app/interior/:projectId", element: <ProjectPage /> },
        ],
      },
      { path: "/login", element: <p>logowanie</p> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={createQueryClient()}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return { flow, router };
}

const seededId = (flow: ReturnType<typeof createInterior>) => [...flow.projects.keys()][0] ?? "";
const image = (text = "FAKEIMG pokoj") => new File([text], "pokoj.jpg", { type: "image/jpeg" });

async function openWorkspace(options: InteriorOptions = {}) {
  const flow = createInterior(options);
  serveScenario(flow);
  const id = seededId(flow);
  // mount() builds its own flow; open the workspace on the flow we hold
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [{ path: "/app/interior/:projectId", element: <ProjectPage /> }],
      },
    ],
    { initialEntries: [`/app/interior/${id}`] },
  );
  render(
    <QueryClientProvider client={createQueryClient()}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Salon", level: 1 });
  return { flow, id };
}

describe("the project list", () => {
  it("shows the person's projects with the photo state and when each expires", async () => {
    mount("/app/interior");
    const card = (await screen.findByRole("heading", { name: "Salon", level: 3 })).closest("li");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText("Ze zdjęciem pokoju")).toBeInTheDocument();
    expect(within(card as HTMLElement).getByText(/^Wygasa /)).toBeInTheDocument();
    expect(screen.getByText(/przechowywany 30 dni od utworzenia/)).toBeInTheDocument();
  });

  it("refuses a blank name before sending anything", async () => {
    const { flow } = mount("/app/interior");
    await screen.findByRole("heading", { name: "Salon", level: 3 });
    await userEvent.click(screen.getByRole("button", { name: "Utwórz projekt" }));
    expect((await screen.findAllByText("Wpisz nazwę projektu."))[0]).toBeInTheDocument();
    expect(flow.calls.filter((c) => c.startsWith("POST"))).toEqual([]);
  });

  it("creates a project and opens it", async () => {
    const { flow, router } = mount("/app/interior", { seeded: false });
    await userEvent.type(await screen.findByRole("textbox", { name: /Nazwa projektu/ }), "Sypialnia");
    await userEvent.click(screen.getByRole("button", { name: "Utwórz projekt" }));
    await waitFor(() => expect(router.state.location.pathname).toMatch(/^\/app\/interior\/[0-9a-f-]{36}$/));
    expect([...flow.projects.values()].map((p) => p.name)).toEqual(["Sypialnia"]);
  });

  it("outside the closed beta it says so and offers no form", async () => {
    mount("/app/interior", { closed: true });
    expect(await screen.findByText("Architekt wnętrz jest w zamkniętej wersji beta")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Utwórz projekt" })).not.toBeInTheDocument();
  });

  it("asks before deleting and deletes only after the confirmation", async () => {
    const { flow } = mount("/app/interior");
    await userEvent.click(await screen.findByRole("button", { name: "Usuń projekt Salon" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Anuluj" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(flow.projects.size).toBe(1);
    await userEvent.click(screen.getByRole("button", { name: "Usuń projekt Salon" }));
    await userEvent.click(
      within(await screen.findByRole("dialog")).getByRole("button", { name: "Usuń projekt" }),
    );
    await waitFor(() => expect(flow.projects.size).toBe(0));
    expect(await screen.findByText("Nie masz jeszcze projektu")).toBeInTheDocument();
  });
});

describe("the room photo", () => {
  it("previews the stored photo through the authenticated route", async () => {
    const { id } = await openWorkspace();
    const img = await screen.findByRole("img", { name: "Zdjęcie pokoju, z którego powstaje wizualizacja" });
    expect(img.getAttribute("src")).toMatch(new RegExp(`^/api/interior/projects/${id}/media/[0-9a-f-]{36}$`));
  });

  it("uploads a new photo and refuses a file that is not an image with the server's reason", async () => {
    const { flow } = await openWorkspace();
    const input = screen.getByTestId("interior-source-input");
    fireEvent.change(input, { target: { files: [image("to nie jest zdjęcie")] } });
    expect(await screen.findByText("Nie udało się odczytać tego pliku jako zdjęcia.")).toBeInTheDocument();
    const before = [...flow.projects.values()][0]?.source?.media_id;
    fireEvent.change(input, { target: { files: [image()] } });
    await waitFor(() => expect([...flow.projects.values()][0]?.source?.media_id).not.toBe(before));
  });

  it("refuses a file over 10 MB without sending it", async () => {
    const { flow } = await openWorkspace();
    const big = new File([new ArrayBuffer(10 * 1024 * 1024 + 1)], "duze.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByTestId("interior-source-input"), { target: { files: [big] } });
    expect(await screen.findByText("Plik jest większy niż 10 MB.")).toBeInTheDocument();
    expect(flow.calls.filter((c) => c.includes("/source"))).toEqual([]);
  });

  it("when storage is down the project is kept and the person is told", async () => {
    await openWorkspace({ storageDown: true });
    fireEvent.change(screen.getByTestId("interior-source-input"), { target: { files: [image()] } });
    expect(await screen.findByText("Zdjęcia są chwilowo niedostępne")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Salon", level: 1 })).toBeInTheDocument();
  });
});

describe("the person's own items", () => {
  it("needs only a name: an item without a price is shown as unknown and stays out of the sum", async () => {
    const { flow } = await openWorkspace();
    await userEvent.type(screen.getByRole("textbox", { name: "Nazwa rzeczy" }), "Stary fotel");
    await userEvent.click(screen.getByRole("button", { name: "Dodaj rzecz" }));
    const card = (await screen.findByRole("heading", { name: "Stary fotel", level: 3 })).closest(
      "li",
    ) as HTMLElement;
    expect(within(card).getByText("Cena nieznana")).toBeInTheDocument();
    expect(within(card).getByText("Dodane przez Ciebie, niezweryfikowane")).toBeInTheDocument();
    expect([...flow.projects.values()][0]?.basket).toMatchObject({
      unpriced_lines: 1,
      known_subtotal_pln: "0.00",
    });
    expect(await screen.findByText(/Pozycje bez ceny \(poza sumą\): 1/)).toBeInTheDocument();
  });

  it("checks the shape of an optional price and link before sending", async () => {
    const { flow } = await openWorkspace();
    await userEvent.type(screen.getByRole("textbox", { name: "Nazwa rzeczy" }), "Lampa");
    await userEvent.type(screen.getByRole("textbox", { name: /Cena za sztukę/ }), "dużo");
    await userEvent.type(screen.getByRole("textbox", { name: /Link/ }), "javascript:alert(1)");
    await userEvent.click(screen.getByRole("button", { name: "Dodaj rzecz" }));
    expect((await screen.findAllByText(/Wpisz kwotę w złotych, na przykład 199/))[0]).toBeInTheDocument();
    expect(screen.getAllByText(/zaczynający się od http/).length).toBeGreaterThan(0);
    expect(flow.calls.filter((c) => c.includes("/items"))).toEqual([]);
  });

  it("keeps a price as the exact text the person typed, comma included", async () => {
    const { flow } = await openWorkspace();
    await userEvent.type(screen.getByRole("textbox", { name: "Nazwa rzeczy" }), "Regał");
    await userEvent.type(screen.getByRole("textbox", { name: /Cena za sztukę/ }), "199,99");
    await userEvent.click(screen.getByRole("button", { name: "Dodaj rzecz" }));
    await screen.findByRole("heading", { name: "Regał", level: 3 });
    expect([...flow.projects.values()][0]?.items[0]?.price_pln).toBe("199.99");
  });
});

describe("the catalogue and the board", () => {
  async function pickSofa() {
    const opened = await openWorkspace();
    await userEvent.type(await screen.findByRole("textbox", { name: /Czego szukasz/ }), "sofa");
    await userEvent.click(screen.getByRole("button", { name: "Szukaj produktów" }));
    await userEvent.click(
      await screen.findByRole("button", { name: /Wybierz: Sofa Nordic 3-osobowa \(szary/ }),
    );
    await screen.findByRole("heading", { name: "Tablica produktów" });
    return opened;
  }

  it("says what it is when no source is connected and never invents products", async () => {
    await openWorkspace({ noCatalogue: true });
    expect(await screen.findByText("Katalog produktów nie jest jeszcze podłączony")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Szukaj produktów" })).not.toBeInTheDocument();
  });

  it("labels the demo source as demo data, not a shop", async () => {
    await openWorkspace();
    expect(await screen.findByText(/dane przykładowe, nie sklep/)).toBeInTheDocument();
    expect(screen.getByText(/To dane przykładowe, a nie oferta sklepu/)).toBeInTheDocument();
  });

  it("picks an exact variant: the board shows the price, the check time and the server's sum", async () => {
    const { flow } = await pickSofa();
    const board = screen.getByRole("region", { name: "Tablica produktów" });
    expect(within(board).getByText("Aktualna oferta")).toBeInTheDocument();
    expect(within(board).getByText(/Sprawdzono:/)).toBeInTheDocument();
    expect(within(board).getByText(/Razem: 2\s?499,00/)).toBeInTheDocument();
    expect(within(board).getByText(/Suma znanych cen: 2\s?499,00/)).toBeInTheDocument();
    expect(flow.calls.some((c) => c.startsWith("POST") && c.endsWith("/selections"))).toBe(true);
  });

  it("an expired offer leaves the sum, is counted, and a re-check brings it back", async () => {
    const { flow } = await pickSofa();
    flow.setOfferState("grey", "expired");
    await userEvent.click(screen.getByRole("button", { name: /Sprawdź ponownie: Sofa Nordic/ }));
    await waitFor(() => expect(screen.getByText("Oferta sprawdzona ponownie.")).toBeInTheDocument());
    flow.setOfferState("grey", "expired");
    await userEvent.click(screen.getByRole("button", { name: "Zapisz wersję" }));
    await screen.findByText("Wersja zapisana.");
    expect(screen.getAllByText("Oferta wygasła").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Oferty wygasłe lub niedostępne \(poza sumą\): 1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Razem: nie obliczamy").length).toBeGreaterThan(0);
  });

  it("unknown price and unknown delivery are said, never shown as 0 zł", async () => {
    await openWorkspace();
    await userEvent.type(await screen.findByRole("textbox", { name: /Czego szukasz/ }), "lampa");
    await userEvent.click(screen.getByRole("button", { name: "Szukaj produktów" }));
    const results = await screen.findByRole("list", { name: "Znalezione produkty" });
    expect(within(results).getAllByText("Cena nieznana").length).toBeGreaterThan(0);
    expect(within(results).queryByText(/^0,00/)).not.toBeInTheDocument();
  });

  it("changes the quantity and removes a line", async () => {
    const { flow } = await pickSofa();
    await userEvent.click(screen.getByRole("button", { name: /Zwiększ liczbę sztuk: Sofa Nordic/ }));
    await waitFor(() => expect([...flow.projects.values()][0]?.selections?.[0]?.quantity).toBe(2));
    await userEvent.click(screen.getByRole("button", { name: /Usuń z tablicy: Sofa Nordic/ }));
    expect(await screen.findByText("Nie wybrano jeszcze produktów.")).toBeInTheDocument();
  });
});

describe("versions and visualisations", () => {
  async function savedVersion(options: InteriorOptions = {}) {
    const opened = await openWorkspace(options);
    await userEvent.click(screen.getByRole("button", { name: "Zapisz wersję" }));
    await screen.findByText("Wersja zapisana.");
    return opened;
  }

  it("saves an immutable version and lists it", async () => {
    const { flow } = await savedVersion();
    expect(await screen.findByRole("heading", { name: "Wersja 1", level: 3 })).toBeInTheDocument();
    expect([...flow.projects.values()][0]?.revisions).toHaveLength(1);
  });

  it("runs a generation to a stored picture, shown beside the original and labelled an illustration", async () => {
    const { flow, id } = await savedVersion();
    await userEvent.click(screen.getByRole("button", { name: "Generuj wizualizację z wersji 1" }));
    expect(await screen.findByText("Gotowa", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Przed: oryginalne zdjęcie")).toBeInTheDocument();
    expect(screen.getByText("Po: ilustracja")).toBeInTheDocument();
    expect(screen.getByText("Ilustracja, nie dokładny wygląd produktów")).toBeInTheDocument();
    expect(screen.getByText(/Koszt: 0,034 USD/)).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Ilustracja pokoju z wybranymi rzeczami" }).getAttribute("src"),
    ).toContain(`/projects/${id}/media/`);
    expect(flow.calls.filter((c) => c.startsWith("POST") && c.endsWith("/generations"))).toHaveLength(1);
  });

  it("a second activation while the request is pending sends no second generation", async () => {
    const { flow } = await savedVersion();
    const button = screen.getByRole("button", { name: "Generuj wizualizację z wersji 1" });
    await userEvent.dblClick(button);
    await screen.findByText("W kolejce", {}, { timeout: 3000 }).catch(() => undefined);
    await waitFor(() => expect(flow.generations.get([...flow.projects.keys()][0] ?? "")?.length).toBe(1));
    expect(flow.calls.filter((c) => c.startsWith("POST") && c.endsWith("/generations"))).toHaveLength(1);
  });

  it("a failed visualisation says why, and a retry is a new operation", async () => {
    const { flow } = await savedVersion({ failWith: "AMBIGUOUS" });
    await userEvent.click(screen.getByRole("button", { name: "Generuj wizualizację z wersji 1" }));
    expect(await screen.findByText(/nie dostaliśmy odpowiedzi/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText(/Koszt szacunkowy: 0,1 USD/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    await waitFor(() =>
      expect(flow.calls.filter((c) => c.startsWith("POST") && c.endsWith("/generations"))).toHaveLength(2),
    );
  });

  it("switched off: says so and the rest keeps working", async () => {
    await savedVersion({ generationOff: true });
    await userEvent.click(screen.getByRole("button", { name: "Generuj wizualizację z wersji 1" }));
    expect(await screen.findByText(/Generowanie obrazów jest wyłączone/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zapisz wersję" })).toBeEnabled();
  });
});
