import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, expect } from "vitest";

import { server, unmatched } from "./handlers";

beforeAll(() => {
  // A request nobody mocked is a bug in the test, not a network call: never reach the real network.
  server.listen({ onUnhandledFrame: "error" });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  const missed = unmatched.splice(0);
  expect(missed, "requests the scenario had no route for").toEqual([]);
});

afterAll(() => {
  server.close();
});
