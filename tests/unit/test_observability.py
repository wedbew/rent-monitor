from typing import Any, cast

import sentry_sdk
from rm_core.observability import _before_send, init_sentry, redact_text, scrub_event
from rm_core.settings import Settings
from sentry_sdk.types import Event


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


# ---------- RM-149: frame variables, breadcrumbs and free text ----------
def test_frame_variables_are_removed_even_if_present() -> None:
    event = {
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": "failed for ana@example.test",
                    "stacktrace": {
                        "frames": [{"function": "f", "vars": {"email": "ana@example.test", "url": "x"}}]
                    },
                }
            ]
        }
    }
    out = scrub_event(event)
    frame = out["exception"]["values"][0]["stacktrace"]["frames"][0]
    assert "vars" not in frame
    assert frame["function"] == "f"  # the useful part of the frame stays
    assert out["exception"]["values"][0]["value"] == "failed for [email]"


def test_breadcrumb_data_is_dropped_and_messages_are_redacted() -> None:
    event = {
        "breadcrumbs": {
            "values": [
                {
                    "message": "GET /login/email#t=abc123SECRET sent to ana@example.test",
                    "data": {"email": "a@b.pl"},
                },
                {"message": "plain", "category": "query"},
            ]
        }
    }
    out = scrub_event(event)
    first, second = out["breadcrumbs"]["values"]
    assert "data" not in first
    assert "abc123SECRET" not in first["message"]
    assert "ana@example.test" not in first["message"]
    assert second == {"message": "plain", "category": "query"}


def test_extra_loses_sensitive_keys_and_redacts_text() -> None:
    event = {"extra": {"credential": "eyJhbGciOi.eyJzdWIiOiIx.sig", "note": "mail ana@example.test", "n": 3}}
    out = scrub_event(event)
    assert out["extra"]["note"] == "mail [email]"
    assert out["extra"]["n"] == 3
    assert "eyJ" not in str(out["extra"])


def test_log_message_and_params_are_scrubbed() -> None:
    event = {
        "message": "link https://app.test/login/email#t=TOKEN123 for ana@example.test",
        "logentry": {
            "message": "user %s",
            "formatted": "user ana@example.test",
            "params": ["ana@example.test"],
        },
    }
    out = scrub_event(event)
    assert "TOKEN123" not in out["message"]
    assert "ana@example.test" not in out["message"]
    assert out["logentry"] == {"message": "user %s", "formatted": "user [email]"}


def test_redact_text_covers_tokens_jwts_and_bearer_headers() -> None:
    text = "Authorization: Bearer abc.DEF-123 token=xyz789 id_token=eyJhbGci.eyJzdWIi.sigpart code=4/0Abc&x=1"
    redacted = redact_text(text)
    for secret in ("abc.DEF-123", "xyz789", "eyJhbGci", "4/0Abc"):
        assert secret not in redacted
    assert "x=1" in redacted  # unrelated parameters survive


def test_redact_text_covers_a_token_at_the_start_of_a_text_or_line() -> None:
    """RM-280: `token=...` with nothing before it used to escape (the pattern needed a separator first)."""
    cases = {"token=abc123 for x": "abc123", "first line\ncredential=xyz": "xyz", "session=s1&x=1": "s1&"}
    for text, secret in cases.items():
        assert secret not in redact_text(text), redact_text(text)


def test_redact_text_leaves_ordinary_text_alone() -> None:
    text = "audit 5f2a1c9e-1111-4222-8333-444455556666 failed after 3 attempts (UPSTREAM_BLOCKED)"
    assert redact_text(text) == text


def test_the_request_url_is_redacted() -> None:
    out = scrub_event({"request": {"url": "https://app.test/login/email#t=SECRETTOKEN"}})
    assert "SECRETTOKEN" not in out["request"]["url"]


def test_an_event_that_cannot_be_scrubbed_is_dropped_not_sent() -> None:
    class Explodes(dict[str, Any]):
        def get(self, *_a: object, **_k: object) -> object:
            raise RuntimeError("boom")

    assert _before_send(cast("Event", Explodes()), {}) is None


def test_local_variables_are_switched_off_in_the_sdk() -> None:
    try:
        assert init_sentry(Settings(sentry_dsn="https://key@o0.ingest.sentry.io/1", app_env="test")) is True
        assert sentry_sdk.get_client().options["include_local_variables"] is False
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init()
