import httpx
import pytest
from journey_check import JourneyError, run_journey

AUDIT_ID = "11111111-1111-1111-1111-111111111111"


def make_client(
    statuses: list[str], charge: str, *, anonymous_status: int = 401, login_status: int = 200
) -> httpx.Client:
    polls = iter(statuses)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/auth/login":
            assert request.headers["origin"] == "https://beta.example.test"
            return httpx.Response(login_status, json={})
        if path == "/api/audits" and request.method == "POST":
            return httpx.Response(202, json={"audit_id": AUDIT_ID})
        if path == f"/api/audits/{AUDIT_ID}":
            if "cookie" not in request.headers and not request.headers.get("x-test-session"):
                return httpx.Response(anonymous_status, json={})
            status = next(polls)
            ok = status.startswith("succeeded")
            return httpx.Response(
                200, json={"status": status, "charge_state": charge, "result": {"a": 1} if ok else None}
            )
        return httpx.Response(404)

    return httpx.Client(
        base_url="http://api.test", transport=httpx.MockTransport(handler), headers={"x-test-session": "1"}
    )


def anonymous_of(client: httpx.Client) -> httpx.Client:
    """Same server, without the session header."""
    return httpx.Client(base_url="http://api.test", transport=client._transport)


def run(client: httpx.Client, **kwargs: object) -> list[str]:
    return run_journey(
        client,
        email="a@example.test",
        password="pw",
        listing="123456",
        origin="https://beta.example.test",
        sleep=lambda _s: None,
        anonymous=anonymous_of(client),
        **kwargs,  # type: ignore[arg-type]
    )


def test_failed_audit_with_released_credit_passes_by_default() -> None:
    steps = run(make_client(["queued", "running", "failed_upstream"], "released"))
    assert steps[-2] == "terminal failed_upstream, charge released"
    assert steps[-1].startswith("anonymous read refused")


def test_success_captures_and_returns_result() -> None:
    steps = run(make_client(["succeeded_degraded"], "captured"), expect="success")
    assert "terminal succeeded_degraded, charge captured" in steps


def test_failure_when_success_was_expected() -> None:
    with pytest.raises(JourneyError, match="expected success"):
        run(make_client(["failed_upstream"], "released"), expect="success")


def test_failed_audit_that_kept_the_charge_fails() -> None:
    with pytest.raises(JourneyError, match="not settled"):
        run(make_client(["failed_internal"], "reserved"))


def test_failed_audit_that_captured_fails() -> None:
    with pytest.raises(JourneyError, match="must release"):
        run(make_client(["failed_internal"], "captured"))


def test_login_failure_stops_the_journey() -> None:
    with pytest.raises(JourneyError, match="login returned 401"):
        run(make_client(["queued"], "reserved", login_status=401))


def test_anonymous_read_that_succeeds_fails() -> None:
    with pytest.raises(JourneyError, match="anonymous read returned 200"):
        run(make_client(["failed_upstream"], "released", anonymous_status=200))


def test_stuck_audit_times_out() -> None:
    with pytest.raises(JourneyError, match="still queued"):
        run(make_client(["queued"] * 50, "reserved"), timeout_s=0.0)
