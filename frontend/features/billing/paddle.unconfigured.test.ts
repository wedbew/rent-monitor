import { describe, expect, it, vi } from "vitest";

vi.mock("../../config", () => ({ config: { paddleClientToken: "", paddleEnvironment: "sandbox" } }));

import { loadPaddle, paddleConfigured, PADDLE_SCRIPT } from "./paddle";

describe("without a client token", () => {
  it("nothing is offered and nothing is ever fetched", async () => {
    expect(paddleConfigured()).toBe(false);
    await expect(loadPaddle()).rejects.toMatchObject({ kind: "not-configured" });
    expect(document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)).toBeNull();
  });
});
