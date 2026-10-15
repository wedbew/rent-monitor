import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { classifyRouteError, isChunkLoadError, RouteError } from "./RouteError";

function Boom({ error }: { error: Error }): never {
  throw error;
}

function renderWith(error: Error) {
  vi.spyOn(console, "error").mockImplementation(() => undefined); // React logs the caught render error
  const router = createMemoryRouter(
    [{ path: "/", element: <Boom error={error} />, errorElement: <RouteError /> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("chunk-load detection", () => {
  it.each([
    new TypeError("Failed to fetch dynamically imported module: https://x/assets/Report-abc.js"),
    new TypeError("error loading dynamically imported module"),
    new TypeError("Importing a module script failed."),
    Object.assign(new Error("Loading chunk 3 failed"), { name: "ChunkLoadError" }),
  ])("recognises %s", (error) => {
    expect(isChunkLoadError(error)).toBe(true);
    expect(classifyRouteError(error)).toBe("chunk");
  });

  it("does not mistake an ordinary error for a stale chunk", () => {
    expect(isChunkLoadError(new Error("x is undefined"))).toBe(false);
    expect(isChunkLoadError("not an error")).toBe(false);
    expect(classifyRouteError(new Error("x is undefined"))).toBe("unexpected");
  });
});

describe("RouteError", () => {
  it("offers a manual reload for a stale chunk, and never reloads by itself", () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    renderWith(new TypeError("Failed to fetch dynamically imported module: /assets/x.js"));
    expect(
      screen.getByRole("heading", { level: 1, name: "Dostępna jest nowa wersja aplikacji" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Wystąpił błąd");
    expect(screen.getByRole("button", { name: "Odśwież stronę" })).toBeInTheDocument();
    expect(reload).not.toHaveBeenCalled(); // a reload loop is impossible: only the person triggers it
    vi.unstubAllGlobals();
  });

  it("shows a retry and a way out for an unexpected error", () => {
    renderWith(new Error("boom"));
    expect(screen.getByRole("heading", { level: 1, name: "Coś poszło nie tak" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wróć do pulpitu" })).toHaveAttribute("href", "/app");
  });
});
