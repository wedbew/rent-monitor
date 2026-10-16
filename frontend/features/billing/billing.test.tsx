import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../config", () => ({
  config: { paddleClientToken: "test_fixture_token", paddleEnvironment: "sandbox" },
}));

import { createQueryClient } from "../../api/query";
import { fx } from "../../test/fixtures";
import { useScenario as serveScenario } from "../../test/handlers";
import { createBilling, replyFrom, SHOP_HISTORY, type BillingFlow, type Reply } from "../../test/scenarios";
import { RequireSession, SessionProvider } from "../../shell/session";
import { CreditsPage } from "./CreditsPage";
import { resetPaddleForTests } from "./paddle";
import { pollSchedule } from "./queries";
import { SuccessPage } from "./SuccessPage";

const reply = (operation: string, name: string): Reply => replyFrom(fx(operation, name));

function mount(flow: BillingFlow, path = "/app/credits") {
  serveScenario(flow);
  const client = createQueryClient();
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          { path: "/app/credits", element: <CreditsPage /> },
          { path: "/app/credits/success", element: <SuccessPage /> },
        ],
      },
      { path: "/login", element: <p>logowanie</p> },
    ],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return { client, router };
}

const paddle = {
  Environment: { set: vi.fn() },
  Initialize: vi.fn(),
  Checkout: { open: vi.fn() },
};

const buy = (count: string) => screen.findByRole("button", { name: new RegExp(`^Kup pakiet ${count}\\s`) });
const keysOf = (flow: BillingFlow) =>
  flow.calls.filter((c) => c.startsWith("checkout:")).map((c) => c.split(":")[1]);

beforeEach(() => {
  resetPaddleForTests();
  paddle.Checkout.open.mockReset();
  paddle.Initialize.mockReset();
  window.Paddle = paddle;
  pollSchedule.stepsMs = [10, 10, 10];
  pollSchedule.steadyMs = 10;
});
afterEach(() => {
  delete window.Paddle;
  vi.restoreAllMocks();
});

describe("packs", () => {
  it("shows the server's packs with gross prices, never computed here", async () => {
    mount(createBilling());
    const list = await screen.findByRole("list", { name: "Dostępne pakiety" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Pakiet: 1 raport");
    expect(items[0]).toHaveTextContent("10 zł brutto");
    expect(items[1]).toHaveTextContent("40 zł brutto");
    expect(items[2]).toHaveTextContent("70 zł brutto");
  });

  it("when billing is disabled the shop says so and offers nothing", async () => {
    mount(createBilling({ enabled: false }));
    expect(await screen.findByText("Zakupy nie są jeszcze dostępne")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Kup pakiet/ })).toBeNull();
  });

  it("an unverified address blocks buying and says how to fix it", async () => {
    mount(createBilling({ verified: false }));
    expect(await screen.findByText("Potwierdź adres e-mail, aby kupować")).toBeInTheDocument();
    expect(await buy("5")).toBeDisabled();
  });

  it("an unreadable catalog is a failure with a retry, not an empty shop", async () => {
    mount(
      createBilling({
        overrides: { "GET /api/billing/packs": { status: 200, body: { enabled: true, packs: [{ x: 1 }] } } },
      }),
    );
    expect(await screen.findByText("Nie udało się wczytać pakietów")).toBeInTheDocument();
  });
});

describe("checkout", () => {
  it("sends one request with a fresh idempotency key and opens Paddle with the returned transaction", async () => {
    const flow = createBilling();
    mount(flow);
    await userEvent.click(await buy("5"));
    await waitFor(() => expect(paddle.Checkout.open).toHaveBeenCalledOnce());
    const [call] = flow.calls.filter((c) => c.startsWith("checkout:"));
    expect(call).toMatch(/^checkout:[0-9a-f-]{36}:reports_5$/);
    const options = paddle.Checkout.open.mock.calls[0]?.[0] as {
      transactionId: string;
      settings: { successUrl: string };
    };
    expect(options.transactionId).toBe("txn_fixture0001");
    expect(options.settings.successUrl).toContain("/app/credits/success?purchase=00000000-0000-4000-8000-");
  });

  it("a second activation while the request is pending sends nothing more", async () => {
    const flow = createBilling();
    const slow = flow.routes.find((r) => r.operation === "POST /api/billing/checkout");
    let posts = 0;
    const counted: BillingFlow = {
      ...flow,
      routes: [
        {
          operation: "POST /api/billing/checkout",
          reply: (request) => {
            posts += 1;
            const answer = typeof slow?.reply === "function" ? slow.reply(request) : slow?.reply;
            return { ...(answer as Reply), delayMs: 200 };
          },
        },
        ...flow.routes.filter((r) => r.operation !== "POST /api/billing/checkout"),
      ],
    };
    mount(counted);
    const button = await buy("1");
    await userEvent.click(button);
    await userEvent.click(button);
    await waitFor(() => expect(paddle.Checkout.open).toHaveBeenCalled());
    expect(posts).toBe(1);
  });

  it("after a lost answer the retry reuses the same key (so it cannot create a second order); a new intent gets a new key", async () => {
    let drop = true;
    const flow = createBilling();
    const real = flow.routes.find((r) => r.operation === "POST /api/billing/checkout");
    const lossy: BillingFlow = {
      ...flow,
      routes: [
        {
          operation: "POST /api/billing/checkout",
          reply: (request) => {
            const answer = typeof real?.reply === "function" ? real.reply(request) : (real?.reply as Reply);
            if (drop) {
              drop = false;
              return { status: 0, networkError: true };
            }
            return answer;
          },
        },
        ...flow.routes.filter((r) => r.operation !== "POST /api/billing/checkout"),
      ],
    };
    mount(lossy);
    await userEvent.click(await buy("5"));
    expect(await screen.findByText("Nie wiemy, czy zamówienie zostało utworzone")).toBeInTheDocument();
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    await waitFor(() => expect(paddle.Checkout.open).toHaveBeenCalledOnce());
    const keys = keysOf(flow);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);

    await userEvent.click(await buy("5"));
    await waitFor(() => expect(keysOf(flow)).toHaveLength(3));
    expect(keysOf(flow)[2]).not.toBe(keys[0]);
  });

  it("a refusal (billing hold) is said in Polish and the next try is a new intent", async () => {
    const flow = createBilling({
      overrides: { "POST /api/billing/checkout": reply("POST /api/billing/checkout", "billing_hold") },
    });
    mount(flow);
    await userEvent.click(await buy("1"));
    expect(await screen.findByText(/kontrol|weryfik|zawiesz|blokad/i)).toBeInTheDocument();
    await userEvent.click(await buy("1"));
    await waitFor(() => expect(keysOf(flow)).toHaveLength(2));
    expect(keysOf(flow)[0]).not.toBe(keysOf(flow)[1]);
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
  });

  it("an order the provider may or may not have created (202) is shown as being checked: no payment window, no second order", async () => {
    mount(
      createBilling({
        overrides: {
          "POST /api/billing/checkout": reply("POST /api/billing/checkout", "provider_outcome_unknown"),
        },
      }),
    );
    await userEvent.click(await buy("10"));
    expect(await screen.findByText("Zamówienie jest sprawdzane")).toBeInTheDocument();
    expect(screen.getByText(/Nie płać ponownie/)).toBeInTheDocument();
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
  });

  it("when the payment window cannot open the order still exists and can be finished from the list", async () => {
    paddle.Checkout.open.mockImplementation(() => {
      throw new Error("blocked");
    });
    mount(createBilling());
    await userEvent.click(await buy("5"));
    expect(await screen.findByText("Nie udało się otworzyć płatności")).toBeInTheDocument();
    const list = await screen.findByRole("list", { name: "Zakupy" });
    expect(
      await within(list).findByRole("button", { name: /^Dokończ płatność, zamówienie/ }),
    ).toBeInTheDocument();
  });
});

describe("purchases", () => {
  const flow = () => createBilling({ existing: SHOP_HISTORY });

  it("shows every state in words with the order number", async () => {
    mount(flow());
    const list = await screen.findByRole("list", { name: "Zakupy" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    const expected = [
      "Raporty dodane do konta",
      "Czeka na płatność",
      "Zwrócone",
      "Wymaga sprawdzenia",
      "Sprawdzamy zamówienie",
      "Płatność nie powiodła się",
    ];
    for (const [i, label] of expected.entries()) expect(items[i]).toHaveTextContent(label);
    expect(items[0]).toHaveTextContent("00000000");
  });

  it("offers an invoice only once there is something paid, and a payment only where one can be finished", async () => {
    mount(flow());
    const list = await screen.findByRole("list", { name: "Zakupy" });
    const items = within(list).getAllByRole("listitem");
    const has = (i: number, name: RegExp) =>
      within(items[i] as HTMLElement).queryByRole("button", { name }) !== null;
    expect(has(0, /faktur/i)).toBe(true); // granted
    expect(has(1, /Dokończ płatność/)).toBe(true); // created
    expect(has(1, /faktur/i)).toBe(false);
    expect(has(2, /faktur/i)).toBe(true); // refunded
    for (const i of [3, 4, 5]) {
      expect(has(i, /faktur/i)).toBe(false);
      expect(has(i, /Dokończ płatność/)).toBe(false);
    }
  });

  it("opens the invoice link in a new tab without an opener", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    mount(flow());
    const list = await screen.findByRole("list", { name: "Zakupy" });
    await userEvent.click(within(list).getAllByRole("button", { name: /faktur/i })[0] as HTMLElement);
    await waitFor(() =>
      expect(open).toHaveBeenCalledWith(
        "https://invoice.example.test/document.pdf",
        "_blank",
        "noopener,noreferrer",
      ),
    );
  });

  it("an invoice that is not ready, or a provider outage, is said without losing the page", async () => {
    mount(
      createBilling({
        existing: SHOP_HISTORY,
        overrides: {
          "GET /api/billing/purchases/{purchase_id}/invoice": reply(
            "GET /api/billing/purchases/{purchase_id}/invoice",
            "provider_outage",
          ),
        },
      }),
    );
    const list = await screen.findByRole("list", { name: "Zakupy" });
    await userEvent.click(within(list).getAllByRole("button", { name: /faktur/i })[0] as HTMLElement);
    expect(await within(list).findByRole("alert")).toBeInTheDocument();
  });

  it("an invoice link that is not https is never opened", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    mount(
      createBilling({
        existing: SHOP_HISTORY,
        overrides: {
          "GET /api/billing/purchases/{purchase_id}/invoice": {
            status: 200,
            body: { url: "javascript:alert(1)" },
          },
        },
      }),
    );
    const list = await screen.findByRole("list", { name: "Zakupy" });
    await userEvent.click(within(list).getAllByRole("button", { name: /faktur/i })[0] as HTMLElement);
    expect(await within(list).findByRole("alert")).toBeInTheDocument();
    expect(open).not.toHaveBeenCalled();
  });

  it("an empty history says so", async () => {
    mount(createBilling());
    expect(await screen.findByText("Nie kupiono jeszcze żadnego pakietu.")).toBeInTheDocument();
  });
});

describe("success page", () => {
  const id = "00000000-0000-4000-8000-000000000901";
  const seeded = (options: Parameters<typeof createBilling>[0] = {}) => {
    const flow = createBilling(options);
    flow.purchases.set(id, {
      purchase_id: id,
      pack_code: "reports_5",
      reports: 5,
      gross_pln: "40",
      currency: "PLN",
      state: "created",
      transaction_id: "txn_fixture0001",
      checkout_url: null,
      created_at: "2026-10-02T10:00:00Z",
      granted_at: null,
      refunded_at: null,
    });
    return flow;
  };

  it("never says credit arrived on the browser's word: it waits, asks again, and shows granted only when the server says so", async () => {
    const flow = seeded();
    mount(flow, `/app/credits/success?purchase=${id}`);
    expect(await screen.findByText(/Nie płać ponownie/)).toBeInTheDocument();
    expect(screen.queryByText("Raporty są na koncie")).toBeNull();
    expect(await screen.findByText("Raporty są na koncie", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText(/Dodaliśmy 5 raportów/)).toBeInTheDocument();
    const polls = flow.calls.filter((c) => c.startsWith("poll:")).length;
    expect(polls).toBeGreaterThanOrEqual(3);
    await new Promise((r) => setTimeout(r, 100));
    expect(flow.calls.filter((c) => c.startsWith("poll:")).length).toBe(polls); // settled: polling stopped
    expect(screen.getByRole("link", { name: "Sprawdź mieszkanie" })).toBeInTheDocument();
  });

  it("finds the purchase by Paddle's transaction when it comes back from the payment-link page", async () => {
    const flow = seeded();
    mount(flow, "/app/credits/success?txn=txn_fixture0001");
    expect(await screen.findByText("Raporty są na koncie", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("a failed or reviewed purchase is said as it is, with the order number", async () => {
    const flow = seeded({ finalState: "review", settleAfter: 1 });
    mount(flow, `/app/credits/success?purchase=${id}`);
    expect(await screen.findByText("Wymaga sprawdzenia")).toBeInTheDocument();
    expect(screen.getByText(/Numer zamówienia: 00000000/)).toBeInTheDocument();
  });

  it("an address that names no purchase is said, not guessed", async () => {
    mount(createBilling(), "/app/credits/success?purchase=not-an-id");
    expect(await screen.findByText("Nie znaleziono zamówienia")).toBeInTheDocument();
  });

  it("someone else's purchase is a 404 and is said as such", async () => {
    mount(createBilling(), "/app/credits/success?purchase=00000000-0000-4000-8000-0000000009ff");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /Nie znaleziono|nie istnieje|Nie udało się sprawdzić/i,
    );
  });
});
