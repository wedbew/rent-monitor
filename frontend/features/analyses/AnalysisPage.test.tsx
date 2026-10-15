import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../api/query";
import { RequireSession, SessionProvider } from "../../shell/session";
import { useScenario } from "../../test/handlers";
import { SUCCEEDED_AUDITS } from "../../test/scenarios";
import { AnalysisPage } from "./AnalysisPage";

function renderAudit(id: string) {
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [{ path: "/app/analyses/:auditId", element: <AnalysisPage /> }],
      },
    ],
    { initialEntries: [`/app/analyses/${id}`] },
  );
  render(
    <QueryClientProvider client={createQueryClient()}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
}

describe("a completed report", () => {
  it("opens on the listing and the section navigation, with no completion messages or card", async () => {
    useScenario("loaded");
    const audit = SUCCEEDED_AUDITS[0];
    if (audit === undefined) throw new Error("no fixture");
    renderAudit(audit.audit_id);

    const heading = await screen.findByRole("heading", { level: 1, name: `Ogłoszenie ${audit.otodom_id}` });
    expect(heading).toHaveTextContent(`Ogłoszenie ${audit.otodom_id}`);
    expect(screen.queryByRole("heading", { level: 1, name: "Raport" })).toBeNull();

    // The section navigation is the very next thing after the heading.
    const nav = screen.getByRole("navigation", { name: "Sekcje raportu" });
    expect(heading.parentElement?.nextElementSibling).toBe(nav.parentElement);
    expect(within(nav).getAllByRole("link")).toHaveLength(6);

    // No success banner, no "gotowa" message, no result card, no credit sentence.
    expect(screen.queryByRole("region", { name: "Wynik analizy" })).toBeNull();
    expect(screen.queryByText(/Analiza gotowa|Analiza jest gotowa/)).toBeNull();
    expect(screen.queryByText("Raport został pobrany z konta.")).toBeNull();
    expect(screen.queryByText("Raport nie został pobrany z konta.")).toBeNull();
  });

  it("uses the real listing id of each report", async () => {
    useScenario("loaded");
    const audit = SUCCEEDED_AUDITS[3];
    if (audit === undefined) throw new Error("no fixture");
    renderAudit(audit.audit_id);
    expect(
      await screen.findByRole("heading", { level: 1, name: `Ogłoszenie ${audit.otodom_id}` }),
    ).toBeVisible();
  });
});
