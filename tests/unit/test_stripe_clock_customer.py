import httpx
import pytest
from stripe_clock_customer import build_client, create_clock_customer, require_test_key


@pytest.mark.parametrize("key", ["", "sk_live_abc", "rk_live_abc", "pk_test_abc", "whsec_x"])
def test_refuses_anything_but_a_test_key(key: str) -> None:
    with pytest.raises(SystemExit, match="test-mode key"):
        require_test_key(key)


def test_creates_clock_then_customer_attached_to_it() -> None:
    seen: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.content.decode()))
        assert request.headers["authorization"] == "Bearer sk_test_x"
        assert request.headers["stripe-version"] == "2026-09-30.endive"
        if request.url.path.endswith("/test_clocks"):
            return httpx.Response(200, json={"id": "clock_1"})
        return httpx.Response(200, json={"id": "cus_1"})

    client = build_client("sk_test_x", "2026-09-30.endive", transport=httpx.MockTransport(handler))
    assert create_clock_customer(client, "b@example.test", 1_800_000_000) == ("clock_1", "cus_1")
    assert seen[0][1] == "/v1/test_helpers/test_clocks"
    assert "frozen_time=1800000000" in seen[0][2]
    assert seen[1][1] == "/v1/customers"
    assert "test_clock=clock_1" in seen[1][2]
