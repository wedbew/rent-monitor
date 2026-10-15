import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";

import { routes } from "./routes";

describe("foundation", () => {
  it("renders the honest placeholder on any path", () => {
    render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: ["/anything"] })} />);
    expect(screen.getByRole("heading", { name: "renti" })).toBeInTheDocument();
    expect(screen.getByText("Aplikacja jest w budowie.")).toBeInTheDocument();
  });
});
