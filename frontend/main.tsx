import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { createQueryClient } from "./api/query";
import { captureFragmentToken } from "./features/auth/token";
import { router } from "./routes";
import { initObservability } from "./shell/observability";
import { SessionProvider } from "./shell/session";
import "./styles/globals.css";

// Mailed links carry a one-time token in the fragment: take it out of the address bar before anything renders.
captureFragmentToken();

// Error reporting starts only when configured; a failure to load it never blocks the app.
void initObservability().catch(() => false);

const queryClient = createQueryClient();

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html has no #root element");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>
  </StrictMode>,
);
