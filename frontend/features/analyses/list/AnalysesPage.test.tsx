import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../../api/query";
import { RequireSession, SessionProvider } from "../../../shell/session";
import { useScenario } from "../../../test/handlers";
import { AnalysesPage } from "./AnalysesPage";

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.search}</p>;
}

function renderList(initial = "/app/analyses") {
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/analyses",
            element: (
              <>
                <AnalysesPage />
                <Where />
              </>
            ),
          },
        ],
      },
    ],
    { initialEntries: [initial] },
  );
  render(
    <QueryClientProvider client={createQueryClient()}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
}

describe("Moje analizy controls", () => {
  it("groups search and filters apart from the results toolbar that holds the count and the view switch", async () => {
    useScenario("collection");
    renderList();
    const filters = await screen.findByRole("region", { name: "Wyszukiwanie i filtry" });
    expect(within(filters).getByRole("search")).toBeInTheDocument();
    expect(within(filters).getByRole("combobox", { name: "Status" })).toBeInTheDocument();
    expect(within(filters).getByRole("combobox", { name: "Ocena" })).toBeInTheDocument();
    expect(within(filters).queryByRole("group", { name: "Widok" })).toBeNull();

    const view = screen.getByRole("group", { name: "Widok" });
    const count = await screen.findByText(/Wyświetlono/);
    expect(view.parentElement).toBe(count.parentElement?.parentElement);
    expect(within(view).getByRole("button", { name: "Karty" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switching to the table keeps the search and filters, in the address and on screen", async () => {
    useScenario("collection");
    renderList("/app/analyses?status=ready&q=IDLST");
    await screen.findByRole("list", { name: "Analizy" });
    expect(screen.getByRole("combobox", { name: "Status" })).toHaveTextContent("Gotowe");
    expect(screen.getByRole("textbox", { name: "Numer ogłoszenia (początek)" })).toHaveValue("IDLST");

    await userEvent.click(screen.getByRole("button", { name: "Tabela" }));
    const table = await screen.findByRole("table");
    expect(table).toBeInTheDocument();
    const where = screen.getByTestId("where").textContent ?? "";
    expect(where).toContain("view=table");
    expect(where).toContain("status=ready");
    expect(where).toContain("q=IDLST");
    expect(screen.getByRole("combobox", { name: "Status" })).toHaveTextContent("Gotowe");
    expect(screen.getByRole("textbox", { name: "Numer ogłoszenia (początek)" })).toHaveValue("IDLST");
    expect(screen.getByRole("button", { name: "Tabela" })).toHaveAttribute("aria-pressed", "true");

    await userEvent.click(screen.getByRole("button", { name: "Karty" }));
    expect(await screen.findByRole("list", { name: "Analizy" })).toBeInTheDocument();
    expect(screen.getByTestId("where").textContent).toContain("status=ready");
  });

  it("an unsubmitted search stays in the field when the view changes", async () => {
    useScenario("collection");
    renderList();
    await screen.findByRole("list", { name: "Analizy" });
    await userEvent.type(screen.getByRole("textbox", { name: "Numer ogłoszenia (początek)" }), "ABC");
    await userEvent.click(screen.getByRole("button", { name: "Tabela" }));
    await screen.findByRole("table");
    expect(screen.getByRole("textbox", { name: "Numer ogłoszenia (początek)" })).toHaveValue("ABC");
  });

  it("the table is semantic, says the order the server uses, and offers no sort the API cannot do", async () => {
    useScenario("collection");
    renderList("/app/analyses?view=table");
    const table = await screen.findByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Ogłoszenie",
      "Data",
      "Status",
      "Ocena",
      "Cena ofertowa",
      "Cena progowa",
      "Zapisane",
    ]);
    expect(within(table).getByRole("columnheader", { name: "Data" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    // No header is a button: sorting the loaded rows would pretend to order every analysis.
    const head = table.querySelector("thead");
    expect(head && within(head as HTMLElement).queryAllByRole("button")).toEqual([]);
    const first = within(table).getAllByRole("rowheader")[0];
    expect(within(first as HTMLElement).getByRole("link", { name: /^Ogłoszenie IDLST/ })).toHaveAttribute(
      "href",
      expect.stringMatching(/^\/app\/analyses\//),
    );
  });

  it("filters are requests to the API: a table row count is the server's page, not a local slice", async () => {
    useScenario("collection");
    renderList("/app/analyses?view=table");
    await screen.findByRole("table");
    expect(screen.getByRole("button", { name: "Załaduj więcej" })).toBeInTheDocument();
  });

  it("no matching results and an empty account are different messages", async () => {
    useScenario("empty");
    renderList("/app/analyses?view=table");
    expect(await screen.findByText(/Nie masz jeszcze/i)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
