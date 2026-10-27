/** Real upload and responsive wizard checks. Optional INTERIOR_ROOM_PHOTO supplies a local, owner-selected image.
 * Without it the browser creates a valid portrait PNG, so CI never downloads third-party photographs.
 * LEGAL[images]: the optional user-supplied room photo is uploaded only to the configured test stack (RM-465)
 * GDPR[erasure]: a throwaway account owns the upload and is erased in finally (RM-465)
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { THEME_KEY_FOR_TESTS } from "../visual-theme";

const compose = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function helper(...args: string[]): Record<string, string> {
  const [command = "docker", ...rest] = compose;
  const output = execFileSync(
    command,
    [...rest, "exec", "-T", "api", "python", "scripts/e2e_session.py", ...args],
    { encoding: "utf8" },
  );
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, string>;
}

/** Register in interior.spec.ts's serial suite: its storage-failure case stops the shared S3 test store. */
export function registerMobileInteriorJourneys() {
  for (const theme of ["light", "dark"] as const) {
    for (const width of [320, 390, 768]) {
      test(`interior portrait upload and every wizard step: ${theme}, ${String(width)} px`, async ({
        page,
        context,
        baseURL,
      }, testInfo) => {
        test.setTimeout(60_000);
        const account = helper("create", "--credits", "0");
        try {
          const session = helper(
            "session-for",
            "--email",
            account["email"] ?? "",
            "--entitlement",
            "unlimited_reports",
          );
          await context.addCookies([
            {
              name: session["cookie_name"] ?? "",
              value: session["cookie_value"] ?? "",
              url: baseURL ?? "http://localhost:4173",
              httpOnly: true,
              secure: true,
              sameSite: "Lax",
            },
          ]);
          await page.setViewportSize({ width, height: 844 });
          await page.addInitScript(
            ([key, value]) => localStorage.setItem(key ?? "", value ?? ""),
            [THEME_KEY_FOR_TESTS, theme],
          );

          const supplied = process.env["INTERIOR_ROOM_PHOTO"];
          const buffer = supplied
            ? readFileSync(supplied)
            : Buffer.from(
                await page.evaluate(() => {
                  const canvas = document.createElement("canvas");
                  canvas.width = 900;
                  canvas.height = 1200;
                  const ctx = canvas.getContext("2d");
                  if (!ctx) throw new Error("Canvas context unavailable");
                  ctx.fillStyle = "#cbbda9";
                  ctx.fillRect(0, 0, 900, 1200);
                  return canvas.toDataURL("image/png").split(",")[1] ?? "";
                }),
                "base64",
              );

          await page.goto("/app/interior");
          await page.getByRole("textbox", { name: "Nazwa projektu" }).fill("Pokój — próba mobilna");
          await page.getByRole("button", { name: "Utwórz projekt" }).click();
          await expect(page.getByRole("heading", { level: 1, name: "Pokój — próba mobilna" })).toBeVisible();
          const projectId = new URL(page.url()).pathname.split("/").at(-1) ?? "";
          const accepted = page.waitForResponse(
            (response) =>
              response.url().endsWith(`/projects/${projectId}/source`) &&
              response.request().method() === "POST",
          );
          const chooser = page.waitForEvent("filechooser");
          await page.getByRole("button", { name: "Wybierz zdjęcie pokoju" }).click();
          await (
            await chooser
          ).setFiles({
            name: supplied ? "room.jpg" : "room.png",
            mimeType: supplied ? "image/jpeg" : "image/png",
            buffer,
          });
          const upload = await accepted;
          expect(upload.status()).toBe(201);
          const source = (await upload.json()) as { width: number; height: number; content_digest: string };
          expect(source.width).toBe(900);
          expect(source.height).toBe(1200);
          const image = page.getByRole("img", { name: "Zdjęcie pokoju, z którego powstaje wizualizacja" });
          await expect(image).toBeVisible();
          await expect
            .poll(() =>
              image.evaluate((element: HTMLImageElement) => element.complete && element.naturalWidth),
            )
            .toBe(900);
          const imageUrl = await image.getAttribute("src");
          expect(imageUrl).toMatch(new RegExp(`^/api/interior/projects/${projectId}/media/`));
          const stored = await page.request.get(imageUrl ?? "");
          expect(stored.status()).toBe(200);
          expect(stored.headers()["content-type"]).toContain("image/jpeg");
          expect(
            createHash("sha256")
              .update(await stored.body())
              .digest("hex"),
          ).toBe(source.content_digest);
          await expect(image).toHaveCSS("object-fit", "contain");

          async function capture(step: string) {
            const labelsFit = await page.getByRole("navigation", { name: "Etapy projektu" }).evaluate((nav) =>
              [...nav.querySelectorAll("button")].every((button) => {
                const bounds = button.getBoundingClientRect();
                return [...button.querySelectorAll("strong")]
                  .filter((label) => label.getBoundingClientRect().width > 0)
                  .every((label) => {
                    const text = label.getBoundingClientRect();
                    return text.left >= bounds.left && text.right <= bounds.right;
                  });
              }),
            );
            expect(labelsFit, "step labels stay inside their touch targets").toBe(true);
            await expect
              .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
              .toBe(true);
            expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
            await page.screenshot({
              path: testInfo.outputPath(`interior-${step}-${theme}-${String(width)}.png`),
              fullPage: true,
            });
          }

          await capture("photo");
          await page.getByRole("button", { name: "Dalej" }).click();
          await expect(page.getByRole("heading", { name: "Jak chcesz się tu czuć?" })).toBeVisible();
          await page.getByRole("combobox", { name: "Styl", exact: true }).click();
          await page.getByRole("option", { name: "Własny styl", exact: true }).click();
          await page.getByRole("textbox", { name: "Nazwa własnego stylu" }).fill("Naturalny z zielenią");
          await page.getByRole("textbox", { name: "Rzeczy, które zostają" }).fill("Piec kaflowy");
          await page.getByRole("button", { name: "Zapisz założenia" }).click();
          await expect(page.getByText("Założenia zapisane.")).toBeVisible();
          await capture("direction");
          await page.getByRole("button", { name: "Dalej" }).click();
          await expect(page.getByRole("heading", { name: "Zrób miejsce na swoje pomysły." })).toBeVisible();
          await capture("furniture");
          await page.getByRole("button", { name: "Przejdź do podsumowania" }).click();
          await expect(page.getByRole("heading", { name: "Zobacz nową perspektywę." })).toBeVisible();
          await page.getByRole("button", { name: "Zapisz wersję", exact: true }).click();
          await expect(page.getByText("Wersja zapisana.")).toBeVisible();
          await capture("review");
          await page.reload();
          await expect(page.getByRole("heading", { name: "Zobacz nową perspektywę." })).toBeVisible();
          await page.getByRole("button", { name: /Krok 1/ }).click();
          await expect(image).toHaveAttribute("src", imageUrl ?? "");
          await expect
            .poll(() =>
              image.evaluate((element: HTMLImageElement) => element.complete && element.naturalHeight),
            )
            .toBe(1200);
        } finally {
          helper("delete", account["user_id"] ?? "");
        }
      });
    }
  }
}
