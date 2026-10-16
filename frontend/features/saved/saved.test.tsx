import { QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, Link, RouterProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../api/query";
import { fx } from "../../test/fixtures";
import { useScenario as serveScenario } from "../../test/handlers";
import { createSaved, replyFrom, SUCCEEDED_AUDITS, type Reply } from "../../test/scenarios";
import { RequireSession, SessionProvider } from "../../shell/session";
import { advanceSessionGeneration, runTenantCleanups } from "../../shell/tenant";
import { NoteEditor } from "./NoteEditor";
import { SavedList } from "./SavedList";
import { SavedPanel } from "./SavedPanel";
import { SaveToggle } from "./SaveToggle";
import { useSavedState } from "./useSaved";

const NOTED = SUCCEEDED_AUDITS[0]?.otodom_id ?? ""; // saved, with a note
const PLAIN = SUCCEEDED_AUDITS[1]?.otodom_id ?? ""; // saved, no note
const UNSAVED = SUCCEEDED_AUDITS[2]?.otodom_id ?? "";

const reply = (operation: string, name: string): Reply => replyFrom(fx(operation, name));

function Panel({ id }: { readonly id: string }) {
  const state = useSavedState();
  const item = state.status === "ready" ? state.byId.get(id) : undefined;
  return item ? <NoteEditor item={item} /> : null;
}

function mount(element: React.ReactNode, flow = createSaved()) {
  serveScenario(flow);
  const client = createQueryClient();
  const router = createMemoryRouter(
    [
      {
        element: <RequireSession />,
        children: [
          {
            path: "/app/page",
            element: (
              <>
                {element}
                <Link to="/app/elsewhere">elsewhere</Link>
              </>
            ),
          },
          { path: "/app/elsewhere", element: <p>inna strona</p> },
        ],
      },
      { path: "/login", element: <p>logowanie</p> },
    ],
    { initialEntries: ["/app/page"] },
  );
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  );
  return { flow, router };
}

const toggle = (id: string) => screen.findByRole("button", { name: `Zapisz ogłoszenie ${id}` });

describe("SaveToggle", () => {
  it("shows the server's state: pressed when saved, not pressed when not", async () => {
    mount(
      <>
        <SaveToggle otodomId={NOTED} />
        <SaveToggle otodomId={UNSAVED} />
      </>,
    );
    expect(await toggle(NOTED)).toHaveAttribute("aria-pressed", "true");
    expect(await toggle(UNSAVED)).toHaveAttribute("aria-pressed", "false");
  });

  it("saves with no note and becomes pressed only after the server answered", async () => {
    const { flow } = mount(<SaveToggle otodomId={UNSAVED} />);
    await userEvent.click(await toggle(UNSAVED));
    await waitFor(async () => expect(await toggle(UNSAVED)).toHaveAttribute("aria-pressed", "true"));
    expect(flow.calls).toContain(`put:${UNSAVED}:`);
    expect(flow.saved.get(UNSAVED)?.note).toBeNull();
  });

  it("a second activation while the request is pending sends nothing more", async () => {
    const flow = createSaved([], {});
    const slow: Reply = { ...reply("PUT /api/saved/{otodom_id}", "saved_without_note"), delayMs: 300 };
    const real = flow.routes.find((r) => r.operation === "PUT /api/saved/{otodom_id}");
    let puts = 0;
    const counted: typeof flow = {
      ...flow,
      routes: [
        {
          operation: "PUT /api/saved/{otodom_id}",
          reply: (request) => {
            puts += 1;
            void real;
            return {
              ...slow,
              body: {
                otodom_id: request.params["otodom_id"],
                note: null,
                latest_audit_id: null,
                created_at: "2026-10-02T12:00:00Z",
              },
            };
          },
        },
        ...flow.routes.filter((r) => r.operation !== "PUT /api/saved/{otodom_id}"),
      ],
    };
    mount(<SaveToggle otodomId={UNSAVED} />, counted);
    const button = await toggle(UNSAVED);
    await userEvent.click(button);
    await userEvent.click(button);
    await waitFor(() => expect(puts).toBeGreaterThan(0));
    await new Promise((r) => setTimeout(r, 400));
    expect(puts).toBe(1);
  });

  it("a save still in flight when the session ends does not ask for the list again", async () => {
    const flow = createSaved();
    const put = flow.routes.find((r) => r.operation === "PUT /api/saved/{otodom_id}");
    if (put === undefined || typeof put.reply !== "function") throw new Error("no put route");
    mount(<SaveToggle otodomId={UNSAVED} />, {
      ...flow,
      routes: [
        {
          operation: "PUT /api/saved/{otodom_id}",
          reply: { ...reply("PUT /api/saved/{otodom_id}", "saved_without_note"), delayMs: 200 },
        },
        ...flow.routes.filter((r) => r.operation !== "PUT /api/saved/{otodom_id}"),
      ],
    });
    await userEvent.click(await toggle(UNSAVED));
    const listsBefore = flow.calls.filter((c) => c === "list").length;
    act(() => {
      runTenantCleanups();
      advanceSessionGeneration();
    });
    await new Promise((r) => setTimeout(r, 400));
    expect(flow.calls.filter((c) => c === "list").length).toBe(listsBefore);
  });

  it("a listing that was never analysed says so and stays not saved", async () => {
    mount(<SaveToggle otodomId="IDNEVER01" />);
    await userEvent.click(await toggle("IDNEVER01"));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(await toggle("IDNEVER01")).toHaveAttribute("aria-pressed", "false");
  });

  it("the 500 limit is said in Polish", async () => {
    mount(
      <SaveToggle otodomId={UNSAVED} />,
      createSaved(undefined, {
        "PUT /api/saved/{otodom_id}": reply("PUT /api/saved/{otodom_id}", "limit_reached"),
      }),
    );
    await userEvent.click(await toggle(UNSAVED));
    expect(await screen.findByText("Osiągnięto limit zapisanych ogłoszeń")).toBeInTheDocument();
  });

  it("a dropped connection says it does not know, and never claims success", async () => {
    mount(
      <SaveToggle otodomId={UNSAVED} />,
      createSaved(undefined, { "PUT /api/saved/{otodom_id}": { status: 0, networkError: true } }),
    );
    await userEvent.click(await toggle(UNSAVED));
    expect(await screen.findByText("Nie wiemy, czy zmiana się udała")).toBeInTheDocument();
  });

  it("unsaving a listing without a note deletes at once", async () => {
    const { flow } = mount(<SaveToggle otodomId={PLAIN} />);
    await userEvent.click(await toggle(PLAIN));
    await waitFor(() => expect(flow.saved.has(PLAIN)).toBe(false));
    expect(flow.calls).toContain(`delete:${PLAIN}`);
  });

  it("unsaving a listing with a note asks first: cancel keeps everything, confirm deletes", async () => {
    const { flow } = mount(<SaveToggle otodomId={NOTED} />);
    await userEvent.click(await toggle(NOTED));
    const dialog = await screen.findByRole("dialog", { name: "Usunąć z zapisanych?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Anuluj" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(flow.calls.some((c) => c.startsWith("delete"))).toBe(false);

    await userEvent.click(await toggle(NOTED));
    await userEvent.click(await screen.findByRole("button", { name: "Usuń z zapisanych" }));
    await waitFor(() => expect(flow.saved.has(NOTED)).toBe(false));
  });

  it("shows nothing while the saved list is unknown, so a note can never be replaced blindly", async () => {
    mount(
      <SaveToggle otodomId={UNSAVED} />,
      createSaved(undefined, { "GET /api/saved": { status: 503, body: { code: "NOT_READY" } } }),
    );
    await waitFor(() => expect(screen.queryByRole("button")).toBeNull());
  });
});

describe("SaveToggle with a full saved list (RM-347)", () => {
  const fullList = (): Reply => ({
    status: 200,
    body: Array.from({ length: 500 }, (_, n) => ({
      otodom_id: `9${String(n).padStart(8, "0")}`,
      note: null,
      latest_audit_id: null,
      created_at: "2026-10-01T10:00:00Z",
    })),
  });

  it("asks for the whole list in one request", async () => {
    const { flow } = mount(<SaveToggle otodomId={NOTED} />);
    await toggle(NOTED);
    expect(flow.calls).toContain("list?limit=500");
  });

  it("a listing missing from a full list is unknown: no toggle, so no blind save", async () => {
    const flow = createSaved(undefined, { "GET /api/saved": fullList() });
    mount(
      <>
        <SaveToggle otodomId={UNSAVED} />
        <SaveToggle otodomId="900000007" label="Zapisane na liście" />
      </>,
      flow,
    );
    expect(await screen.findByRole("button", { name: "Zapisane na liście" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.queryByRole("button", { name: `Zapisz ogłoszenie ${UNSAVED}` })).toBeNull();
    expect(flow.calls.filter((c) => c.startsWith("put:"))).toEqual([]);
  });

  it("saving a listing again sends no note and keeps the stored one", async () => {
    const flow = createSaved([[0, "stara notatka"]], { "DELETE /api/saved/{otodom_id}": { status: 204 } });
    mount(<SaveToggle otodomId={UNSAVED} />, flow);
    await userEvent.click(await toggle(UNSAVED));
    await waitFor(() => expect(flow.saved.has(UNSAVED)).toBe(true));
    expect(flow.calls).toContain(`put:${UNSAVED}:`); // no note key on the wire
    expect(flow.saved.get(NOTED)?.note).toBe("stara notatka");
  });
});

describe("NoteEditor", () => {
  it("shows the stored note and a counter in characters", async () => {
    mount(<Panel id={NOTED} />);
    const field = await screen.findByRole("textbox", { name: "Twoja notatka" });
    expect(field).toHaveValue("Notatka testowa");
    expect(field).toHaveAccessibleDescription(/15 z 2\s?000 znaków/);
  });

  it("saves the whole note, sending null for an empty one", async () => {
    const { flow } = mount(<Panel id={NOTED} />);
    const field = await screen.findByRole("textbox", { name: "Twoja notatka" });
    await userEvent.clear(field);
    await userEvent.type(field, "nowa");
    await userEvent.click(screen.getByRole("button", { name: "Zapisz notatkę" }));
    await waitFor(() => expect(flow.saved.get(NOTED)?.note).toBe("nowa"));
    expect(await screen.findByText("Notatka zapisana.")).toBeInTheDocument();

    await userEvent.clear(field);
    await userEvent.click(screen.getByRole("button", { name: "Zapisz notatkę" }));
    await waitFor(() => expect(flow.saved.get(NOTED)?.note).toBeNull());
  });

  it("refuses more than 2000 characters in the browser and sends nothing", async () => {
    const { flow } = mount(<Panel id={NOTED} />);
    const field = await screen.findByRole("textbox", { name: "Twoja notatka" });
    await userEvent.clear(field);
    await userEvent.click(field);
    await userEvent.paste("x".repeat(2001));
    await userEvent.click(screen.getByRole("button", { name: "Zapisz notatkę" }));
    expect((await screen.findAllByText(/najwyżej 2\s?000 znaków/)).length).toBeGreaterThan(0);
    expect(flow.calls.filter((c) => c.startsWith("put"))).toHaveLength(0);
  });

  it("leaving with an unsaved draft asks first; staying keeps the draft, leaving goes", async () => {
    const { router } = mount(<Panel id={NOTED} />);
    const field = await screen.findByRole("textbox", { name: "Twoja notatka" });
    await userEvent.type(field, " dopisek");
    expect(screen.getByText("Masz niezapisane zmiany w notatce.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: "elsewhere" }));
    const dialog = await screen.findByRole("dialog", { name: "Masz niezapisane zmiany" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Zostań i zapisz" }));
    expect(router.state.location.pathname).toBe("/app/page");
    expect(field).toHaveValue("Notatka testowa dopisek");

    await userEvent.click(screen.getByRole("link", { name: "elsewhere" }));
    await userEvent.click(await screen.findByRole("button", { name: "Wyjdź bez zapisywania" }));
    expect(await screen.findByText("inna strona")).toBeInTheDocument();
  });

  it("a clean note never blocks leaving, and closing the tab is only warned about for a draft", async () => {
    mount(<Panel id={NOTED} />);
    await screen.findByRole("textbox", { name: "Twoja notatka" });
    const clean = new Event("beforeunload", { cancelable: true });
    act(() => {
      window.dispatchEvent(clean);
    });
    expect(clean.defaultPrevented).toBe(false);
    await userEvent.click(screen.getByRole("link", { name: "elsewhere" }));
    expect(await screen.findByText("inna strona")).toBeInTheDocument();
  });

  it("a draft is warned about on tab close", async () => {
    mount(<Panel id={NOTED} />);
    await userEvent.type(await screen.findByRole("textbox", { name: "Twoja notatka" }), "x");
    const dirty = new Event("beforeunload", { cancelable: true });
    act(() => {
      window.dispatchEvent(dirty);
    });
    expect(dirty.defaultPrevented).toBe(true);
  });
});

describe("SavedPanel", () => {
  it("offers to save an unsaved listing, and no note yet", async () => {
    mount(<SavedPanel otodomId={UNSAVED} />);
    expect(await screen.findByRole("button", { name: "Zapisz to ogłoszenie" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.queryByRole("textbox", { name: "Twoja notatka" })).toBeNull();
  });

  it("saving reveals the note editor", async () => {
    mount(<SavedPanel otodomId={UNSAVED} />);
    await userEvent.click(await screen.findByRole("button", { name: "Zapisz to ogłoszenie" }));
    expect(await screen.findByRole("textbox", { name: "Twoja notatka" })).toHaveValue("");
  });
});

describe("SavedList", () => {
  it("lists the saved listings with their notes and a link to the newest analysis", async () => {
    mount(<SavedList />);
    const list = await screen.findByRole("list", { name: "Zapisane ogłoszenia" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Notatka testowa");
    expect(items[1]).toHaveTextContent("Bez notatki");
    expect(within(items[0] as HTMLElement).getByRole("link")).toHaveAttribute(
      "href",
      `/app/analyses/${SUCCEEDED_AUDITS[0]?.audit_id ?? ""}`,
    );
  });

  it("shows a hostile note as text, never as markup", async () => {
    mount(<SavedList />, createSaved([[0, "<img src=x onerror=alert(1)>"]]));
    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeInTheDocument();
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("says so when nothing is saved", async () => {
    mount(<SavedList />, createSaved([]));
    expect(await screen.findByText("Nie masz zapisanych ogłoszeń")).toBeInTheDocument();
  });

  it("an unreadable answer is a failure with a retry, not a crash", async () => {
    mount(
      <SavedList />,
      createSaved(undefined, { "GET /api/saved": { status: 200, body: { not: "a list" } } }),
    );
    expect(await screen.findByText("Nie udało się wczytać zapisanych ogłoszeń")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });
});
