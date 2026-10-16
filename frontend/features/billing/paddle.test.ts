import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../config", () => ({
  config: { paddleClientToken: "test_fixture_token", paddleEnvironment: "sandbox" },
}));

import { loadPaddle, openCheckout, PADDLE_SCRIPT, PaddleError, resetPaddleForTests } from "./paddle";

function stub() {
  const paddle = {
    Environment: { set: vi.fn() },
    Initialize: vi.fn(),
    Checkout: { open: vi.fn() },
  };
  window.Paddle = paddle;
  return paddle;
}

describe("Paddle.js loader", () => {
  beforeEach(() => resetPaddleForTests());
  afterEach(() => {
    delete window.Paddle;
    document.head.querySelectorAll("script[src*='paddle']").forEach((node) => node.remove());
  });

  it("uses a Paddle.js that is already on the page without fetching anything, and initialises it once", async () => {
    const paddle = stub();
    await loadPaddle();
    await loadPaddle();
    expect(document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)).toBeNull();
    expect(paddle.Initialize).toHaveBeenCalledOnce();
    expect(paddle.Initialize).toHaveBeenCalledWith({ token: "test_fixture_token" });
    expect(paddle.Environment.set).toHaveBeenCalledWith("sandbox");
  });

  it("opens a transaction with an absolute return address that leads back to the polling page", async () => {
    const paddle = stub();
    await openCheckout("txn_fixture0001", "/app/credits/success?purchase=abc");
    expect(paddle.Checkout.open).toHaveBeenCalledWith({
      transactionId: "txn_fixture0001",
      settings: {
        displayMode: "overlay",
        successUrl: `${window.location.origin}/app/credits/success?purchase=abc`,
      },
    });
  });

  it("injects the script when absent, and a script that fails to load is a typed failure that can be retried", async () => {
    const first = loadPaddle();
    const script = document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`);
    expect(script).not.toBeNull();
    script?.dispatchEvent(new Event("error"));
    await expect(first).rejects.toMatchObject({ kind: "load-failed" });

    const second = loadPaddle();
    stub();
    document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)?.dispatchEvent(new Event("load"));
    await expect(second).resolves.toBeDefined();
  });

  it("a script that loads but defines no Paddle is a failure", async () => {
    const pending = loadPaddle();
    document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)?.dispatchEvent(new Event("load"));
    await expect(pending).rejects.toBeInstanceOf(PaddleError);
  });
});
