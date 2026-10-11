import sentry_sdk
from rm_core.observability import init_sentry, scrub_event
from rm_core.settings import Settings


def test_sentry_is_off_without_a_dsn() -> None:
    assert init_sentry(Settings(sentry_dsn="")) is False


def test_sentry_initialises_with_a_dsn_and_pii_off() -> None:
    try:
        assert init_sentry(Settings(sentry_dsn="https://key@o0.ingest.sentry.io/1", app_env="test")) is True
        options = sentry_sdk.get_client().options
        assert options["send_default_pii"] is False
        assert options["environment"] == "test"
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()  # reset to a disabled client for the other tests


def test_scrubber_removes_cookies_auth_bodies_and_user_details() -> None:
    event = {
        "request": {
            "cookies": {"rm_session": "secret"},
            "data": {"id_token": "x"},
            "query_string": "token=abc",
            "headers": {
                "Authorization": "Bearer x",
                "Cookie": "a=b",
                "Stripe-Signature": "s",
                "Accept": "*/*",
            },
        },
        "user": {"id": "u1", "email": "a@example.test", "ip_address": "1.2.3.4"},
    }
    out = scrub_event(event)
    assert out["request"] == {"headers": {"Accept": "*/*"}}
    assert out["user"] == {"id": "u1"}
