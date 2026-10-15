import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";

import { createQueryClient } from "./api/query";
import { router } from "./routes";
import "./styles/globals.css";

const queryClient = createQueryClient();

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html has no #root element");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
