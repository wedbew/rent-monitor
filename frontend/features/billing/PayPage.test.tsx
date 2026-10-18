import { act, render } from "@testing-library/react";
import { StrictMode } from "react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../config", () => ({
  config: { paddleClientToken: "test_fixture_token", paddleEnvironment: "sandbox" },
}));

import { PayPage } from "./PayPage";
import { PADDLE_SCRIPT, resetPaddleForTests } from "./paddle";

const paddle = {
  Environment: { set: vi.fn() },
  Initialize: vi.fn(),
  Checkout: { open: vi.fn(), close: vi.fn() },
};

/** `/pay` with Paddle.js still downloading: the script arrives only when the test says so. */
function mount(txn: string, strict = false) {
  const router = createMemoryRouter([{ path: "/pay", element: <PayPage /> }], {
    initialEntries: [`/pay?_ptxn=${txn}`],
  });
  const tree = <RouterProvider router={router} />;
  const view = render(strict ? <StrictMode>{tree}</StrictMode> : tree);
  return { router, view };
}
const arrive = () => {
  window.Paddle = paddle;
  document.head.querySelector(`script[src="${PADDLE_SCRIPT}"]`)?.dispatchEvent(new Event("load"));
};
const settle = () => new Promise((r) => setTimeout(r, 30));

beforeEach(() => {
  resetPaddleForTests();
  for (const fn of [paddle.Checkout.open, paddle.Checkout.close, paddle.Initialize]) fn.mockReset();
  delete window.Paddle;
});
afterEach(() => document.head.querySelectorAll("script[src*='paddle']").forEach((n) => n.remove()));

describe("/pay: the transaction opens only while its page is still there", () => {
  it("opens the transaction once the script has loaded", async () => {
    mount("txn_fixture0001");
    arrive();
    await settle();
    expect(paddle.Checkout.open).toHaveBeenCalledOnce();
  });

  it("does not open after the page was left while the script was loading", async () => {
    const { view } = mount("txn_fixture0001");
    view.unmount();
    arrive();
    await settle();
    expect(paddle.Checkout.open).not.toHaveBeenCalled();
  });

  it("opens only the transaction that is in the address now, when it changed while loading", async () => {
    const { router } = mount("txn_firstfirst001");
    await act(() => router.navigate("/pay?_ptxn=txn_secondsecond1"));
    arrive();
    await settle();
    expect(paddle.Checkout.open).toHaveBeenCalledOnce();
    expect(paddle.Checkout.open.mock.calls[0]?.[0]).toMatchObject({ transactionId: "txn_secondsecond1" });
  });

  it("opens exactly once under StrictMode's effect replay", async () => {
    mount("txn_fixture0001", true);
    arrive();
    await settle();
    expect(paddle.Checkout.open).toHaveBeenCalledOnce();
  });

  it("closes the overlay when the page is left afterwards", async () => {
    const { view } = mount("txn_fixture0001");
    arrive();
    await settle();
    view.unmount();
    expect(paddle.Checkout.close).toHaveBeenCalledOnce();
  });
});
