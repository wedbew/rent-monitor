"""Create a Stripe test clock and a customer attached to it, to test renewals (blueprint §4.6).

Sandbox only: refuses any key that is not a test-mode key. Reads STRIPE_SECRET_KEY (and optionally
STRIPE_API_VERSION) from the environment and never prints the key. Uses the REST API directly, so no SDK pin
is needed before RM-14.

    uv run python scripts/stripe_clock_customer.py --email buyer@example.test
    stripe test_helpers test_clocks advance <clk_...> --frozen-time <unix>
"""

import argparse
import os
import sys
import time

import httpx

API = "https://api.stripe.com/v1"
TEST_PREFIXES = ("sk_test_", "rk_test_")


def require_test_key(key: str) -> str:
    if not key.startswith(TEST_PREFIXES):
        msg = "refusing to run: STRIPE_SECRET_KEY must be a test-mode key (sk_test_ / rk_test_)"
        raise SystemExit(msg)
    return key


def create_clock_customer(client: httpx.Client, email: str, frozen_time: int) -> tuple[str, str]:
    clock = client.post("/test_helpers/test_clocks", data={"frozen_time": str(frozen_time)})
    clock.raise_for_status()
    clock_id: str = clock.json()["id"]
    customer = client.post("/customers", data={"email": email, "test_clock": clock_id})
    customer.raise_for_status()
    return clock_id, customer.json()["id"]


def build_client(
    key: str, api_version: str | None = None, transport: httpx.BaseTransport | None = None
) -> httpx.Client:
    headers = {"Authorization": f"Bearer {require_test_key(key)}"}
    if api_version:
        headers["Stripe-Version"] = api_version
    return httpx.Client(
        base_url=API, headers=headers, timeout=httpx.Timeout(15.0, connect=5.0), transport=transport
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    with build_client(
        os.environ.get("STRIPE_SECRET_KEY", ""), os.environ.get("STRIPE_API_VERSION")
    ) as client:
        clock_id, customer_id = create_clock_customer(client, args.email, int(time.time()))
    print(f"test_clock={clock_id} customer={customer_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
