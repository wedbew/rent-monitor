import { createBrowserRouter } from "react-router";

import { Placeholder } from "./Placeholder";

/** The one place routes are declared. The app shell and the real pages arrive with #270 onwards. */
export const routes = [{ path: "*", element: <Placeholder /> }];

export const router = createBrowserRouter(routes);
