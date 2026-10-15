import { createBrowserRouter, Navigate, type RouteObject } from "react-router";

import { AnalysesPage } from "./features/analyses/list/AnalysesPage";
import { AnalysisPage } from "./features/analyses/AnalysisPage";
import { NewAnalysisPage } from "./features/analyses/new/NewAnalysisPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { EmailLinkPage, VerifySignupPage } from "./features/auth/LinkPages";
import { LoginPage } from "./features/auth/LoginPage";
import { ForgotPasswordPage, ResetPasswordPage } from "./features/auth/PasswordPages";
import { PublicLayout } from "./features/auth/PublicLayout";
import { SignupPage } from "./features/auth/SignupPage";
import { AppShell } from "./shell/AppShell";
import { type Destination, LEGAL, PRIMARY } from "./shell/navigation";
import { NotFound } from "./shell/NotFound";
import { PendingPage } from "./shell/PendingPage";
import { RootLayout } from "./shell/RootLayout";
import { RouteError } from "./shell/RouteError";
import { RedirectIfSignedIn, RequireSession } from "./shell/session";

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
 * The one place routes are declared.
 *  - Auth pages (signed-out frame): sign-in, sign-up, the three pages the API's emails link to, password recovery.
 *  - `/app/*`: behind the session boundary; a signed-out visit goes to sign-in and comes back.
 *  - Documents and unknown paths: the shell, no session needed.
 * Pages are placeholders until their slice lands (#272 onwards); errors render inside their frame.
 */
export const routes: RouteObject[] = [
  {
    element: <RootLayout />,
    children: [
      {
        element: <PublicLayout />,
        errorElement: <RouteError />,
        children: [
          {
            path: "/login",
            element: (
              <RedirectIfSignedIn>
                <LoginPage />
              </RedirectIfSignedIn>
            ),
          },
          {
            path: "/signup",
            element: (
              <RedirectIfSignedIn>
                <SignupPage />
              </RedirectIfSignedIn>
            ),
          },
          // The three links the API mails. A signed-in person who follows one must still reach it.
          { path: "/login/email", element: <EmailLinkPage /> },
          { path: "/signup/verify", element: <VerifySignupPage /> },
          { path: "/password/reset", element: <ResetPasswordPage /> },
          { path: "/password/forgot", element: <ForgotPasswordPage /> },
        ],
      },
      {
        element: <RequireSession />,
        children: [
          {
            element: <AppShell />,
            errorElement: <RouteError />,
            children: [
              {
                errorElement: <RouteError />,
                children: [
                  { path: "/app", element: <DashboardPage /> },
                  {
                    path: "/app/credits",
                    element: <PendingPage title="Raporty i zakupy" availability="building" />,
                  },
                  { path: "/app/analyses/new", element: <NewAnalysisPage /> },
                  { path: "/app/analyses", element: <AnalysesPage /> },
                  {
                    path: "/app/analyses/:auditId",
                    element: <AnalysisPage />,
                  },
                  pending("market", "/app/market"),
                  pending("interior", "/app/interior"),
                  pending("listing", "/app/listings/new"),
                  pending("settings", "/app/settings"),
                ],
              },
            ],
          },
        ],
      },
      {
        element: <AppShell />,
        errorElement: <RouteError />,
        children: [
          {
            errorElement: <RouteError />,
            children: [
              { index: true, element: <Navigate to="/app" replace /> },
              pending("terms", "/terms"),
              pending("privacy", "/privacy"),
              { path: "*", element: <NotFound /> },
            ],
          },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
