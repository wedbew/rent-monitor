import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, describe, expect, it } from "vitest";

import { createQueryClient } from "../api/query";
import { NewAnalysisPage } from "../features/analyses/new/NewAnalysisPage";
import { CreditsPage } from "../features/billing/CreditsPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { useScenario as serveScenario } from "../test/handlers";
import type { ScenarioName } from "../test/scenarios";
import { AccountBlock } from "./AccountBlock";
import { balanceLabel, hasNoLimit } from "./balance";
import { RequireSession, SessionProvider } from "./session";

afterEach(cleanup);

function show(scenario: ScenarioName, path: string) {
  serveScenario(scenario);
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app",
            element: (
              <>
                <AccountBlock />
                <DashboardPage />
              </>
            ),
          },
          { path: "/app/analyses/new", element: <NewAnalysisPage /> },
          { path: "/app/credits", element: <CreditsPage /> },
        ],
      },
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
}

describe("explicit no-limit entitlement (RM-438)", () => {
  it("is decided by the server flag alone, never by the balance", () => {
    const base = { credit_balance: 0, plan: {} };
    expect(hasNoLimit(base)).toBe(false);
    expect(hasNoLimit({ ...base, plan: { unlimited_reports: false } })).toBe(false);
    expect(hasNoLimit({ ...base, plan: { unlimited_reports: true } })).toBe(true);
    expect(balanceLabel({ credit_balance: 0, plan: { unlimited_reports: true } })).toBe("Bez limitu");
    expect(balanceLabel({ credit_balance: 5, plan: {} })).not.toBe("Bez limitu");
  });

  it("shows Bez limitu and no purchase prompt on the dashboard and in the account block", async () => {
    show("unlimited", "/app");
    expect(await screen.findByText("Raporty: bez limitu")).toBeTruthy();
    expect(screen.getAllByText("Bez limitu").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Kup raporty" })).toBeNull();
  });

  it("still offers purchase to an ordinary account with no reports", async () => {
    show("insufficientCredits", "/app");
    expect(await screen.findByRole("link", { name: "Kup raporty" })).toBeTruthy();
    expect(screen.queryByText("Bez limitu")).toBeNull();
  });

  it("says on the new-analysis page that no report is used, and keeps the submit enabled", async () => {
    show("unlimited", "/app/analyses/new");
    expect(await screen.findByText(/nie ma limitu raportów/)).toBeTruthy();
    const submit = screen.getByRole("button", { name: "Rozpocznij analizę" });
    expect((submit as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows Bez limitu as the balance on the credits page", async () => {
    show("unlimited", "/app/credits");
    expect(await screen.findByText("Bez limitu")).toBeTruthy();
  });
});
