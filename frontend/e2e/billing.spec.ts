import type { Page } from "@playwright/test";

import { fx } from "../test/fixtures";
import { createBilling, replyFrom, SHOP_HISTORY } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";

const buy = (page: Page, count: string) =>
  page.getByRole("button", { name: new RegExp(`^Kup pakiet ${count}\\s`) });
const keys = (calls: readonly string[]) =>
  calls.filter((c) => c.startsWith("checkout:")).map((c) => c.split(":")[1]);

test.describe("credits and purchases", () => {
  test("the shop lists the server's packs and a purchase opens Paddle with the server's transaction, one key per intent", async ({
    paddle,
    page,
    serve,
  }) => {
    const flow = createBilling();
    const api = await serve(flow);
    await page.goto("/app/credits");
    await expect(page.getByRole("heading", { level: 1, name: "Raporty i zakupy" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Dostępne pakiety" }).getByRole("listitem")).toHaveCount(3);
    await expect(page.getByText("40 zł brutto")).toBeVisible();
    await exercise("credits.buy", async () => {
      await buy(page, "5").click();
      await expect.poll(async () => (await paddle.opened()).length).toBe(1);
      return [
        await outcome.request(api, {
          method: "POST",
          path: "/api/billing/checkout",
          body: { pack_code: "reports_5" },
        }),
      ];
    });
    const [opened] = await paddle.opened();
    expect(opened?.transactionId).toBe("txn_fixture0001");
    expect(opened?.settings?.successUrl).toMatch(
      /\/app\/credits\/success\?purchase=00000000-0000-4000-8000-/,
    );
    expect(keys(flow.calls)).toHaveLength(1);
    expect(paddle.hostRequests, "Paddle.js is never fetched in the mocked lane").toEqual([]);
  });

  test("billing disabled: an honest unavailable state and no buttons", async ({ page, serve }) => {
    await serve("billingDisabled");
    await page.goto("/app/credits");
    await expect(page.getByText("Zakupy nie są jeszcze dostępne")).toBeVisible();
    await expect(page.getByRole("button", { name: /^Kup pakiet/ })).toHaveCount(0);
  });

  test("a lost answer is said as unknown; the retry is the same order (same key), never a second one", async ({
    page,
    serve,
  }) => {
    let drop = true;
    const flow = createBilling();
    const real = flow.routes.find((r) => r.operation === "POST /api/billing/checkout");
    await serve({
      ...flow,
      routes: [
        {
          operation: "POST /api/billing/checkout",
          reply: (request) => {
            const answer =
              typeof real?.reply === "function" ? real.reply(request) : (real?.reply ?? { status: 500 });
            if (drop) {
              drop = false;
              return { status: 0, networkError: true };
            }
            return answer;
          },
        },
        ...flow.routes.filter((r) => r.operation !== "POST /api/billing/checkout"),
      ],
    });
    await page.goto("/app/credits");
    await buy(page, "1").click();
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie wiemy, czy zamówienie zostało utworzone" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Spróbuj ponownie" }).click();
    await expect.poll(() => keys(flow.calls).length).toBe(2);
    expect(keys(flow.calls)[0]).toBe(keys(flow.calls)[1]);
  });

  test("the history shows every state in words; a payment can be finished and an invoice opened where it makes sense", async ({
    paddle,
    page,
    serve,
  }) => {
    const flow = createBilling({ existing: SHOP_HISTORY });
    const api = await serve(flow);
    await page.goto("/app/credits");
    const items = page.getByRole("list", { name: "Zakupy" }).getByRole("listitem");
    await expect(items).toHaveCount(6);
    for (const [i, label] of [
      "Raporty dodane do konta",
      "Czeka na płatność",
      "Zwrócone",
      "Wymaga sprawdzenia",
      "Sprawdzamy zamówienie",
      "Płatność nie powiodła się",
    ].entries())
      await expect(items.nth(i)).toContainText(label);

    await exercise("credits.resume", async () => {
      await items
        .nth(1)
        .getByRole("button", { name: /^Dokończ płatność/ })
        .click();
      await expect.poll(async () => (await paddle.opened()).length).toBe(1);
      return [await outcome.request(api, { method: "GET", path: "/api/billing/purchases" })];
    });
    await exercise("credits.invoice", async () => {
      const popup = page.waitForEvent("popup");
      await items
        .nth(0)
        .getByRole("button", { name: /^Pokaż fakturę/ })
        .click();
      await popup.then((p) => p.close()).catch(() => undefined);
      return [
        await outcome.request(api, {
          method: "GET",
          path: new RegExp(`/api/billing/purchases/${SHOP_HISTORY[0]?.purchase_id ?? ""}/invoice$`),
        }),
      ];
    });
  });

  test("an invoice that is not ready is said, in the list, without losing the page", async ({
    page,
    serve,
  }) => {
    await serve(
      createBilling({
        existing: SHOP_HISTORY,
        overrides: {
          "GET /api/billing/purchases/{purchase_id}/invoice": replyFrom(
            fx("GET /api/billing/purchases/{purchase_id}/invoice", "not_paid_yet"),
          ),
        },
      }),
    );
    await page.goto("/app/credits");
    await page
      .getByRole("button", { name: /^Pokaż fakturę/ })
      .first()
      .click();
    await expect(page.getByRole("list", { name: "Zakupy" }).getByRole("alert")).toBeVisible();
  });
});

test.describe("after payment", () => {
  test("the success page waits, never claims credit on the browser's word, then shows what the server granted and the new balance", async ({
    isMobile,
    page,
    serve,
  }) => {
    const flow = createBilling();
    await serve(flow);
    await page.goto("/app/credits");
    await buy(page, "5").click();
    await expect.poll(() => flow.purchases.size).toBe(1);
    const purchaseId = [...flow.purchases.keys()][0] ?? "";
    await page.goto(`/app/credits/success?purchase=${purchaseId}`);
    await expect(page.getByText("Raporty są na koncie")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Dodaliśmy 5\s+raportów/)).toBeVisible();
    // The balance is the server's, read again after the grant: 7 before, 5 more now.
    if (!isMobile) await expect(page.getByText(/12\s+raportów na koncie/)).toBeVisible(); // the rail is a sheet on a phone
    await exercise("success.analysis", async () => {
      await page.getByRole("link", { name: "Sprawdź mieszkanie" }).click();
      return [await outcome.url(page, /\/app\/analyses\/new$/)];
    });
  });

  test("a purchase still waiting says so and offers the way back", async ({ page, serve }) => {
    await serve("shopHistory");
    await page.goto(`/app/credits/success?purchase=${SHOP_HISTORY[1]?.purchase_id ?? ""}`);
    await expect(page.getByText(/Nie płać ponownie/)).toBeVisible();
    await expect(page.getByText("Raporty są na koncie")).toHaveCount(0);
    await exercise("success.purchases", async () => {
      await page.getByRole("link", { name: "Wróć do zakupów" }).click();
      return [await outcome.url(page, /\/app\/credits$/)];
    });
  });
});

test.describe("/pay (the default payment link)", () => {
  test("opens the transaction Paddle names, with a return address that leads to the polling page", async ({
    paddle,
    page,
    serve,
  }) => {
    await serve("firstVisit");
    await page.goto("/pay?_ptxn=txn_fixture0001");
    await expect.poll(async () => (await paddle.opened()).length).toBe(1);
    const [opened] = await paddle.opened();
    expect(opened?.transactionId).toBe("txn_fixture0001");
    expect(opened?.settings?.successUrl).toMatch(/\/app\/credits\/success\?txn=txn_fixture0001$/);
    await exercise("pay.credits", async () => {
      await page.getByRole("link", { name: "Wróć do zakupów" }).click();
      return [await outcome.url(page, /\/app\/credits$|\/login/)];
    });
  });

  test("a value that is not a Paddle transaction is never handed to Paddle.js", async ({
    paddle,
    page,
    serve,
  }) => {
    await serve("firstVisit");
    await page.goto("/pay?_ptxn=%3Cscript%3E");
    await expect(page.getByText("Nieprawidłowy adres płatności")).toBeVisible();
    expect(await paddle.opened()).toEqual([]);
  });

  test("when Paddle.js cannot open the checkout it says so and can try again", async ({
    paddle,
    page,
    serve,
  }) => {
    await paddle.failOpen(true);
    await serve("firstVisit");
    await page.goto("/pay?_ptxn=txn_fixture0001");
    await expect(
      page.getByRole("alert").filter({ hasText: "Nie udało się otworzyć płatności" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Spróbuj ponownie" })).toBeVisible();
  });
});
