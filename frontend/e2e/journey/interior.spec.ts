/**
 * Architekt wnętrz against the real stack: the built SPA, the real API and Postgres, the real worker (`worker-ops`),
 * the production object-store code (boto3 against `s3mock`, a real S3 API server standing in for the private R2
 * bucket) and the real atomic AI budget. Only three things are stand-ins, all named in `deploy/compose.e2e.yml`: the
 * demo product catalogue, the offline image model and `s3mock`. No provider key exists in this stack.
 *
 * Evidence class: fake provider data, throwaway accounts and a disposable stack; not a live merchant, not a live model,
 * not R2. Needs the stack up: see frontend/README.md (Journey lane).
 */
import { execFileSync } from "node:child_process";
import { crc32, deflateSync } from "node:zlib";

import { request, type BrowserContext, type Page } from "@playwright/test";

import { expect, test } from "./fixtures";

import { registerMobileInteriorJourneys } from "./interior-mobile";

const COMPOSE = (
  process.env["E2E_COMPOSE"] ?? "docker compose -f ../deploy/compose.yml -f ../deploy/compose.e2e.yml"
).split(" ");

function compose(...args: string[]): string {
  const [command = "docker", ...rest] = COMPOSE;
  return execFileSync(command, [...rest, ...args], { encoding: "utf8" });
}

function helper(...args: string[]): Record<string, unknown> {
  const output = compose("exec", "-T", "api", "python", "scripts/e2e_session.py", ...args);
  return JSON.parse(output.trim().split("\n").at(-1) ?? "{}") as Record<string, unknown>;
}

interface Seeded {
  user_id: string;
  email: string;
  cookie_name: string;
  cookie_value: string;
}

/** A throwaway account; `entitled` accounts are in the closed beta (the staff entitlement), others are not. */
function seed(entitled: boolean): Seeded {
  const made = helper("create", "--credits", "0") as unknown as Seeded;
  return entitled
    ? (helper(
        "session-for",
        "--email",
        made.email,
        "--entitlement",
        "unlimited_reports",
      ) as unknown as Seeded)
    : made;
}

async function signIn(context: BrowserContext, who: Seeded, baseURL: string | undefined) {
  await context.clearCookies();
  await context.addCookies([
    {
      name: who.cookie_name,
      value: who.cookie_value,
      url: baseURL ?? "http://localhost:4173",
      httpOnly: true,
      secure: true,
      sameSite: "Lax",
    },
  ]);
}

/** A real, valid PNG (the server decodes, strips and re-encodes it): flat colour, no library needed. */
function png(width: number, height: number, rgb: [number, number, number]): Buffer {
  const chunk = (type: string, data: Buffer): Buffer => {
    const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const out = Buffer.alloc(8 + data.length + 4);
    out.writeUInt32BE(data.length, 0);
    body.copy(out, 4);
    out.writeUInt32BE(crc32(body), 8 + data.length);
    return out;
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8-bit RGB
  const row = Buffer.concat([Buffer.from([0]), Buffer.from(Array.from({ length: width }, () => rgb).flat())]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const room = (shade = 0) => ({
  name: "pokoj.png",
  mimeType: "image/png",
  buffer: png(320, 240, [180 - shade, 160, 140]),
});
const section = (page: Page, name: string) => page.getByRole("region", { name });
const money = (digits: string) => new RegExp(`${digits.replace(" ", "\\s")}\\szł`);

async function upload(
  page: Page,
  button: string | RegExp,
  file: { name: string; mimeType: string; buffer: Buffer },
) {
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: button }).click();
  await (await chooser).setFiles(file);
}

/** The pixels of an `<img>` really arrived (a broken picture has no natural width). */
async function imageLoaded(page: Page, name: string): Promise<void> {
  const img = page.getByRole("img", { name });
  await expect(img).toBeVisible();
  await img.scrollIntoViewIfNeeded(); // lazy pictures load when they come into view
  await expect
    .poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
    .toBe(true);
}

async function createProject(page: Page, name: string): Promise<string> {
  await page.goto("/app/interior");
  await page.getByRole("textbox", { name: "Nazwa projektu" }).fill(name);
  await page.getByRole("button", { name: "Utwórz projekt" }).click();
  await expect(page).toHaveURL(/\/app\/interior\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name })).toBeVisible();
  await page.getByRole("button", { name: "Pokaż wszystkie narzędzia" }).click();
  return new URL(page.url()).pathname.split("/").at(-1) ?? "";
}

async function saveVersion(page: Page): Promise<void> {
  await section(page, "Wersje").getByRole("button", { name: "Zapisz wersję" }).click();
  await expect(page.getByText("Wersja zapisana.")).toBeVisible();
}

const ORIGIN_HEADER = (baseURL: string | undefined) => ({ Origin: baseURL ?? "http://localhost:4173" });

let tester: Seeded;
let beta2: Seeded;
let stranger: Seeded;
let projectId = "";
let mediaPath = "";
let generationId = "";

test.describe.configure({ mode: "serial" });

test.beforeAll(() => {
  tester = seed(true);
  beta2 = seed(true);
  stranger = seed(false);
});

test.afterAll(() => {
  for (const who of [tester, beta2, stranger]) helper("delete", who.user_id);
  helper("ai-budget", "--clear");
});

test("sign in, create a project, upload the room, brief it, add own items, pick real-shaped products, save a version, generate, reload", async ({
  context,
  page,
  baseURL,
}) => {
  await signIn(context, tester, baseURL);
  helper("ai-budget", "--clear"); // the month's allowance starts unspent; billed calls are compared with this baseline
  const baseline = Number(helper("ai-usage")["billed_calls"]);

  // 1. the architect is a working screen for an entitled tester
  await page.goto("/app/interior");
  await expect(page.getByRole("heading", { level: 1, name: "Architekt wnętrz" })).toBeVisible();
  await expect(page.getByText("Nie masz jeszcze projektu")).toBeVisible();
  await expect(page.getByText("w budowie")).toHaveCount(0);
  projectId = await createProject(page, "Salon E2E");

  // 2. the room photo goes through the server (normalised, stored in the bucket) and comes back by the private route
  await upload(page, "Wybierz zdjęcie pokoju", room());
  await imageLoaded(page, "Zdjęcie pokoju, z którego powstaje wizualizacja");
  const src = await page
    .getByRole("img", { name: "Zdjęcie pokoju, z którego powstaje wizualizacja" })
    .getAttribute("src");
  expect(src).toMatch(new RegExp(`^/api/interior/projects/${projectId}/media/[0-9a-f-]{36}$`));
  mediaPath = src ?? "";
  const delivered = await page.request.get(mediaPath);
  expect(delivered.status()).toBe(200);
  expect(delivered.headers()["content-type"]).toBe("image/jpeg");
  expect(delivered.headers()["cache-control"]).toBe("private, no-store");
  expect((await delivered.body()).subarray(0, 2).toString("hex")).toBe("ffd8"); // re-encoded JPEG, whatever was sent
  const bare = await request.newContext(baseURL === undefined ? {} : { baseURL });
  expect((await bare.get(mediaPath)).status()).toBe(401); // no cookie, no picture
  await bare.dispose();

  // 3. the brief
  const brief = section(page, "Założenia");
  await brief.getByRole("combobox", { name: "Styl", exact: true }).click();
  await page.getByRole("option", { name: "Skandynawski", exact: true }).click();
  await brief.getByRole("textbox", { name: "Budżet na wyposażenie (zł)" }).fill("6000");
  await brief.getByRole("button", { name: "Zapisz założenia" }).click();
  await expect(page.getByText("Założenia zapisane.")).toBeVisible();

  // 4. own items: a name alone is enough; one gets a photo
  const items = section(page, "Twoje rzeczy");
  await items.getByRole("textbox", { name: "Nazwa rzeczy" }).fill("Stary fotel");
  await items.getByRole("button", { name: "Dodaj rzecz" }).click();
  const old = items.getByRole("listitem").filter({ has: page.getByRole("heading", { name: "Stary fotel" }) });
  await expect(old.getByText("Cena nieznana")).toBeVisible();
  await expect(old.getByText("Dodane przez Ciebie, niezweryfikowane")).toBeVisible();
  await items.getByRole("textbox", { name: "Nazwa rzeczy" }).fill("Regał");
  await items.getByRole("textbox", { name: "Cena za sztukę (zł, opcjonalnie)" }).fill("199,99");
  await items.getByRole("button", { name: "Dodaj rzecz" }).click();
  await expect(items.getByRole("heading", { name: "Regał", level: 3 })).toBeVisible();
  await upload(page, "Dodaj zdjęcie: Regał", room(40));
  await imageLoaded(page, "Zdjęcie rzeczy: Regał");

  // 5. the catalogue: labelled as demo data; unknown price and unknown delivery are said, never zero
  const catalogue = section(page, "Katalog produktów");
  await expect(catalogue.getByText(/dane przykładowe, nie sklep/)).toBeVisible();
  const board = section(page, "Tablica produktów");
  for (const [query, pick] of [
    ["sofa", /^Wybierz: Sofa Nordic 3-osobowa \(szary/],
    ["lampa", /^Wybierz: Lampa podłogowa Arc \(biały/],
    ["stół", /^Wybierz: Stół dębowy 140x80 \(dąb, 140x80/],
  ] as const) {
    await catalogue.getByRole("textbox", { name: "Czego szukasz" }).fill(query);
    await catalogue.getByRole("button", { name: "Szukaj produktów" }).click();
    const results = catalogue.getByRole("list", { name: "Znalezione produkty" });
    await expect(results).toBeVisible();
    await results.getByRole("button", { name: pick }).click();
    await expect(board.getByRole("listitem").first()).toBeVisible();
  }
  const sofa = board
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Sofa Nordic 3-osobowa" }) });
  await expect(sofa.getByText("Aktualna oferta")).toBeVisible();
  await expect(sofa.getByText(/Sprawdzono:/)).toBeVisible();
  await expect(sofa.getByText(money("2 499,00"), { exact: false }).first()).toBeVisible();
  const lamp = board
    .getByRole("listitem")
    .filter({ has: page.getByRole("heading", { name: "Lampa podłogowa Arc" }) });
  await expect(lamp.getByText("Cena nieznana")).toBeVisible();
  await expect(lamp.getByText("Razem: nie obliczamy")).toBeVisible();
  // the server's own sums: 199,99 (own shelf) + 2 499 + 1 299 priced; the own armchair without a price and the lamp are
  // left out and counted; one delivery is unknown and one is known (149 zł); this is said not to be the cost of the room
  await expect(board.getByText(/Suma znanych cen: 3\s?997,99/)).toBeVisible();
  await expect(board.getByText(/Pozycje bez ceny \(poza sumą\): 2/)).toBeVisible();
  await expect(board.getByText(/Znane koszty dostawy: 149,00/)).toBeVisible();
  await expect(board.getByText(/Pozycje z nieznaną dostawą: 1/)).toBeVisible();
  await expect(board.getByText(/To nie jest pełny koszt/)).toBeVisible();

  // 6. an immutable version, then the visualisation, run by the real worker through the real budget gate
  await saveVersion(page);
  await expect(page.getByRole("heading", { name: "Wersja 1", level: 3 })).toBeVisible();
  await page.getByRole("button", { name: "Generuj wizualizację z wersji 1" }).click();
  await expect(page.getByText("Gotowa")).toBeVisible({ timeout: 60_000 });
  await imageLoaded(page, "Ilustracja pokoju z wybranymi rzeczami");
  await imageLoaded(page, "Zdjęcie pokoju, z którego powstaje wizualizacja");
  await expect(page.getByText("Przed: oryginalne zdjęcie")).toBeVisible();
  await expect(page.getByText("Po: ilustracja")).toBeVisible();
  await expect(page.getByText("Ilustracja, nie dokładny wygląd produktów")).toBeVisible();
  await expect(page.getByText(/Koszt: 0,034 USD/)).toBeVisible();
  // three picked products (their demo pictures are permitted references) and the own item with a photo are sent;
  // the own item without a photo is described by its name only and counted as skipped
  await expect(page.getByText(/wysłano 4, pominięto 1/)).toBeVisible();

  // 7. exactly one model call was billed, and a reload neither starts nor pays for another
  const usage = helper("ai-usage");
  expect(Number(usage["billed_calls"]) - baseline).toBe(1);
  expect(usage["spent"]).toBe("0.034000");
  expect(usage["reserved"]).toBe("0.000000");
  const list = await page.request.get(`/api/interior/projects/${projectId}/generations`);
  const generations = (await list.json()) as { generation_id: string; state: string }[];
  expect(generations.map((g) => g.state)).toEqual(["succeeded"]);
  generationId = generations[0]?.generation_id ?? "";
  await page.reload();
  await expect(page.getByText("Gotowa")).toBeVisible();
  await imageLoaded(page, "Ilustracja pokoju z wybranymi rzeczami");
  expect(Number(helper("ai-usage")["billed_calls"]) - baseline).toBe(1);
  expect(
    ((await (await page.request.get(`/api/interior/projects/${projectId}/generations`)).json()) as unknown[])
      .length,
  ).toBe(1);
});

test("the closed beta and tenant isolation: a stranger is refused, another tester gets 404 everywhere, sign-out and switching leave nothing behind", async ({
  context,
  page,
  baseURL,
}) => {
  test.skip(projectId === "", "needs the project of the first journey");
  const origin = ORIGIN_HEADER(baseURL);

  // someone outside the beta: the page says so, the API refuses with its own code
  await signIn(context, stranger, baseURL);
  await page.goto("/app/interior");
  await expect(page.getByText("Architekt wnętrz jest w zamkniętej wersji beta")).toBeVisible();
  await expect(page.getByRole("button", { name: "Utwórz projekt" })).toHaveCount(0);
  const refused = await page.request.get(`/api/interior/projects/${projectId}`);
  expect(refused.status()).toBe(403);
  expect(((await refused.json()) as { code: string }).code).toBe("FEATURE_NOT_IN_PLAN");

  // another entitled tester: the first tester's project, picture and operation do not exist for them
  await signIn(context, beta2, baseURL);
  await page.goto("/app/interior");
  await expect(page.getByText("Nie masz jeszcze projektu")).toBeVisible();
  await expect(page.getByText("Salon E2E")).toHaveCount(0);
  for (const [method, path] of [
    ["GET", `/api/interior/projects/${projectId}`],
    ["GET", mediaPath],
    ["GET", `/api/interior/projects/${projectId}/generations/${generationId}`],
    ["POST", `/api/interior/projects/${projectId}/revisions`],
    ["DELETE", `/api/interior/projects/${projectId}`],
  ] as const) {
    const reply = await page.request.fetch(path, { method, headers: origin });
    expect([method, path, reply.status()]).toEqual([method, path, 404]);
  }
  await page.goto(`/app/interior/${projectId}`);
  await expect(page.getByText("Nie ma takiego projektu albo wygasł.")).toBeVisible();

  // the first tester's data survived all of that
  await signIn(context, tester, baseURL);
  await page.goto(`/app/interior/${projectId}`);
  await expect(page.getByRole("heading", { level: 1, name: "Salon E2E" })).toBeVisible();

  // signing out leaves no interior content on screen or reachable
  await page.getByRole("button", { name: "Wyloguj się" }).click();
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByText("Salon E2E")).toHaveCount(0);
  expect((await page.request.get(`/api/interior/projects/${projectId}`)).status()).toBe(401);
});

test("failures are actionable and never cost twice: a refused file, storage down, stale offers, a refusing model, a lost answer, no budget, a repeated click", async ({
  context,
  page,
  baseURL,
}) => {
  test.setTimeout(240_000);
  // the previous journey signed this account out (the server revoked that session): a fresh one
  tester = helper("session-for", "--email", tester.email) as unknown as Seeded;
  await signIn(context, tester, baseURL);
  const id = await createProject(page, "Sypialnia E2E");
  helper("ai-budget", "--clear");
  const before = helper("ai-usage");

  // a file that is not an image is refused with its reason; the project stays
  await upload(page, "Wybierz zdjęcie pokoju", {
    name: "x.png",
    mimeType: "image/png",
    buffer: Buffer.from("to nie jest zdjęcie"),
  });
  await expect(page.getByText("Nie udało się odczytać tego pliku jako zdjęcia.")).toBeVisible();
  await expect(page.getByText("Nie dodano jeszcze zdjęcia pokoju.")).toBeVisible();

  // the bucket is down: a clear message, the project untouched, and it works again when the store is back
  compose("stop", "s3mock");
  try {
    await upload(page, "Wybierz zdjęcie pokoju", room());
    await expect(page.getByText("Zdjęcia są chwilowo niedostępne")).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { level: 1, name: "Sypialnia E2E" })).toBeVisible();
  } finally {
    compose("start", "s3mock");
    for (let i = 0; i < 40; i += 1) {
      try {
        if (compose("ps", "--format", "{{.Health}}", "s3mock").includes("healthy")) break;
      } catch {
        /* still starting */
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
  }
  await upload(page, "Wybierz zdjęcie pokoju", room());
  await imageLoaded(page, "Zdjęcie pokoju, z którego powstaje wizualizacja");

  // one product, then its observation ages: the offer leaves the sum and a re-check brings it back
  const catalogue = section(page, "Katalog produktów");
  await catalogue.getByRole("textbox", { name: "Czego szukasz" }).fill("sofa");
  await catalogue.getByRole("button", { name: "Szukaj produktów" }).click();
  await catalogue.getByRole("button", { name: /^Wybierz: Sofa Nordic 3-osobowa \(szary/ }).click();
  const board = section(page, "Tablica produktów");
  await expect(board.getByText("Aktualna oferta")).toBeVisible();
  expect(helper("expire-selections", "--project", id)["expired"]).toBe(1);
  await page.reload();
  await expect(board.getByText("Oferta wygasła")).toBeVisible();
  await expect(board.getByText("Razem: nie obliczamy")).toBeVisible();
  await expect(board.getByText(/Oferty wygasłe lub niedostępne \(poza sumą\): 1/)).toBeVisible();
  await expect(board.getByText(/Suma znanych cen: 0,00/)).toBeVisible();
  await board.getByRole("button", { name: /^Sprawdź ponownie: Sofa Nordic/ }).click();
  await expect(board.getByText("Aktualna oferta")).toBeVisible();

  // a model that refuses: said in words, nothing is charged, the hold is released
  const notes = section(page, "Założenia").getByRole("textbox", { name: "Dodatkowe życzenia" });
  const setNotes = async (value: string) => {
    await notes.fill(value);
    await section(page, "Założenia").getByRole("button", { name: "Zapisz założenia" }).click();
    await expect(page.getByText("Założenia zapisane.")).toBeVisible();
  };
  const generate = async (version: number) => {
    await saveVersion(page);
    await page.getByRole("button", { name: `Generuj wizualizację z wersji ${String(version)}` }).click();
  };
  await setNotes("FAKE_REJECT");
  await generate(1);
  await expect(page.getByText("Dostawca odrzucił zapytanie. Nic nie zostało naliczone.")).toBeVisible({
    timeout: 60_000,
  });
  let usage = helper("ai-usage");
  expect([usage["spent"], usage["reserved"], usage["billed_calls"]]).toEqual([
    before["spent"],
    "0.000000",
    before["billed_calls"],
  ]);

  // an answer that never came: the estimate stays charged, nothing is retried by itself
  await setNotes("FAKE_UNKNOWN");
  await generate(2);
  await expect(page.getByText(/nie dostaliśmy odpowiedzi/)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Koszt szacunkowy: 0,1 USD/)).toBeVisible();
  usage = helper("ai-usage");
  expect(usage["spent"]).toBe("0.100000");
  expect(usage["reserved"]).toBe("0.000000");
  const afterUnknown = (await (
    await page.request.get(`/api/interior/projects/${id}/generations`)
  ).json()) as unknown[];
  expect(afterUnknown).toHaveLength(2); // one per click, none added behind the person's back

  // no budget left: nothing is sent at all
  helper("ai-budget", "--fill");
  await setNotes("zwykłe życzenia");
  await generate(3);
  await expect(page.getByText("Wyczerpano wspólny budżet na testy. Nic nie zostało wysłane.")).toBeVisible({
    timeout: 60_000,
  });
  helper("ai-budget", "--clear");

  // a new attempt after the allowance is back succeeds; a fast double click starts only one operation
  await page.getByRole("button", { name: "Generuj wizualizację z wersji 3" }).dblclick();
  await expect(page.getByText("Gotowa")).toBeVisible({ timeout: 60_000 });
  const operations = (await (await page.request.get(`/api/interior/projects/${id}/generations`)).json()) as {
    revision_id: string;
  }[];
  expect(operations.filter((o) => o.revision_id === operations[0]?.revision_id)).toHaveLength(2); // the budget failure and the success
  expect(operations).toHaveLength(4);

  // the same Idempotency-Key, sent twice at once, is one operation and one charge
  const revisions = (await (await page.request.get(`/api/interior/projects/${id}`)).json()) as {
    revisions: { revision_id: string }[];
  };
  const revision = revisions.revisions[0]?.revision_id ?? "";
  await saveVersion(page);
  const fresh =
    (
      (await (await page.request.get(`/api/interior/projects/${id}`)).json()) as {
        revisions: { revision_id: string }[];
      }
    ).revisions[0]?.revision_id ?? revision;
  const key = crypto.randomUUID();
  const send = () =>
    page.request.post(`/api/interior/projects/${id}/generations`, {
      headers: { ...ORIGIN_HEADER(baseURL), "Idempotency-Key": key },
      data: { revision_id: fresh },
    });
  const [a, b] = await Promise.all([send(), send()]);
  expect([a.status(), b.status()].sort()).toEqual([200, 202]);
  const first = (await a.json()) as { generation_id: string };
  const second = (await b.json()) as { generation_id: string };
  expect(first.generation_id).toBe(second.generation_id);
  const operation = first.generation_id;
  await expect
    .poll(
      async () =>
        (
          (await (
            await page.request.get(`/api/interior/projects/${id}/generations/${operation}`)
          ).json()) as { state: string }
        ).state,
      {
        timeout: 60_000,
      },
    )
    .toBe("succeeded");
  const final = helper("ai-usage");
  expect(final["reserved"]).toBe("0.000000");
  expect(Number(final["billed_calls"]) - Number(before["billed_calls"])).toBe(3); // the lost answer (estimate) and two successes; the refusal, the empty budget and the repeats cost nothing
});

// Keep portrait uploads after the storage-failure journey in this same serial suite.
registerMobileInteriorJourneys();
