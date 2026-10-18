/**
 * The shop against the real API (RM-277). Billing is not enabled on the journey stack and the SPA is built without a
 * Paddle client token, so this proves the honest unavailable state end to end: real packs answer, real purchases
 * list (empty), nothing to buy, nothing sent to Paddle. It is NOT provider evidence and says nothing about checkout.
 */
import { execFileSync } from "node:child_process";

import { expect, test } from "@playwright/test";

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function script(...args: string[]): Record<string, unknown> {
  const [command = "docker", ...rest] = COMPOSE;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    { encoding: "utf8" },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, unknown>;
}

interface Seeded {
  user_id: string;
  cookie_name: string;
  cookie_value: string;
}
let seeded: Seeded;

test.beforeAll(() => {
  seeded = script("create", "--credits", "3") as unknown as Seeded;
});
test.afterAll(() => {
  script("delete", seeded.user_id);
});

test("credits page against the real API: no shop is offered, the history is empty, and Paddle is never contacted", async ({
  page,
  baseURL,
}) => {
  const paddleRequests: string[] = [];
  page.on("request", (request) => {
    if (/paddle\.com/.test(request.url())) paddleRequests.push(request.url());
  });
  await page.context().addCookies([
    {
      name: seeded.cookie_name,
      value: seeded.cookie_value,
      url: baseURL ?? "http://localhost:4173",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
  await page.goto("/app/credits");
  await expect(page.getByRole("heading", { level: 1, name: "Raporty i zakupy" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Raporty na koncie" })).toContainText(/3\s+raporty/);
  await expect(page.getByText("Nie kupiono jeszcze żadnego pakietu.")).toBeVisible();
  await expect(page.getByRole("button", { name: /^Kup pakiet/ })).toHaveCount(0);
  await expect(
    page
      .getByRole("alert")
      .or(page.getByText(/nie są jeszcze dostępne|nie jest tu jeszcze skonfigurowana|Nie ma teraz/)),
  ).toBeVisible();

  await page.goto("/pay?_ptxn=txn_realstack0001");
  await expect(page.getByText("Płatność nie jest tu skonfigurowana")).toBeVisible();
  expect(paddleRequests).toEqual([]);
});
