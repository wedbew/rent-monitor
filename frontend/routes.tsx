import { createBrowserRouter, Navigate, type RouteObject } from "react-router";

import { AppShell } from "./shell/AppShell";
import { type Destination, PRIMARY, LEGAL } from "./shell/navigation";
import { NotFound } from "./shell/NotFound";
import { PendingPage } from "./shell/PendingPage";
import { RouteError } from "./shell/RouteError";

const byId = (id: string): Destination => {
  const found = [...PRIMARY, ...LEGAL].find((d) => d.id === id);
  if (found === undefined) throw new Error(`no destination "${id}"`);
  return found;
};

function pending(id: string, path: string): RouteObject {
  const destination = byId(id);
  return {
    path,
    element: (
      <PendingPage
        title={destination.label}
        availability={destination.availability === "unavailable" ? "unavailable" : "building"}
      />
    ),
  };
}

/**
 * The one place routes are declared. Pages are placeholders until their slice lands (#272 onwards); the nav
 * destinations are honest about it (`PendingPage`). Errors render inside the shell, so navigation survives them.
 */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      {
        errorElement: <RouteError />,
        children: [
          { index: true, element: <Navigate to="/app" replace /> },
          pending("dashboard", "/app"),
          pending("new-analysis", "/app/analyses/new"),
          pending("analyses", "/app/analyses"),
          { path: "/app/analyses/:auditId", element: <PendingPage title="Raport" availability="building" /> },
          pending("market", "/app/market"),
          pending("interior", "/app/interior"),
          pending("listing", "/app/listings/new"),
          pending("settings", "/app/settings"),
          pending("terms", "/terms"),
          pending("privacy", "/privacy"),
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
