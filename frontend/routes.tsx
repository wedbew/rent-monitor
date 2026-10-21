import { type ComponentType, lazy, Suspense } from "react";
import { createBrowserRouter, Navigate, type RouteObject, useLocation, useParams } from "react-router";

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
import { AppLoading, RootLayout } from "./shell/RootLayout";
import { RouteError } from "./shell/RouteError";
import { RedirectIfSignedIn, RequireSession } from "./shell/session";

const NewAnalysisPage = lazy(async () => ({
  default: (await import("./features/analyses/new/NewAnalysisPage")).NewAnalysisPage,
}));
const AnalysesPage = lazy(async () => ({
  default: (await import("./features/analyses/list/AnalysesPage")).AnalysesPage,
}));
const CreditsPage = lazy(async () => ({
  default: (await import("./features/billing/CreditsPage")).CreditsPage,
}));
const SuccessPage = lazy(async () => ({
  default: (await import("./features/billing/SuccessPage")).SuccessPage,
}));
const PayPage = lazy(async () => ({
  default: (await import("./features/billing/PayPage")).PayPage,
}));
const MarketLayout = lazy(async () => ({
  default: (await import("./features/market/MarketLayout")).MarketLayout,
}));
const OtodomExplorer = lazy(async () => ({
  default: (await import("./features/market/OtodomExplorer")).OtodomExplorer,
}));
const PlacePage = lazy(async () => ({
  default: (await import("./features/market/PlacePage")).PlacePage,
}));
const DistrictPage = lazy(async () => ({
  default: (await import("./features/market/DistrictPage")).DistrictPage,
}));
const GusPage = lazy(async () => ({
  default: (await import("./features/market/GusPage")).GusPage,
}));
const InteriorPage = lazy(async () => ({
  default: (await import("./features/interior/InteriorPage")).InteriorPage,
}));
const InteriorProjectPage = lazy(async () => ({
  default: (await import("./features/interior/ProjectPage")).ProjectPage,
}));
const SettingsPage = lazy(async () => ({
  default: (await import("./features/settings/SettingsPage")).SettingsPage,
}));
const AnalysisPage = lazy(async () => ({
  default: (await import("./features/analyses/AnalysisPage")).AnalysisPage,
}));

/** `/app/market` is the Otodom tab. */
function MarketRoot() {
  const location = useLocation();
  return <Navigate to={`/app/market/otodom${location.search}`} replace />;
}

/** The place address before the tabs (`/app/market/torun`) keeps working. */
function LegacyPlace() {
  const location = useLocation();
  const { locationId = "" } = useParams();
  return <Navigate to={`/app/market/otodom/${encodeURIComponent(locationId)}${location.search}`} replace />;
}

/** A page whose code loads on first visit: a quiet status while it loads, never a blank screen. */
function lazyPage(Page: ComponentType) {
  return (
    <Suspense fallback={<AppLoading />}>
      <Page />
    </Suspense>
  );
}

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
          // The default payment link Paddle redirects the buyer to (docs/PADDLE-INTEGRATION.md section 3).
          { path: "/pay", element: lazyPage(PayPage) },
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
                  { path: "/app/credits", element: lazyPage(CreditsPage) },
                  { path: "/app/credits/success", element: lazyPage(SuccessPage) },
                  // The analysis pages load on first visit (audit F17, #312): the report and the collection are the
                  // largest features and most visits start on the Pulpit. A chunk that fails to load (a deploy
                  // replaced the files) throws while rendering, into this RouteError, which offers a reload.
                  { path: "/app/analyses/new", element: lazyPage(NewAnalysisPage) },
                  { path: "/app/analyses", element: lazyPage(AnalysesPage) },
                  { path: "/app/analyses/:auditId", element: lazyPage(AnalysisPage) },
                  // Rynek: two sources, two tabs, each a path of its own (RM-439). The bare address and the old
                  // `/app/market/:id` place address go to the Otodom tab, keeping the query.
                  { path: "/app/market", element: <MarketRoot /> },
                  {
                    path: "/app/market",
                    element: lazyPage(MarketLayout),
                    children: [
                      { path: "otodom", element: lazyPage(OtodomExplorer) },
                      { path: "otodom/:locationId", element: lazyPage(PlacePage) },
                      { path: "otodom/:locationId/:districtKey", element: lazyPage(DistrictPage) },
                      { path: "gus", element: lazyPage(GusPage) },
                      { path: "gus/:locationId", element: lazyPage(GusPage) },
                      { path: ":locationId", element: <LegacyPlace /> },
                    ],
                  },
                  { path: "/app/interior", element: lazyPage(InteriorPage) },
                  { path: "/app/interior/:projectId", element: lazyPage(InteriorProjectPage) },
                  pending("listing", "/app/listings/new"),
                  { path: "/app/settings", element: lazyPage(SettingsPage) },
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
