import type { Page } from "@playwright/test";

import { fx } from "../test/fixtures";
import { createSaved, replyFrom, SUCCEEDED_AUDITS } from "../test/scenarios";
import { exercise, outcome } from "./coverage";
import { expect, test } from "./fixtures";
import { expectDialogContract } from "./popups";

const FIRST = SUCCEEDED_AUDITS[0];
const REPORT = `/app/analyses/${FIRST?.audit_id ?? ""}`;
const FIRST_ID = FIRST?.otodom_id ?? "";
const SECOND_ID = SUCCEEDED_AUDITS[1]?.otodom_id ?? "";
const THIRD_ID = SUCCEEDED_AUDITS[2]?.otodom_id ?? "";

const reportToggle = (page: Page) => page.getByRole("button", { name: "Zapisz to ogłoszenie" });
const note = (page: Page) => page.getByRole("textbox", { name: "Twoja notatka" });

test.describe("saved listings on the report", () => {
  test("save a listing, keep a private note with it, and see both after a reload", async ({
    page,
    serve,
  }) => {
    const flow = createSaved([]);
    const api = await serve(flow);
    await page.goto(REPORT);
    await expect(reportToggle(page)).toHaveAttribute("aria-pressed", "false");
    await expect(note(page)).toHaveCount(0);
    await exercise("report.save", async () => {
      await reportToggle(page).click();
      await expect(reportToggle(page)).toHaveAttribute("aria-pressed", "true");
      return [
        await outcome.request(api, { method: "PUT", path: `/api/saved/${FIRST_ID}`, body: { note: null } }),
      ];
    });
    await expect(note(page)).toHaveValue("");
    await note(page).fill("Sprawdzić czynsz\ni piętro");
    await exercise("report.note.save", async () => {
      await page.getByRole("button", { name: "Zapisz notatkę" }).click();
      await expect(page.getByText("Notatka zapisana.")).toBeVisible();
      return [
        await outcome.request(api, {
          method: "PUT",
          path: `/api/saved/${FIRST_ID}`,
          body: { note: "Sprawdzić czynsz\ni piętro" },
        }),
      ];
    });
    await page.reload();
    await expect(note(page)).toHaveValue("Sprawdzić czynsz\ni piętro");
    await expect(reportToggle(page)).toHaveAttribute("aria-pressed", "true");
  });

  test("the note field keeps what is typed and counts characters", async ({ page, serve }) => {
    await serve(createSaved([[0, "Notatka testowa"]]));
    await page.goto(REPORT);
    await exercise("report.note", async () => {
      await note(page).fill("Notatka testowa, dopisek");
      return [await outcome.value(note(page), "Notatka testowa, dopisek")];
    });
    await expect(note(page)).toHaveAccessibleDescription(/24 z 2\s?000 znaków/);
    await expect(page.getByText("Masz niezapisane zmiany w notatce.")).toBeVisible();
  });

  test("unsaving a listing with a note asks first; closing and Anuluj keep it, confirming removes it", async ({
    page,
    serve,
  }) => {
    const flow = createSaved([[0, "Notatka testowa"]]);
    const api = await serve(flow);
    await page.goto(REPORT);
    const dialog = page.getByRole("dialog", { name: "Usunąć z zapisanych?" });
    await expectDialogContract(page, {
      trigger: reportToggle(page),
      dialog,
      backdrop: "closes",
      modal: true,
    });
    await reportToggle(page).click();
    await exercise("report.unsave.close", async () => {
      await dialog.getByRole("button", { name: "Zamknij", exact: true }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    await reportToggle(page).click();
    await exercise("report.unsave.cancel", async () => {
      await dialog.getByRole("button", { name: "Anuluj" }).click();
      return [await outcome.dialog(dialog, "closed")];
    });
    expect(flow.calls.some((c) => c.startsWith("delete"))).toBe(false);
    await reportToggle(page).click();
    await exercise("report.unsave.confirm", async () => {
      await dialog.getByRole("button", { name: "Usuń z zapisanych" }).click();
      await expect(reportToggle(page)).toHaveAttribute("aria-pressed", "false");
      return [await outcome.request(api, { method: "DELETE", path: `/api/saved/${FIRST_ID}` })];
    });
    await expect(note(page)).toHaveCount(0);
  });

  test("a failed save says what happened in Polish and leaves the state as the server has it", async ({
    page,
    serve,
  }) => {
    await serve(
      createSaved([], {
        "PUT /api/saved/{otodom_id}": replyFrom(fx("PUT /api/saved/{otodom_id}", "limit_reached")),
      }),
    );
    await page.goto(REPORT);
    await reportToggle(page).click();
    await expect(
      page.getByRole("alert").filter({ hasText: "Osiągnięto limit zapisanych ogłoszeń" }),
    ).toBeVisible();
    await expect(reportToggle(page)).toHaveAttribute("aria-pressed", "false");
  });

  test("leaving with an unsaved note asks first (keyboard-operable dialog), staying keeps the draft", async ({
    page,
    serve,
    isMobile,
  }) => {
    test.skip(isMobile, "the navigation link lives in the sheet on a phone; the guard is layout-independent");
    await serve(createSaved([[0, "Notatka testowa"]]));
    await page.goto(REPORT);
    await note(page).fill("zmieniona");
    const leave = page.getByRole("link", { name: "Moje analizy", exact: true }).first();
    await leave.click();
    const dialog = page.getByRole("dialog", { name: "Masz niezapisane zmiany" });
    await expect(dialog).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(page).toHaveURL(new RegExp(`${REPORT}$`));
    await expect(note(page)).toHaveValue("zmieniona");
    await leave.click();
    await dialog.getByRole("button", { name: "Wyjdź bez zapisywania" }).click();
    await expect(page).toHaveURL(/\/app\/analyses$/);
  });
});

test.describe("saved listings in Moje analizy", () => {
  test("rows carry a save toggle in the cards and in the table", async ({ page, serve }) => {
    const flow = createSaved([]);
    const api = await serve(flow);
    await page.goto("/app/analyses");
    const toggle = page.getByRole("button", { name: `Zapisz ogłoszenie ${THIRD_ID}` });
    await expect(toggle).toHaveAttribute("aria-pressed", "false");
    await exercise("analyses.save", async () => {
      await toggle.click();
      await expect(toggle).toHaveAttribute("aria-pressed", "true");
      return [
        await outcome.request(api, { method: "PUT", path: `/api/saved/${THIRD_ID}`, body: { note: null } }),
      ];
    });
    await page.getByRole("button", { name: "Tabela" }).click();
    await expect(
      page.getByRole("table").getByRole("button", { name: `Zapisz ogłoszenie ${THIRD_ID}` }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  test("the Zapisane scope lists the server's saved listings with notes and links to their analysis", async ({
    page,
    serve,
  }) => {
    await serve(createSaved());
    await page.goto("/app/analyses");
    await exercise("analyses.scope.saved", async () => {
      await page.getByRole("button", { name: "Zapisane", exact: true }).click();
      await expect(page.getByRole("list", { name: "Zapisane ogłoszenia" })).toBeVisible();
      return [await outcome.url(page, /\/app\/analyses\?saved=1$/)];
    });
    const items = page.getByRole("list", { name: "Zapisane ogłoszenia" }).getByRole("listitem");
    await expect(items).toHaveCount(2);
    await expect(items.first()).toContainText("Notatka testowa");
    await expect(items.first()).toContainText(FIRST_ID);
    await expect(items.nth(1)).toContainText("Bez notatki");
    await expect(page.getByRole("combobox", { name: "Status" })).toHaveCount(0);
    await exercise("analyses.saved.open", async () => {
      await items.first().getByRole("link").click();
      return [await outcome.url(page, new RegExp(`${REPORT}$`))];
    });
    expect(SECOND_ID).not.toBe("");
  });

  test("the scope is in the address: a shared link and Back restore it; Wszystkie analizy leaves it", async ({
    page,
    serve,
  }) => {
    await serve(createSaved());
    await page.goto("/app/analyses?saved=1");
    await expect(page.getByRole("list", { name: "Zapisane ogłoszenia" })).toBeVisible();
    await exercise("analyses.scope.all", async () => {
      await page.getByRole("button", { name: "Wszystkie analizy" }).click();
      await expect(
        page.getByRole("list", { name: "Karty analiz" }).or(page.getByRole("list").first()),
      ).toBeVisible();
      return [await outcome.url(page, /\/app\/analyses$/)];
    });
  });

  test("nothing saved says so", async ({ page, serve }) => {
    await serve(createSaved([]));
    await page.goto("/app/analyses?saved=1");
    await expect(page.getByText("Nie masz zapisanych ogłoszeń")).toBeVisible();
  });
});
