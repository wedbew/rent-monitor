import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../config", () => ({
  config: { paddleClientToken: "test_fixture_token", paddleEnvironment: "sandbox" },
}));

import { runTenantCleanups } from "../../shell/tenant";
import { loadPaddle, openCheckout, PADDLE_SCRIPT, PaddleError, resetPaddleForTests } from "./paddle";

function stub() {
  const paddle = {
    Environment: { set: vi.fn() },
    Initialize: vi.fn(),
    Checkout: { open: vi.fn(), close: vi.fn() },
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
    expect(paddle.Initialize).toHaveBeenCalledWith({
      token: "test_fixture_token",
      eventCallback: expect.any(Function) as unknown,
    });
    expect(paddle.Environment.set).toHaveBeenCalledWith("sandbox");
  });

  it("opens a transaction with an absolute return address that leads back to the polling page", async () => {
    const paddle = stub();
    await openCheckout("txn_fixture0001", "/app/credits/success?purchase=abc", {
      signal: new AbortController().signal,
    });
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

  it("a script that loads but defines no Paddle is a failure, and is removed so a retry injects a fresh one", async () => {
    const pending = loadPaddle();
    document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)?.dispatchEvent(new Event("load"));
    await expect(pending).rejects.toBeInstanceOf(PaddleError);
    expect(document.head.querySelectorAll(`script[src="${PADDLE_SCRIPT}"]`)).toHaveLength(0);
  });
});

describe("the checkout lifetime: nothing opens after the caller left", () => {
  beforeEach(() => resetPaddleForTests());
  afterEach(() => {
    delete window.Paddle;
    document.head.querySelectorAll("script[src*='paddle']").forEach((node) => node.remove());
  });

  const finishLoading = (paddle: ReturnType<typeof stub>) => {
    window.Paddle = paddle;
    document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)?.dispatchEvent(new Event("load"));
  };

  it("does not open when the caller left while the script was still loading", async () => {
    const controller = new AbortController();
    const pending = openCheckout("txn_fixture0001", "/app/credits/success", { signal: controller.signal });
    delete window.Paddle; // the script is loading, nothing is defined yet
    await Promise.resolve();
    controller.abort(); // unmount, another transaction or a route change
    const paddle = stub();
    delete window.Paddle;
    finishLoading(paddle);
    await expect(pending).rejects.toMatchObject({ kind: "cancelled" });
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
  });

  it("does not open when the session moved on while the script was loading", async () => {
    let live = true;
    const pending = openCheckout("txn_fixture0001", "/app/credits/success", {
      signal: new AbortController().signal,
      current: () => live,
    });
    await Promise.resolve();
    live = false; // sign-out, or account A became account B
    const paddle = stub();
    delete window.Paddle;
    finishLoading(paddle);
    await expect(pending).rejects.toMatchObject({ kind: "cancelled" });
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
  });

  it("does not even start loading for a caller that is already gone", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(
      openCheckout("txn_fixture0001", "/app/credits/success", { signal: controller.signal }),
    ).rejects.toMatchObject({ kind: "cancelled" });
    expect(document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)).toBeNull();
  });

  it("closes an open overlay when the caller goes away", async () => {
    const paddle = stub();
    const controller = new AbortController();
    await openCheckout("txn_fixture0001", "/pay", { signal: controller.signal });
    expect(paddle.Checkout.open).toHaveBeenCalledOnce();
    controller.abort();
    expect(paddle.Checkout.close).toHaveBeenCalledOnce();
  });

  it("closes a signed-in person's overlay when the session ends, and a public one is left alone", async () => {
    const paddle = stub();
    await openCheckout("txn_fixture0001", "/app/credits/success", {
      signal: new AbortController().signal,
      closeOnSessionEnd: true,
    });
    runTenantCleanups();
    expect(paddle.Checkout.close).toHaveBeenCalledOnce();

    resetPaddleForTests();
    const other = stub();
    await openCheckout("txn_fixture0002", "/pay", { signal: new AbortController().signal });
    runTenantCleanups();
    expect(other.Checkout.close).not.toHaveBeenCalled();
  });

  it("forgets the overlay once Paddle says it was closed, so a later session end touches nothing", async () => {
    const paddle = stub();
    await openCheckout("txn_fixture0001", "/app/credits/success", {
      signal: new AbortController().signal,
      closeOnSessionEnd: true,
    });
    const init = paddle.Initialize.mock.calls[0]?.[0] as { eventCallback: (e: { name: string }) => void };
    init.eventCallback({ name: "checkout.closed" });
    runTenantCleanups();
    expect(paddle.Checkout.close).not.toHaveBeenCalled();
  });

  it("an SDK without close() is tolerated", async () => {
    const paddle = stub();
    delete (paddle.Checkout as { close?: unknown }).close;
    const controller = new AbortController();
    await openCheckout("txn_fixture0001", "/pay", { signal: controller.signal });
    expect(() => controller.abort()).not.toThrow();
  });
});
