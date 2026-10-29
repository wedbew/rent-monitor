/**
 * Journey lane smoke: a session seeded inside the api container (scripts/e2e_session.py, no HTTP bypass) is accepted by
 * the real, unmodified API through the SPA's own origin. Slices add their journeys next to this file.
 * Needs the stack up: see frontend/README.md (Journey lane).
 */
import { execFileSync } from "node:child_process";

import { expect, test } from "./fixtures";

interface Seeded {
  user_id: string;
  email: string;
  cookie_name: string;
  cookie_value: string;
}

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function session(...args: string[]): unknown {
  const [command = "docker", ...rest] = COMPOSE;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    {
      encoding: "utf8",
    },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}");
}

let seeded: Seeded;

test.beforeAll(() => {
  seeded = session("create", "--credits", "3") as Seeded;
});

test.afterAll(() => {
  session("delete", seeded.user_id);
});

test("a seeded session is accepted by the real API through the SPA origin", async ({
  context,
  page,
  baseURL,
}) => {
  await context.addCookies([
    {
      name: seeded.cookie_name,
      value: seeded.cookie_value,
      url: baseURL ?? "http://localhost:4173",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
  const reply = await page.request.get("/api/me");
  expect(reply.status()).toBe(200);
  expect(await reply.json()).toMatchObject({ email: seeded.email, credit_balance: 3 });

  await page.goto("/");
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { level: 1, name: "Pulpit" })).toBeVisible();
  await expect(page.getByText("3 raporty na koncie")).toBeVisible();
});

test("without the cookie the same API call is refused", async ({ page }) => {
  const reply = await page.request.get("/api/me");
  expect(reply.status()).toBe(401);
  expect(reply.headers()["content-type"]).toContain("application/problem+json");
});
